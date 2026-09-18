/**
 * Periodic digest (CDC "notifications régulières", 2026-09-17) -- daily by
 * default (config.digestIntervalMs). Purely informational: summarizes the
 * two live-broker gate conditions (paper trading history + backtest
 * evidence) so progress is visible without opening the app or reading
 * Overview. Never decides anything -- same read-only spirit as
 * app/backtest/evidence.py itself.
 */
import { render } from '@react-email/render'
import { config } from '../config.js'
import { db } from '../db.js'
import { DigestEmail } from './emails/DigestEmail.js'
import { sendMail } from './mailer.js'

const FETCH_TIMEOUT_MS = 15_000

interface PaperPerformanceResponse {
  num_open_positions: number
  num_closed_trades: number
  total_return: number | null
  win_rate: number | null
}

interface BacktestEvidenceResponse {
  total_rows: number
  distinct_days: number
  latest_pairs: number
  last_run_at: string | null
  pipeline_beats_ichimoku_sharpe: { beats: number; compared: number } | null
}

async function fetchEngineJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${config.engineUrl}${path}`, { signal: AbortSignal.timeout(FETCH_TIMEOUT_MS) })
    if (!res.ok) return null
    return (await res.json()) as T
  } catch {
    return null
  }
}

let timer: NodeJS.Timeout | null = null

async function runDigestCycle(): Promise<void> {
  const generatedAt = new Date().toLocaleString('fr-FR', { timeZone: 'Europe/Paris' })

  const [paperRaw, evidenceRaw] = await Promise.all([
    fetchEngineJson<PaperPerformanceResponse>('/api/engine/paper/performance?source=auto_watchlist'),
    fetchEngineJson<BacktestEvidenceResponse>('/api/engine/backtest/evidence'),
  ])

  const paper = paperRaw && {
    numOpenPositions: paperRaw.num_open_positions,
    numClosedTrades: paperRaw.num_closed_trades,
    totalReturn: paperRaw.total_return,
    winRate: paperRaw.win_rate,
  }
  const evidence = evidenceRaw && {
    totalRows: evidenceRaw.total_rows,
    distinctDays: evidenceRaw.distinct_days,
    latestPairs: evidenceRaw.latest_pairs,
    lastRunAt: evidenceRaw.last_run_at,
    pipelineBeatsIchimokuSharpe: evidenceRaw.pipeline_beats_ichimoku_sharpe,
  }

  const appUrl = config.engineUrl.replace(':8000', '')
  const edgeSummary = evidence?.pipelineBeatsIchimokuSharpe
    ? `${evidence.pipelineBeatsIchimokuSharpe.beats}/${evidence.pipelineBeatsIchimokuSharpe.compared}`
    : 'pas encore comparable'

  const users = await db.user.findMany({ select: { id: true } })
  await Promise.all(
    users.map((u) =>
      db.notification.create({
        data: {
          userId: u.id,
          kind: 'system_digest',
          title: 'Résumé quotidien',
          body: `Paper : ${paper?.numOpenPositions ?? '—'} ouvertes. Edge PIPELINE vs Ichimoku : ${edgeSummary}.`,
        },
      }),
    ),
  )

  if (config.alertEmailTo) {
    const html = await render(DigestEmail({ appUrl, generatedAt, paper, evidence }))
    await sendMail({ to: config.alertEmailTo, subject: 'IchiVol — résumé quotidien', html })
  }
}

export function startDigestJob(): void {
  if (timer) return
  timer = setInterval(() => void runDigestCycle(), config.digestIntervalMs)
}

export function stopDigestJob(): void {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}
