import type { Request, Response } from 'express'
import { config } from '../config.js'
import { checkSystemHealth, isHealthy } from '../health/check.js'

/**
 * Real dependency check, not a bare liveness ping -- an external uptime
 * monitor (or our own watchdog, notifications/systemWatchdog.ts) pinging
 * this needs a non-200 the moment Postgres or the Python engine actually
 * goes down, not just when the Express process itself is dead.
 */
export async function handleHealth(_req: Request, res: Response): Promise<void> {
  const checks = await checkSystemHealth()
  const ok = isHealthy(checks)
  res.status(ok ? 200 : 503).json({
    ok,
    provider: config.llmProvider,
    model: config.llmModel,
    checks,
  })
}
