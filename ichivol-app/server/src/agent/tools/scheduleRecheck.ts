/**
 * Chantier 2 E1 — schedule_recheck tool (Comp AI / Eve pattern).
 *
 * DOES: validate reason ≥10, write AgentTask kind=recheck via scheduleTask.
 * DOES NOT: sleep in-process, call Claude, open paper, touch broker/DB directly
 *           beyond Prisma task rows (through tasks.ts).
 */
import type { Prisma } from '@prisma/client'
import { db } from '../../db.js'
import type { AnthropicTool, ToolExecResult } from '../claudeTools.js'
import { nextClosedCandleDueAt } from '../candleDue.js'
import { DEFAULT_AGENT_ID, TASK_STATUS } from '../taskConfig.js'
import { scheduleTask } from '../tasks.js'
import { writeAgentLog } from '../agentLog.js'

export const MIN_RECHECK_REASON_LENGTH = 10

export const SCHEDULE_RECHECK_TOOL: AnthropicTool = {
  name: 'schedule_recheck',
  description:
    "Planifie un réveil agent après la prochaine bougie fermée (+60 s). " +
    "Obligatoire : reason (≥10 caractères) expliquant pourquoi. " +
    "Ne dort pas en process — écrit une tâche durable. Paper only ; pas d'ordre.",
  input_schema: {
    type: 'object',
    properties: {
      symbol: { type: 'string', description: 'Symbole ex. BTCUSDT (requis)' },
      timeframe: { type: 'string', description: "Timeframe 15m|1h|4h|1d (défaut '1h')" },
      reason: {
        type: 'string',
        description: 'Pourquoi rechecker (≥10 caractères, obligatoire)',
      },
      due_at: {
        type: 'string',
        description: 'ISO datetime optionnelle ; sinon next_closed_candle + 60s',
      },
      condition: {
        type: 'object',
        description: 'Condition watch opaque (évaluée en E2) — optionnel',
      },
    },
    required: ['symbol', 'reason'],
  },
}

export type ScheduleRecheckInput = {
  agentId?: string
  symbol: string
  timeframe?: string
  reason: string
  dueAt?: Date
  condition?: Prisma.InputJsonValue | null
  /** Optional user/thread continuity (Copilot thread, not a 2nd chat). */
  userId?: string | null
  threadId?: string | null
}

export type ScheduleRecheckResult = {
  id: string
  created: boolean
  refreshed: boolean
  dueAt: string
  symbol: string
  timeframe: string
}

function normalizeSymbol(raw: string): string {
  return raw.trim().toUpperCase()
}

export function validateRecheckReason(reason: unknown): string | null {
  if (typeof reason !== 'string') return 'reason must be a string'
  const t = reason.trim()
  if (t.length < MIN_RECHECK_REASON_LENGTH) {
    return `reason must be at least ${MIN_RECHECK_REASON_LENGTH} characters`
  }
  return null
}

/**
 * Upsert open recheck for (agent, symbol, timeframe): refresh dueAt/reason
 * if a pending/leased row exists; else create with unique idempotency key.
 */
export async function scheduleRecheck(
  input: ScheduleRecheckInput,
): Promise<ScheduleRecheckResult> {
  const reasonErr = validateRecheckReason(input.reason)
  if (reasonErr) throw new Error(reasonErr)

  const agentId = input.agentId ?? DEFAULT_AGENT_ID
  const symbol = normalizeSymbol(input.symbol)
  if (!symbol) throw new Error('symbol is required')
  const timeframe = (input.timeframe ?? '1h').trim() || '1h'
  const dueAt = input.dueAt ?? nextClosedCandleDueAt(timeframe)
  const reason = input.reason.trim()

  const payload: Prisma.InputJsonValue = {
    reason,
    timeframe,
    trigger: input.dueAt ? 'explicit_due_at' : 'next_closed_candle',
    ...(input.userId ? { userId: input.userId } : {}),
    ...(input.threadId ? { threadId: input.threadId } : {}),
    humanConfirmDefault: true,
    autoOpen: false,
  }

  const open = await db.agentTask.findFirst({
    where: {
      agentId,
      kind: 'recheck',
      symbol,
      status: { in: [TASK_STATUS.pending, TASK_STATUS.leased] },
    },
    orderBy: { dueAt: 'asc' },
  })

  if (open) {
    await db.agentTask.update({
      where: { id: open.id },
      data: {
        dueAt,
        payload,
        condition: input.condition ?? undefined,
        // Keep pending if was pending; leave leased alone (worker owns it).
      },
    })
    await writeAgentLog({
      agentId,
      level: 'PASSE',
      source: 'tool.schedule_recheck',
      message: `Refreshed open recheck ${symbol} ${timeframe}: ${reason.slice(0, 200)}`,
      taskId: open.id,
      meta: { dueAt: dueAt.toISOString(), refreshed: true },
    }).catch(() => {})
    return {
      id: open.id,
      created: false,
      refreshed: true,
      dueAt: dueAt.toISOString(),
      symbol,
      timeframe,
    }
  }

  const idempotencyKey = `recheck:${agentId}:${symbol}:${timeframe}:${dueAt.getTime()}`
  const scheduled = await scheduleTask({
    agentId,
    kind: 'recheck',
    symbol,
    dueAt,
    idempotencyKey,
    payload,
    condition: input.condition ?? null,
  })

  await writeAgentLog({
    agentId,
    level: 'PASSE',
    source: 'tool.schedule_recheck',
    message: `Scheduled recheck ${symbol} ${timeframe}: ${reason.slice(0, 200)}`,
    taskId: scheduled.id,
    meta: { dueAt: dueAt.toISOString(), created: scheduled.created },
  }).catch(() => {})

  return {
    id: scheduled.id,
    created: scheduled.created,
    refreshed: false,
    dueAt: dueAt.toISOString(),
    symbol,
    timeframe,
  }
}

/** Claude tool executor adapter. */
export async function executeScheduleRecheck(
  args: Record<string, unknown>,
  ctx?: { agentId?: string; userId?: string | null; threadId?: string | null },
): Promise<ToolExecResult> {
  try {
    const reasonErr = validateRecheckReason(args.reason)
    if (reasonErr) return { ok: false, content: reasonErr }

    let dueAt: Date | undefined
    if (typeof args.due_at === 'string' && args.due_at.trim()) {
      const parsed = new Date(args.due_at)
      if (Number.isNaN(parsed.getTime())) {
        return { ok: false, content: 'due_at must be a valid ISO datetime' }
      }
      if (parsed.getTime() <= Date.now()) {
        return { ok: false, content: 'due_at must be in the future' }
      }
      dueAt = parsed
    }

    const condition =
      args.condition && typeof args.condition === 'object' && !Array.isArray(args.condition)
        ? (args.condition as Prisma.InputJsonValue)
        : null

    const result = await scheduleRecheck({
      agentId: ctx?.agentId,
      symbol: String(args.symbol ?? ''),
      timeframe: typeof args.timeframe === 'string' ? args.timeframe : '1h',
      reason: String(args.reason),
      dueAt,
      condition,
      userId: ctx?.userId,
      threadId: ctx?.threadId,
    })
    return { ok: true, content: JSON.stringify(result) }
  } catch (err) {
    return { ok: false, content: err instanceof Error ? err.message : String(err) }
  }
}
