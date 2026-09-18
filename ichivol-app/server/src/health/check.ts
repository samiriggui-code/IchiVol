import { config } from '../config.js'
import { db } from '../db.js'

const CHECK_TIMEOUT_MS = 5_000

export interface SystemHealth {
  database: boolean
  engine: boolean
}

async function checkDatabase(): Promise<boolean> {
  try {
    await db.$queryRaw`SELECT 1`
    return true
  } catch {
    return false
  }
}

async function checkEngine(): Promise<boolean> {
  try {
    const res = await fetch(`${config.engineUrl}/api/engine/health`, {
      signal: AbortSignal.timeout(CHECK_TIMEOUT_MS),
    })
    return res.ok
  } catch {
    return false
  }
}

/** Shared by GET /api/health and the watchdog job (notifications/systemWatchdog.ts)
 * so both agree on exactly what "healthy" means. */
export async function checkSystemHealth(): Promise<SystemHealth> {
  const [database, engine] = await Promise.all([checkDatabase(), checkEngine()])
  return { database, engine }
}

export function isHealthy(health: SystemHealth): boolean {
  return health.database && health.engine
}
