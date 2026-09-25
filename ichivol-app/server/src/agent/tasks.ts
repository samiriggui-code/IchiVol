/**
 * Chantier 2 E0 — durable AgentTask queue (Comp AI claim / lease pattern).
 *
 * DOES: schedule / claimDue (FOR UPDATE SKIP LOCKED) / complete / retire.
 * DOES NOT: call Claude, evaluate_watch_condition (E2), or touch paper/broker.
 */
import { Prisma } from '@prisma/client'
import { db } from '../db.js'
import {
  DEFAULT_AGENT_ID,
  TASK_CLAIM_BATCH,
  TASK_LEASE_MS,
  TASK_MAX_ATTEMPTS,
  TASK_RETIRE_BATCH,
  TASK_STALE_SCAN,
  TASK_STATUS,
} from './taskConfig.js'
import { writeAgentLog } from './agentLog.js'

export type LeasedTask = {
  id: string
  agentId: string
  kind: string
  symbol: string | null
  payload: Prisma.JsonValue | null
  condition: Prisma.JsonValue | null
  attempts: number
  dueAt: Date
  idempotencyKey: string
}

export type ScheduleTaskInput = {
  agentId?: string
  kind: string
  symbol?: string | null
  payload?: Prisma.InputJsonValue | null
  condition?: Prisma.InputJsonValue | null
  dueAt: Date
  /** Required — unique. Retries after crash must reuse the same key. */
  idempotencyKey: string
}

export type ScheduleTaskResult = {
  id: string
  created: boolean
}

/** Insert or return existing row for the same idempotency key. */
export async function scheduleTask(input: ScheduleTaskInput): Promise<ScheduleTaskResult> {
  const agentId = input.agentId ?? DEFAULT_AGENT_ID
  const existing = await db.agentTask.findUnique({
    where: { idempotencyKey: input.idempotencyKey },
    select: { id: true },
  })
  if (existing) {
    return { id: existing.id, created: false }
  }

  try {
    const row = await db.agentTask.create({
      data: {
        agentId,
        kind: input.kind,
        symbol: input.symbol ?? null,
        payload: input.payload ?? undefined,
        condition: input.condition ?? undefined,
        dueAt: input.dueAt,
        status: TASK_STATUS.pending,
        idempotencyKey: input.idempotencyKey,
      },
      select: { id: true },
    })
    return { id: row.id, created: true }
  } catch (err) {
    // Race: another worker inserted the same key between findUnique and create.
    if (
      err instanceof Prisma.PrismaClientKnownRequestError &&
      err.code === 'P2002'
    ) {
      const again = await db.agentTask.findUnique({
        where: { idempotencyKey: input.idempotencyKey },
        select: { id: true },
      })
      if (again) return { id: again.id, created: false }
    }
    throw err
  }
}

/**
 * Atomically claim due tasks (pending or lease expired), pose lease, bump attempts.
 * Postgres: FOR UPDATE SKIP LOCKED — concurrent workers never double-claim.
 */
export async function claimDue(
  limit: number = TASK_CLAIM_BATCH,
  leaseMs: number = TASK_LEASE_MS,
): Promise<LeasedTask[]> {
  const now = new Date()
  const until = new Date(now.getTime() + leaseMs)

  const claimed = await db.$queryRaw<LeasedTask[]>`
    UPDATE "agent_tasks" AS t
    SET "leaseUntil" = ${until},
        "status" = ${TASK_STATUS.leased},
        "attempts" = t."attempts" + 1,
        "updatedAt" = ${now}
    FROM (
      SELECT t2.id FROM "agent_tasks" AS t2
      WHERE t2."status" IN (${TASK_STATUS.pending}, ${TASK_STATUS.leased})
        AND t2."dueAt" <= ${now}
        AND (t2."leaseUntil" IS NULL OR t2."leaseUntil" < ${now})
        AND t2."attempts" < ${TASK_MAX_ATTEMPTS}
      ORDER BY t2."dueAt" ASC
      LIMIT ${limit}
      FOR UPDATE SKIP LOCKED
    ) AS due
    WHERE t.id = due.id
    RETURNING t.id, t."agentId", t.kind, t.symbol, t.payload, t.condition,
      t.attempts, t."dueAt", t."idempotencyKey";
  `

  return claimed
}

export async function completeTask(
  taskId: string,
  result?: Prisma.InputJsonValue | null,
): Promise<boolean> {
  const { count } = await db.agentTask.updateMany({
    where: {
      id: taskId,
      status: { in: [TASK_STATUS.leased, TASK_STATUS.pending] },
    },
    data: {
      status: TASK_STATUS.completed,
      leaseUntil: null,
      result: result ?? undefined,
      error: null,
    },
  })
  return count > 0
}

export async function failTask(taskId: string, error: string): Promise<boolean> {
  const { count } = await db.agentTask.updateMany({
    where: {
      id: taskId,
      status: { in: [TASK_STATUS.leased, TASK_STATUS.pending] },
    },
    data: {
      status: TASK_STATUS.failed,
      leaseUntil: null,
      error: error.slice(0, 2000),
    },
  })
  return count > 0
}

/** Release expired leases so claimDue can pick them up again (crash recovery). */
export async function releaseStaleLeases(limit: number = TASK_STALE_SCAN): Promise<number> {
  const now = new Date()
  const stale = await db.$queryRaw<{ id: string }[]>`
    SELECT id FROM "agent_tasks"
    WHERE "status" = ${TASK_STATUS.leased}
      AND "leaseUntil" IS NOT NULL
      AND "leaseUntil" < ${now}
      AND "attempts" < ${TASK_MAX_ATTEMPTS}
    ORDER BY "leaseUntil" ASC
    LIMIT ${limit}
    FOR UPDATE SKIP LOCKED
  `
  if (stale.length === 0) return 0

  const ids = stale.map((r) => r.id)
  const { count } = await db.agentTask.updateMany({
    where: { id: { in: ids }, status: TASK_STATUS.leased },
    data: { status: TASK_STATUS.pending, leaseUntil: null },
  })
  return count
}

/** Retire open tasks that exhausted attempts (lease expired or never leased). */
export async function retireExhausted(limit: number = TASK_RETIRE_BATCH): Promise<number> {
  const now = new Date()
  const outcome = 'retired: max attempts exceeded'

  const retired = await db.$queryRaw<{ id: string; agentId: string }[]>`
    UPDATE "agent_tasks" AS t
    SET "status" = ${TASK_STATUS.retired},
        "leaseUntil" = NULL,
        "error" = ${outcome},
        "updatedAt" = ${now}
    WHERE t.id IN (
      SELECT c.id FROM "agent_tasks" AS c
      WHERE c."status" IN (${TASK_STATUS.pending}, ${TASK_STATUS.leased})
        AND c."attempts" >= ${TASK_MAX_ATTEMPTS}
        AND (c."leaseUntil" IS NULL OR c."leaseUntil" < ${now})
      ORDER BY c."dueAt" ASC
      LIMIT ${limit}
      FOR UPDATE SKIP LOCKED
    )
    RETURNING t.id, t."agentId";
  `

  for (const row of retired) {
    await writeAgentLog({
      agentId: row.agentId,
      level: 'REFUSÉ',
      source: 'runtime.retire',
      message: outcome,
      taskId: row.id,
    }).catch(() => {})
  }

  return retired.length
}

export type ReconcileResult = {
  released: number
  retired: number
}

export async function reconcileStaleTasks(): Promise<ReconcileResult> {
  const released = await releaseStaleLeases()
  const retired = await retireExhausted()
  return { released, retired }
}
