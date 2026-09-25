/**
 * Chantier 2 E1 — minute dispatcher + poke drain.
 *
 * DOES: reconcile stale leases, claim due tasks, missionRunner process.
 * DOES NOT: evaluate_watch_condition DSL (E2), submit orders / auto-open.
 */
import { claimDue, failTask, reconcileStaleTasks } from '../tasks.js'
import { writeAgentLog } from '../agentLog.js'
import { TASK_CLAIM_BATCH, TASK_WORKER_INTERVAL_MS } from '../taskConfig.js'
import { processClaimedTask } from './missionRunner.js'

export type DrainSummary = {
  released: number
  retired: number
  claimed: number
  completed: number
  deferred: number
  failed: number
  wokeLlm: number
}

export async function drainDueTasks(): Promise<DrainSummary> {
  const { released, retired } = await reconcileStaleTasks()
  const claimed = await claimDue(TASK_CLAIM_BATCH)
  let completed = 0
  let deferred = 0
  let failed = 0
  let wokeLlm = 0

  for (const task of claimed) {
    try {
      const outcome = await processClaimedTask(task)
      if (outcome.action === 'completed') {
        completed += 1
        if (outcome.wakeLlm) wokeLlm += 1
      } else if (outcome.action === 'deferred') {
        deferred += 1
      } else {
        failed += 1
        await failTask(task.id, outcome.error).catch(() => {})
      }
    } catch (err) {
      failed += 1
      const msg = err instanceof Error ? err.message : String(err)
      await failTask(task.id, msg).catch(() => {})
      await writeAgentLog({
        agentId: task.agentId,
        level: 'REFUSÉ',
        source: 'runtime.dispatcher',
        message: `E1 process failed: ${msg}`,
        taskId: task.id,
      }).catch(() => {})
    }
  }

  return {
    released,
    retired,
    claimed: claimed.length,
    completed,
    deferred,
    failed,
    wokeLlm,
  }
}

let started = false
let draining = false
let workerStartedAt: Date | null = null
let lastDrainAt: Date | null = null
let lastDrainSummary: DrainSummary | null = null
let lastDrainError: string | null = null

/** Snapshot for GET /api/agents — honest worker liveness (no invented metrics). */
export function getAgentRuntimeSnapshot(): {
  workerStarted: boolean
  workerStartedAt: string | null
  lastDrainAt: string | null
  lastDrain: DrainSummary | null
  lastDrainError: string | null
  intervalMs: number
  draining: boolean
} {
  return {
    workerStarted: started,
    workerStartedAt: workerStartedAt?.toISOString() ?? null,
    lastDrainAt: lastDrainAt?.toISOString() ?? null,
    lastDrain: lastDrainSummary,
    lastDrainError,
    intervalMs: TASK_WORKER_INTERVAL_MS,
    draining,
  }
}

export async function runDispatcherTick(): Promise<DrainSummary | null> {
  if (draining) return null
  draining = true
  try {
    const summary = await drainDueTasks()
    lastDrainAt = new Date()
    lastDrainSummary = summary
    lastDrainError = null
    return summary
  } catch (err) {
    lastDrainAt = new Date()
    lastDrainError = err instanceof Error ? err.message : String(err)
    throw err
  } finally {
    draining = false
  }
}

export function startAgentTaskWorker(): void {
  if (started) return
  started = true
  workerStartedAt = new Date()
  const tick = () => {
    void runDispatcherTick()
      .then((summary) => {
        if (
          summary &&
          (summary.claimed > 0 ||
            summary.released > 0 ||
            summary.retired > 0 ||
            summary.deferred > 0)
        ) {
          console.log(
            `[agent-runtime] drain claimed=${summary.claimed} completed=${summary.completed} ` +
              `deferred=${summary.deferred} woke=${summary.wokeLlm} failed=${summary.failed} ` +
              `released=${summary.released} retired=${summary.retired}`,
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
    `[agent-runtime] minute worker started (interval ${TASK_WORKER_INTERVAL_MS / 1000}s) — E1 missionRunner, paper only`,
  )
}
