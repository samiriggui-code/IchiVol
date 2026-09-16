import { config } from '../config.js'
import { db } from '../db.js'
import { createNotification } from './create.js'

const WATCH_INTERVAL_MS = 3 * 60 * 1000
/** Batch concurrent côté engine — plus long qu’un GET unitaire. */
const FETCH_TIMEOUT_MS = 120_000
const BATCH_BASELINE = 15
const BATCH_ROTATE = 30

interface EngineStage {
  id?: string
  status?: string
}

export interface EngineDecisionBody {
  decision?: string
  pipeline?: {
    decision?: string
    stages?: EngineStage[]
  }
}

interface BatchResultItem extends EngineDecisionBody {
  ok?: boolean
  error?: string
  symbol?: string
  timeframe?: string
}

export function pipelineFingerprint(detail: EngineDecisionBody): string {
  const gate =
    (typeof detail.pipeline?.decision === 'string' && detail.pipeline.decision) ||
    (typeof detail.decision === 'string' && detail.decision) ||
    ''
  const stages = (detail.pipeline?.stages ?? [])
    .map((s) => `${s.id ?? '?'}:${s.status ?? '?'}`)
    .sort()
    .join(',')
  return `${gate}|${stages}`
}

function gateOf(detail: EngineDecisionBody, fallback: string | null): string | null {
  if (typeof detail.pipeline?.decision === 'string' && detail.pipeline.decision) {
    return detail.pipeline.decision
  }
  if (typeof detail.decision === 'string' && detail.decision) return detail.decision
  return fallback
}

function stageDiffSummary(prevFp: string, nextFp: string): string | null {
  const prevStages = new Map(
    (prevFp.split('|')[1] ?? '')
      .split(',')
      .filter(Boolean)
      .map((p) => {
        const [id, status] = p.split(':')
        return [id, status] as const
      }),
  )
  const nextParts = (nextFp.split('|')[1] ?? '').split(',').filter(Boolean)
  const changed: string[] = []
  for (const part of nextParts) {
    const [id, status] = part.split(':')
    if (!id) continue
    const before = prevStages.get(id)
    if (before && before !== status) changed.push(`${id}: ${before}→${status}`)
  }
  if (changed.length === 0) return null
  return changed.slice(0, 3).join(' · ')
}

/**
 * Un seul POST /decisions/batch (Claude SOIR2) — résultats dans l’ordre des items.
 * `persist: false` : le watch lit le pipeline, il ne réécrit pas la DB engine.
 */
export async function fetchEngineDecisionsBatch(
  items: { symbol: string; timeframe: string }[],
): Promise<(EngineDecisionBody | null)[]> {
  if (items.length === 0) return []
  const url = `${config.engineUrl}/api/engine/decisions/batch`
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        items: items.map((i) => ({ symbol: i.symbol, timeframe: i.timeframe })),
        persist: false,
      }),
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    })
    if (!res.ok) return items.map(() => null)
    const body = (await res.json()) as { results?: BatchResultItem[] }
    const results = body.results ?? []
    return items.map((_, i) => {
      const row = results[i]
      if (!row || row.ok === false) return null
      return row
    })
  } catch {
    return items.map(() => null)
  }
}

/** Priorité : jamais pollés, puis les plus anciens `watchCheckedAt` (rotation). */
async function pickConfirmedBatch() {
  const baseline = await db.decision.findMany({
    where: { status: 'confirmed', watchFingerprint: null },
    orderBy: { updatedAt: 'asc' },
    take: BATCH_BASELINE,
  })
  const rotate = await db.decision.findMany({
    where: { status: 'confirmed', watchFingerprint: { not: null } },
    orderBy: [{ watchCheckedAt: 'asc' }, { updatedAt: 'asc' }],
    take: BATCH_ROTATE,
  })
  const seen = new Set(baseline.map((r) => r.id))
  return [...baseline, ...rotate.filter((r) => !seen.has(r.id))]
}

/** Re-lit le pipeline sur les confirms ; notifie si gate/stages changent. */
export async function runJournalWatchOnce(): Promise<{ checked: number; notified: number }> {
  const confirmed = await pickConfirmedBatch()
  if (confirmed.length === 0) return { checked: 0, notified: 0 }

  const now = new Date()
  const details = await fetchEngineDecisionsBatch(
    confirmed.map((row) => ({ symbol: row.symbol, timeframe: row.interval })),
  )

  let notified = 0

  for (let i = 0; i < confirmed.length; i++) {
    const row = confirmed[i]!
    const detail = details[i] ?? null

    if (!detail) {
      await db.decision.update({
        where: { id: row.id },
        data: { watchCheckedAt: now },
      })
      continue
    }

    const fp = pipelineFingerprint(detail)
    const gate = gateOf(detail, row.gateDecision)

    if (row.watchFingerprint == null) {
      await db.decision.update({
        where: { id: row.id },
        data: {
          watchFingerprint: fp,
          gateDecision: gate ?? row.gateDecision,
          watchCheckedAt: now,
        },
      })
      continue
    }

    if (fp === row.watchFingerprint) {
      await db.decision.update({
        where: { id: row.id },
        data: { watchCheckedAt: now },
      })
      continue
    }

    const prevGate = row.gateDecision ?? '—'
    const nextGate = gate ?? '—'
    const stagesHint = stageDiffSummary(row.watchFingerprint, fp)

    await db.decision.update({
      where: { id: row.id },
      data: {
        watchFingerprint: fp,
        gateDecision: gate ?? row.gateDecision,
        watchCheckedAt: now,
      },
    })

    const bodyParts = [`${prevGate} → ${nextGate}`]
    if (stagesHint) bodyParts.push(stagesHint)
    bodyParts.push(`${row.interval}`)

    await createNotification({
      userId: row.userId,
      kind: 'pipeline_change',
      title: `${row.symbol} · portes mises à jour`,
      body: `${bodyParts.join(' · ')}. Ouvre Décisions pour revérifier.`,
      payload: {
        decisionId: row.id,
        symbol: row.symbol,
        interval: row.interval,
        prevGate,
        nextGate,
        fingerprint: fp,
        stagesHint: stagesHint ?? undefined,
        source: 'watch',
      },
    })
    notified += 1
  }

  return { checked: confirmed.length, notified }
}

let timer: ReturnType<typeof setInterval> | null = null
let running = false

export function startJournalWatchJob(): void {
  if (timer) return

  const tick = () => {
    if (running) return
    running = true
    void runJournalWatchOnce()
      .then((r) => {
        console.log(`[watch] checked=${r.checked} notified=${r.notified}`)
      })
      .catch((err: unknown) => {
        console.warn('[watch] error', err instanceof Error ? err.message : err)
      })
      .finally(() => {
        running = false
      })
  }

  // Premier passage après 45s, puis toutes les 3 min.
  setTimeout(tick, 45_000)
  timer = setInterval(tick, WATCH_INTERVAL_MS)
  console.log(`[watch] journal poll every ${WATCH_INTERVAL_MS / 1000}s (engine batch)`)
}
