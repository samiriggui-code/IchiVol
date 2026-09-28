/**
 * AG-S1 — planifie AgentTask analyst_snapshot à l'ouverture de session +60 s.
 * Observe-only · aucun LLM · jamais /screener.
 */
import { config } from '../config.js'
import { writeAgentLog } from './agentLog.js'
import { CANDLE_GRACE_MS, deferOneBar } from './candleDue.js'
import { AGENT_LOG_LEVEL } from './taskConfig.js'
import { checkSymbolFreshness } from './runtime/dataQualityGate.js'
import {
  completeTask,
  deferTask,
  scheduleTask,
  type LeasedTask,
} from './tasks.js'

export const SESSION_AGENT_ID = 'session'
export const ANALYST_SNAPSHOT_KIND = 'analyst_snapshot'

const SNAPSHOT_SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'] as const
const SNAPSHOT_TIMEFRAMES = ['1h', '4h'] as const

type SessionOpen = {
  key: string
  session_id: string
  open_utc: string
  label?: string
}

type SessionsPayload = {
  next_open?: SessionOpen | null
  open_sessions?: SessionOpen[]
  sessions?: SessionOpen[]
  upcoming_opens?: SessionOpen[]
}

async function fetchEngineSessions(): Promise<SessionsPayload | null> {
  try {
    const res = await fetch(`${config.engineUrl}/api/engine/sessions`, {
      signal: AbortSignal.timeout(4_000),
    })
    if (!res.ok) return null
    return (await res.json()) as SessionsPayload
  } catch {
    return null
  }
}

/** Due = ouverture session + 60 s (même grâce que candleDue). */
export function sessionSnapshotDueAt(openUtcIso: string): Date {
  const openMs = Date.parse(openUtcIso)
  return new Date(openMs + CANDLE_GRACE_MS)
}

export function snapshotIdempotencyKey(
  sessionId: string,
  symbol: string,
  timeframe: string,
): string {
  return `analyst_snapshot:${sessionId}:${symbol}:${timeframe}`
}

/**
 * Planifie les tâches manquantes pour les ouvertures dans les ~48 h
 * (next_open + sessions du jour si encore à venir).
 */
export async function ensureSessionSnapshotTasks(
  now: Date = new Date(),
): Promise<{ scheduled: number; reused: number }> {
  const payload = await fetchEngineSessions()
  if (!payload) return { scheduled: 0, reused: 0 }

  const opens: SessionOpen[] = []
  if (payload.next_open) opens.push(payload.next_open)
  for (const s of payload.upcoming_opens ?? []) {
    if (s?.session_id && s?.open_utc) opens.push(s)
  }
  for (const s of payload.open_sessions ?? []) {
    if (s?.session_id && s?.open_utc) opens.push(s)
  }
  for (const s of payload.sessions ?? []) {
    if (s?.session_id && s?.open_utc) opens.push(s)
  }

  const seen = new Set<string>()
  let scheduled = 0
  let reused = 0

  for (const open of opens) {
    if (!open.session_id || !open.open_utc) continue
    const dueAt = sessionSnapshotDueAt(open.open_utc)
    // Ignore ouvertures trop anciennes (> 6 h) ou trop lointaines (> 48 h).
    const horizon = now.getTime() + 48 * 3600_000
    const floor = now.getTime() - 6 * 3600_000
    if (dueAt.getTime() < floor || dueAt.getTime() > horizon) continue

    for (const symbol of SNAPSHOT_SYMBOLS) {
      for (const timeframe of SNAPSHOT_TIMEFRAMES) {
        const key = snapshotIdempotencyKey(open.session_id, symbol, timeframe)
        if (seen.has(key)) continue
        seen.add(key)
        const result = await scheduleTask({
          agentId: SESSION_AGENT_ID,
          kind: ANALYST_SNAPSHOT_KIND,
          symbol,
          dueAt,
          idempotencyKey: key,
          payload: {
            session_id: open.session_id,
            symbol,
            timeframe,
            session_key: open.key,
            open_utc: open.open_utc,
            observe_only: true,
            used_by_decision: false,
          },
        })
        if (result.created) scheduled += 1
        else reused += 1
      }
    }
  }

  return { scheduled, reused }
}

export async function processAnalystSnapshotTask(
  task: LeasedTask,
): Promise<
  | { action: 'completed'; detail: string }
  | { action: 'deferred'; reason: string; dueAt: string }
  | { action: 'failed'; error: string }
> {
  const payload =
    task.payload && typeof task.payload === 'object' && !Array.isArray(task.payload)
      ? (task.payload as Record<string, unknown>)
      : {}
  const sessionId = typeof payload.session_id === 'string' ? payload.session_id : null
  const timeframe =
    typeof payload.timeframe === 'string' && payload.timeframe.trim()
      ? payload.timeframe.trim()
      : '1h'
  const symbol = task.symbol?.trim().toUpperCase() ?? null

  if (!sessionId || !symbol) {
    return { action: 'failed', error: 'missing_session_id_or_symbol' }
  }

  const fresh = await checkSymbolFreshness(symbol, timeframe)
  if (!fresh.ok && (fresh.reason === 'stale' || fresh.reason === 'data_late')) {
    const dueAt = deferOneBar(timeframe)
    await deferTask(task.id, dueAt, fresh.reason)
    await writeAgentLog({
      agentId: task.agentId,
      level: AGENT_LOG_LEVEL.prudence,
      source: 'runtime.sessionSnapshots',
      message: `Analyst snapshot deferred — ${fresh.reason}; ${symbol} ${timeframe}`,
      taskId: task.id,
      meta: {
        reason: fresh.reason,
        dueAt: dueAt.toISOString(),
        wakeLlm: false,
        observe_only: true,
      },
    })
    return { action: 'deferred', reason: fresh.reason, dueAt: dueAt.toISOString() }
  }
  if (!fresh.ok && fresh.reason === 'engine_error') {
    const dueAt = deferOneBar(timeframe)
    await deferTask(task.id, dueAt, `engine_error:${fresh.detail ?? ''}`)
    await writeAgentLog({
      agentId: task.agentId,
      level: AGENT_LOG_LEVEL.prudence,
      source: 'runtime.sessionSnapshots',
      message: `Analyst snapshot deferred — engine_error; ${symbol}`,
      taskId: task.id,
      meta: { reason: 'engine_error', detail: fresh.detail, wakeLlm: false },
    })
    return { action: 'deferred', reason: 'engine_error', dueAt: dueAt.toISOString() }
  }

  try {
    const res = await fetch(`${config.engineUrl}/api/engine/agents/analyst-snapshots`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        symbol,
        timeframe,
      }),
      signal: AbortSignal.timeout(60_000),
    })
    if (!res.ok) {
      const text = await res.text().catch(() => '')
      return {
        action: 'failed',
        error: `engine_snapshot_http_${res.status}:${text.slice(0, 200)}`,
      }
    }
    const data = (await res.json()) as {
      created?: boolean
      snapshot?: { id?: string; as_of?: number }
    }
    await completeTask(task.id, {
      phase: 'AG-S1',
      wakeLlm: false,
      observe_only: true,
      used_by_decision: false,
      created: data.created === true,
      snapshotId: data.snapshot?.id ?? null,
      asOf: data.snapshot?.as_of ?? null,
      processedAt: new Date().toISOString(),
    })
    await writeAgentLog({
      agentId: task.agentId,
      level: AGENT_LOG_LEVEL.passe,
      source: 'runtime.sessionSnapshots',
      message: `Analyst snapshot ${data.created ? 'écrit' : 'réutilisé'} ${symbol} ${timeframe} · ${sessionId}`,
      taskId: task.id,
      meta: { wakeLlm: false, created: data.created === true },
    })
    return {
      action: 'completed',
      detail: data.created ? 'snapshot_created' : 'snapshot_reused',
    }
  } catch (err) {
    return {
      action: 'failed',
      error: err instanceof Error ? err.message : String(err),
    }
  }
}
