/** Chantier 2 E0 — dispatch / lease knobs (Comp AI–inspired, paper-only runtime). */

const MINUTE_MS = 60_000

export const TASK_LEASE_MS = Number(process.env.AGENT_TASK_LEASE_MS) || 10 * MINUTE_MS
export const TASK_MAX_ATTEMPTS = Number(process.env.AGENT_TASK_MAX_ATTEMPTS) || 5
export const TASK_CLAIM_BATCH = Number(process.env.AGENT_TASK_CLAIM_BATCH) || 20
export const TASK_WORKER_INTERVAL_MS =
  Number(process.env.AGENT_TASK_WORKER_INTERVAL_MS) || MINUTE_MS
export const TASK_RETIRE_BATCH = 100
export const TASK_STALE_SCAN = 200

/** Default mono-agent lane until multi-agent is proven necessary. */
export const DEFAULT_AGENT_ID = 'eve'

export const TASK_STATUS = {
  pending: 'pending',
  leased: 'leased',
  completed: 'completed',
  failed: 'failed',
  retired: 'retired',
} as const

export type TaskStatus = (typeof TASK_STATUS)[keyof typeof TASK_STATUS]

export const AGENT_LOG_LEVEL = {
  passe: 'PASSE',
  prudence: 'PRUDENCE',
  refuse: 'REFUSÉ',
} as const

export type AgentLogLevel = (typeof AGENT_LOG_LEVEL)[keyof typeof AGENT_LOG_LEVEL]
