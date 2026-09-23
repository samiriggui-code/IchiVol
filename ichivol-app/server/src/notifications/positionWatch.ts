/**
 * T0-NOTIF — separate position watcher (does NOT modify journal watch.ts).
 *
 * Informative alerts only — NEVER opens/closes paper positions.
 * Interval ~60s. Uses engine marks/proximity + decisions batch.
 */

import { config } from '../config.js'
import { db } from '../db.js'
import { createNotification } from './create.js'
import { parsePushAlertPrefs, type PushAlertPrefs } from './pushPrefs.js'
import { sendPushToUser } from './push.js'
import { shouldEmitAlert } from './positionWatchDedup.js'
import { fetchEngineDecisionsBatch, type EngineDecisionBody } from './watch.js'

export { shouldEmitAlert } from './positionWatchDedup.js'


const POSITION_WATCH_INTERVAL_MS = 60_000
const FETCH_TIMEOUT_MS = 45_000

export type PositionAlertKind =
  | 'position_target_near'
  | 'position_stop_near'
  | 'position_accel'
  | 'position_direction_flip'

type EnginePosition = {
  id: string
  symbol: string
  timeframe: string
  direction: string
  status: string
  user_id: string | null
  entry_price: number
  stop_price: number | null
  take_profit_price: number | null
}

type ProximitySide = {
  remaining_frac: number | null
  near: boolean
  band: string | null
  near_threshold: number
  level: number
}

type ProximityPayload = {
  proximity?: {
    target?: ProximitySide
    stop?: ProximitySide
    mark?: number
    entry?: number
  }
  mark_source?: string
}

/** Pure dedup: fire if no prior, or cooldown expired, or band tightened / state changed. */
// shouldEmitAlert imported from ./positionWatchDedup.js

function bandFromPayload(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') return null
  const b = (payload as Record<string, unknown>).band
  return typeof b === 'string' ? b : null
}

function stateKeyFromPayload(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') return null
  const s = (payload as Record<string, unknown>).stateKey
  return typeof s === 'string' ? s : null
}

async function lastAlert(
  userId: string,
  kind: PositionAlertKind,
  positionId: string,
) {
  const row = await db.notification.findFirst({
    where: {
      userId,
      kind,
      payload: { path: ['positionId'], equals: positionId },
    },
    orderBy: { createdAt: 'desc' },
  })
  if (!row) return null
  return {
    createdAt: row.createdAt,
    band: bandFromPayload(row.payload),
    stateKey: stateKeyFromPayload(row.payload),
  }
}

async function emit(
  userId: string,
  kind: PositionAlertKind,
  title: string,
  body: string,
  payload: Record<string, unknown>,
  prefs: PushAlertPrefs,
): Promise<boolean> {
  const positionId = String(payload.positionId ?? '')
  const band = typeof payload.band === 'string' ? payload.band : null
  const stateKey = typeof payload.stateKey === 'string' ? payload.stateKey : null
  const prior = await lastAlert(userId, kind, positionId)
  if (
    !shouldEmitAlert({
      last: prior,
      now: new Date(),
      cooldownMin: prefs.cooldownMin,
      band,
      stateKey,
    })
  ) {
    return false
  }

  await createNotification({ userId, kind, title, body, payload })

  const symbol = typeof payload.symbol === 'string' ? payload.symbol : ''
  const interval = typeof payload.interval === 'string' ? payload.interval : '1h'
  const url = `${config.appUrl}/app/paper?symbol=${encodeURIComponent(symbol)}&position=${encodeURIComponent(positionId)}&interval=${encodeURIComponent(interval)}`
  // Push is best-effort — in-app row already exists.
  await sendPushToUser(userId, {
    title,
    body,
    url,
    tag: `${kind}:${positionId}`,
    data: { kind, positionId, symbol, interval },
  }).catch(() => false)
  return true
}

async function fetchOpenPositions(): Promise<EnginePosition[]> {
  const url = `${config.engineUrl}/api/engine/paper/positions?status=OPEN&source=user_confirmed`
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(FETCH_TIMEOUT_MS) })
    if (!res.ok) return []
    const body = (await res.json()) as { positions?: EnginePosition[] }
    return (body.positions ?? []).filter(
      (p) => p.status === 'OPEN' && typeof p.user_id === 'string' && p.user_id.length > 0,
    )
  } catch {
    return []
  }
}

async function fetchProximity(
  positionId: string,
  nearPct: number,
): Promise<ProximityPayload | null> {
  const url = `${config.engineUrl}/api/engine/paper/positions/${encodeURIComponent(positionId)}/proximity?near_pct=${nearPct}`
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(FETCH_TIMEOUT_MS) })
    if (!res.ok) return null
    return (await res.json()) as ProximityPayload
  } catch {
    return null
  }
}

function ichimokuDirection(detail: EngineDecisionBody | null): string | null {
  if (!detail) return null
  const raw = detail as Record<string, unknown>
  const ichi = raw.ichimoku
  if (ichi && typeof ichi === 'object') {
    const d = (ichi as { direction?: unknown }).direction
    if (typeof d === 'string' && d) return d
  }
  const pipe = detail.pipeline as { direction?: string } | undefined
  if (pipe && typeof pipe.direction === 'string' && pipe.direction) return pipe.direction
  return null
}

function rvolValue(detail: EngineDecisionBody | null): number | null {
  if (!detail) return null
  const raw = detail as Record<string, unknown>
  if (typeof raw.rvol === 'number' && Number.isFinite(raw.rvol)) return raw.rvol
  const rd = raw.rvol_detail as { metadata?: { rvol?: unknown } } | undefined
  const v = rd?.metadata?.rvol
  return typeof v === 'number' && Number.isFinite(v) ? v : null
}

function structureCodes(detail: EngineDecisionBody | null): string[] {
  const stages = detail?.pipeline?.stages ?? []
  for (const s of stages) {
    if ((s as { id?: string }).id === 'structure') {
      const codes = (s as { codes?: unknown }).codes
      if (Array.isArray(codes)) return codes.filter((c): c is string => typeof c === 'string')
    }
  }
  return []
}

function bosConfirms(detail: EngineDecisionBody | null): boolean {
  return structureCodes(detail).includes('bos_confirms_direction')
}

function positionAlignedWithIchi(direction: string, ichi: string | null): boolean {
  if (!ichi || ichi === 'NEUTRAL') return false
  if (direction === 'LONG') return ichi === 'LONG'
  if (direction === 'SHORT') return ichi === 'SHORT'
  return false
}

function directionOpposed(direction: string, ichi: string | null): boolean {
  if (!ichi || ichi === 'NEUTRAL') return false
  if (direction === 'LONG') return ichi === 'SHORT'
  if (direction === 'SHORT') return ichi === 'LONG'
  return false
}

async function prefsForUser(userId: string): Promise<PushAlertPrefs> {
  const row = await db.setting.findUnique({ where: { userId } })
  return parsePushAlertPrefs(row?.pushAlertPrefs ?? null)
}

export async function runPositionWatchTick(): Promise<{ checked: number; emitted: number }> {
  const positions = await fetchOpenPositions()
  if (positions.length === 0) return { checked: 0, emitted: 0 }

  // Prefs cache
  const prefsByUser = new Map<string, PushAlertPrefs>()
  async function prefs(uid: string) {
    let p = prefsByUser.get(uid)
    if (!p) {
      p = await prefsForUser(uid)
      prefsByUser.set(uid, p)
    }
    return p
  }

  // Batch decisions for accel / flip
  const items = positions.map((p) => ({
    symbol: p.symbol,
    timeframe: p.timeframe || '1h',
  }))
  const decisions = await fetchEngineDecisionsBatch(items)

  let emitted = 0
  for (let i = 0; i < positions.length; i++) {
    const pos = positions[i]!
    const userId = pos.user_id as string
    const p = await prefs(userId)
    if (!p.enabled) continue

    const detail = decisions[i] ?? null
    const interval = pos.timeframe || '1h'

    // --- target / stop proximity (engine geometry) ---
    if (p.targetStop) {
      const proxBody = await fetchProximity(pos.id, p.nearPct)
      const prox = proxBody?.proximity
      if (prox?.target?.near && prox.target.band) {
        const rem = prox.target.remaining_frac
        const remPct = rem != null ? `${(rem * 100).toFixed(1)} %` : '?'
        if (
          await emit(
          userId,
          'position_target_near',
          `${pos.symbol} — objectif proche`,
          `Reste ${remPct} de la distance vers l’objectif (${prox.target.level}). Mark ${prox.mark ?? '?'}. Alerte informative — aucun ordre.`,
          {
            positionId: pos.id,
            symbol: pos.symbol,
            interval,
            band: prox.target.band,
            remainingFrac: rem,
            level: prox.target.level,
            mark: prox.mark,
            entry: prox.entry,
            kindDetail: 'target',
          },
          p,
        )
        ) {
          emitted += 1
        }
      }
      if (prox?.stop?.near && prox.stop.band) {
        const rem = prox.stop.remaining_frac
        const remPct = rem != null ? `${(rem * 100).toFixed(1)} %` : '?'
        if (
          await emit(
          userId,
          'position_stop_near',
          `${pos.symbol} — stop proche`,
          `Reste ${remPct} de la distance vers le stop (${prox.stop.level}). Mark ${prox.mark ?? '?'}. Alerte informative — aucun ordre.`,
          {
            positionId: pos.id,
            symbol: pos.symbol,
            interval,
            band: prox.stop.band,
            remainingFrac: rem,
            level: prox.stop.level,
            mark: prox.mark,
            entry: prox.entry,
            kindDetail: 'stop',
          },
          p,
        )
        ) {
          emitted += 1
        }
      }
    }

    // --- accel: RVOL + BOS confirms from engine ---
    if (p.accel && detail) {
      const setting = await db.setting.findUnique({ where: { userId } })
      const vol = (setting?.volumeParams ?? {}) as Record<string, unknown>
      const rvolMin =
        typeof vol.rvolConfirm === 'number' && vol.rvolConfirm > 0
          ? vol.rvolConfirm
          : 1.5
      const rvol = rvolValue(detail)
      const bos = bosConfirms(detail)
      const ichi = ichimokuDirection(detail)
      if (
        rvol != null &&
        rvol >= rvolMin &&
        bos &&
        positionAlignedWithIchi(pos.direction, ichi)
      ) {
        const stateKey = `accel:${rvolMin}:${bos ? 1 : 0}`
        if (
          await emit(
          userId,
          'position_accel',
          `${pos.symbol} — accélération confirmée`,
          `RVOL ${rvol.toFixed(2)}× (≥ ${rvolMin}) + BOS confirme la direction ${pos.direction}. Lecture moteur — aucun ordre.`,
          {
            positionId: pos.id,
            symbol: pos.symbol,
            interval,
            rvol,
            rvolMin,
            bos: true,
            ichimokuDirection: ichi,
            stateKey,
          },
          p,
        )
        ) {
          emitted += 1
        }
      }
    }

    // --- direction flip ---
    if (p.directionFlip && detail) {
      const ichi = ichimokuDirection(detail)
      if (directionOpposed(pos.direction, ichi)) {
        const stateKey = `flip:${pos.direction}->${ichi}`
        if (
          await emit(
          userId,
          'position_direction_flip',
          `${pos.symbol} — direction opposée`,
          `Ichimoku ${ichi} alors que la position est ${pos.direction}. Alerte informative — aucun ordre.`,
          {
            positionId: pos.id,
            symbol: pos.symbol,
            interval,
            positionDirection: pos.direction,
            ichimokuDirection: ichi,
            stateKey,
          },
          p,
        )
        ) {
          emitted += 1
        }
      }
    }
  }

  return { checked: positions.length, emitted }
}

let started = false

export function startPositionWatchJob(): void {
  if (started) return
  started = true
  const tick = () => {
    void runPositionWatchTick().catch((err) => {
      console.error(
        '[positionWatch] tick failed:',
        err instanceof Error ? err.message : err,
      )
    })
  }
  setTimeout(tick, 70_000)
  setInterval(tick, POSITION_WATCH_INTERVAL_MS)
  console.log(
    `[positionWatch] started (interval ${POSITION_WATCH_INTERVAL_MS / 1000}s) — informative only`,
  )
}
