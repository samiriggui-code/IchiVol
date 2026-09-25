/**
 * Chantier 2 E0 — stale lease reconciliation (re-export for audit file map).
 * Implementation lives in tasks.ts; this module matches docs/AGENT-RUNTIME-AUDIT.md paths.
 */
export {
  reconcileStaleTasks,
  releaseStaleLeases,
  retireExhausted,
  type ReconcileResult,
} from './tasks.js'
