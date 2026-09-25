/**
 * Chantier 2 E0 — poke endpoint (Comp AI AGENT_BRIDGE_SECRET principle).
 * POST /api/agent/runtime/poke — Bearer secret → reconcile + drain due tasks.
 */
import { timingSafeEqual } from 'node:crypto'
import type { Request, Response } from 'express'
import { config } from '../config.js'
import { runDispatcherTick } from './runtime/dispatcher.js'

function authorised(req: Request): boolean {
  const secret = config.agentBridgeSecret
  if (!secret) return false
  const header = req.headers.authorization
  if (!header?.startsWith('Bearer ')) return false
  const candidate = Buffer.from(header.slice('Bearer '.length))
  const expected = Buffer.from(secret)
  if (candidate.length !== expected.length) return false
  return timingSafeEqual(candidate, expected)
}

/**
 * Immediate drain poke. Cron minute worker remains the safety net when poke misses.
 */
export async function handleAgentRuntimePoke(req: Request, res: Response): Promise<void> {
  if (!config.agentBridgeSecret) {
    res.status(503).json({
      error: 'AGENT_BRIDGE_SECRET unset — poke disabled (worker minute still runs if started)',
    })
    return
  }
  if (!authorised(req)) {
    res.status(401).json({ error: 'Unauthorized' })
    return
  }

  try {
    const summary = await runDispatcherTick()
    if (summary === null) {
      res.status(202).json({ ok: true, deferred: true, reason: 'drain_in_progress' })
      return
    }
    res.status(200).json({ ok: true, ...summary })
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    console.error('[agent-runtime] poke failed:', message)
    res.status(500).json({ error: message })
  }
}
