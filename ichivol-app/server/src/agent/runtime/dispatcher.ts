/**
 * Chantier 2 E0 — minute dispatcher + poke drain.
 *
 * DOES: reconcile stale leases, claim due tasks, stub-process (log + complete).
 * DOES NOT: wake Claude (E1), evaluate_watch_condition (E2), submit orders.
 */
import { completeTask, claimDue, failTask, reconcileStaleTasks, type LeasedTask } from '../tasks.js'
import { writeAgentLog } from '../agentLog.js'
import { TASK_CLAIM_BATCH, TASK_WORKER_INTERVAL_MS } from '../taskConfig.js'

export type DrainSummary = {
  released: number
  retired: number
  claimed: number
  completed: number
  failed: number
}

/**
 * E0 task handler: acknowledge + audit log + complete.
 * Condition evaluation / LLM wake deferred to E1/E2 — note gap in result.
 */
export async function processClaimedTask(task: LeasedTask): Promise<void> {
  const hasCondition = task.condition != null
  await writeAgentLog({
    agentId: task.agentId,
    level: 'PASSE',
    source: 'runtime.dispatcher',
    message: hasCondition
      ? `E0 stub: claimed ${task.kind} ${task.symbol ?? ''} — condition present, evaluate_watch deferred to E2`
      : `E0 stub: claimed ${task.kind} ${task.symbol ?? ''} — completed without LLM`,
    taskId: task.id,
    meta: {
      kind: task.kind,
      attempts: task.attempts,
      idempotencyKey: task.idempotencyKey,
      hasCondition,
    },
  })

  const ok = await completeTask(task.id, {
    phase: 'E0',
    processedAt: new Date().toISOString(),
    wakeLlm: false,
    // Gap: E2 will call engine evaluate_watch_condition before any LLM wake.
    evaluateWatchDeferred: hasCondition,
  })
  if (!ok) {
    throw new Error(`completeTask missed for ${task.id}`)
  }
}

export async function drainDueTasks(): Promise<DrainSummary> {
  const { released, retired } = await reconcileStaleTasks()
  const claimed = await claimDue(TASK_CLAIM_BATCH)
  let completed = 0
  let failed = 0

  for (const task of claimed) {
    try {
      await processClaimedTask(task)
      completed += 1
    } catch (err) {
      failed += 1
      const msg = err instanceof Error ? err.message : String(err)
      await failTask(task.id, msg).catch(() => {})
      await writeAgentLog({
        agentId: task.agentId,
        level: 'REFUSÉ',
        source: 'runtime.dispatcher',
        message: `E0 process failed: ${msg}`,
        taskId: task.id,
      }).catch(() => {})
    }
  }

  return {
    released,
    retired,
    claimed: claimed.length,
    completed,
    failed,
  }
}

let started = false
let draining = false

export async function runDispatcherTick(): Promise<DrainSummary | null> {
  if (draining) return null
  draining = true
  try {
    return await drainDueTasks()
  } finally {
    draining = false
  }
}

export function startAgentTaskWorker(): void {
  if (started) return
  started = true
  const tick = () => {
    void runDispatcherTick()
      .then((summary) => {
        if (summary && (summary.claimed > 0 || summary.released > 0 || summary.retired > 0)) {
          console.log(
            `[agent-runtime] drain claimed=${summary.claimed} completed=${summary.completed} ` +
              `failed=${summary.failed} released=${summary.released} retired=${summary.retired}`,
          )
        }
      })
      .catch((err) => {
        console.error(
          '[agent-runtime] tick failed:',
          err instanceof Error ? err.message : err,
        )
      })
  }
  // Slight delay so boot does not race migrations.
  setTimeout(tick, 15_000)
  setInterval(tick, TASK_WORKER_INTERVAL_MS)
  console.log(
    `[agent-runtime] minute worker started (interval ${TASK_WORKER_INTERVAL_MS / 1000}s) — E0 stub, paper only`,
  )
}
