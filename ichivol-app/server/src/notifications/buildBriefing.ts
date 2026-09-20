/**
 * Assembles a desk-style daily briefing from engine read-only APIs.
 * Never decides trades — informational only.
 */
import { config } from '../config.js'
import type {
  BriefingActivityItem,
  BriefingCircuit,
  BriefingEvidence,
  BriefingKpis,
  BriefingPosition,
  BriefingShadow,
  BriefingTone,
  DailyBriefing,
} from './briefingTypes.js'

const FETCH_TIMEOUT_MS = 15_000
const PORTFOLIO = 'ICHIVOL_BASELINE_V1'

async function fetchEngineJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${config.engineUrl}${path}`, {
      signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
    })
    if (!res.ok) return null
    return (await res.json()) as T
  } catch {
    return null
  }
}

function eur(n: number | null | undefined, digits = 2): string {
  if (n == null || !Number.isFinite(n)) return '—'
  return n.toLocaleString('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: digits,
  })
}

function pct(n: number | null | undefined, digits = 1): string {
  if (n == null || !Number.isFinite(n)) return '—'
  const sign = n > 0 ? '+' : ''
  return `${sign}${(n * 100).toFixed(digits)} %`
}

function assetLabel(symbol: string): string {
  const s = symbol.replace(/USDT$/i, '').replace(/USD$/i, '')
  return s || symbol
}

function shadowPlain(verdict: string | null, nClosed: number, meanR: number | null): string {
  if (nClosed < 5) {
    return 'Échantillon encore mince (< 5 cas fermés) — ne pas juger les filtres trop tôt.'
  }
  if (verdict === 'filter_too_aggressive') {
    return 'Les filtres ont souvent bloqué des trades qui auraient gagné — trop stricts pour l’instant.'
  }
  if (verdict === 'filter_helpful') {
    return 'Les filtres ont surtout écarté des trades perdants — utiles sur la période observée.'
  }
  const r = meanR != null ? ` (mean R ${meanR.toFixed(2)})` : ''
  return `Verdict mitigé sur les filtres${r} — ni clairement utiles ni clairement trop durs.`
}

function buildHeadline(k: BriefingKpis, circuit: BriefingCircuit | null): string {
  const day =
    k.dayChange == null
      ? 'variation 24 h indisponible'
      : `${k.dayChange >= 0 ? '+' : ''}${eur(k.dayChange)} sur 24 h`
  const book =
    k.openPositions === 0
      ? 'livre vide'
      : `${k.openPositions} position${k.openPositions > 1 ? 's' : ''} ouverte${k.openPositions > 1 ? 's' : ''}`
  const tape =
    circuit == null
      ? ''
      : ` · circuit 24 h : ${circuit.opened24h} ouverture${circuit.opened24h > 1 ? 's' : ''}, ${circuit.closed24h} clôture${circuit.closed24h > 1 ? 's' : ''}, ${circuit.blocked24h} refus`
  return `Equity ${eur(k.equity)} (${day}) — ${book}${tape}.`
}

function buildNarrative(
  k: BriefingKpis,
  openBook: BriefingPosition[],
  shadow: BriefingShadow | null,
  evidence: BriefingEvidence | null,
  circuit: BriefingCircuit | null,
): string[] {
  const lines: string[] = []

  const vsInitial = k.totalPnl
  if (vsInitial >= 0) {
    lines.push(
      `Depuis le départ (${eur(k.initialCash, 0)}), le compte est à ${eur(k.equity)} soit ${eur(vsInitial)} (${pct(k.totalPnlPct)}). Cash libre ${eur(k.cash)}, capital engagé ${eur(k.invested)}.`,
    )
  } else {
    lines.push(
      `Depuis le départ (${eur(k.initialCash, 0)}), le compte est à ${eur(k.equity)} soit ${eur(vsInitial)} (${pct(k.totalPnlPct)}). Priorité : discipline de risque, pas de rattrapage. Cash ${eur(k.cash)} · engagé ${eur(k.invested)}.`,
    )
  }

  if (openBook.length > 0) {
    const winners = openBook.filter((p) => (p.unrealizedPnl ?? 0) > 0).length
    const losers = openBook.filter((p) => (p.unrealizedPnl ?? 0) < 0).length
    const top = [...openBook].sort(
      (a, b) => Math.abs(b.unrealizedPnl ?? 0) - Math.abs(a.unrealizedPnl ?? 0),
    )[0]
    lines.push(
      `Livre ouvert : ${winners} dans le vert, ${losers} dans le rouge. Plus fort contributeur latent : ${top.label} (${eur(top.unrealizedPnl)}). Latent total ${eur(k.unrealizedPnl)} · réalisé ${eur(k.realizedPnl)}.`,
    )
  } else {
    lines.push(
      `Aucune position ouverte — le capital est en cash. Le circuit peut rouvrir dès qu’un setup passe les portes.`,
    )
  }

  if (circuit) {
    lines.push(
      `Activité des dernières 24 h : ${circuit.decisions24h} décisions moteur, ${circuit.opened24h} entrées paper, ${circuit.closed24h} sorties, ${circuit.blocked24h} setups refusés par les filtres.`,
    )
  }

  if (shadow) {
    lines.push(`Filtres (ShadowBroker) : ${shadow.plain}`)
  }

  if (evidence) {
    lines.push(
      `Preuve edge : ${evidence.edgePlain} Sur ${evidence.distinctDays} j de collecte (${evidence.totalRows} snapshots).`,
    )
  }

  lines.push(
    `Ce briefing est informatif — aucune exécution réelle. Relire Synthèse et Activité dans l’app pour le détail live.`,
  )

  return lines
}

interface OverviewRaw {
  portfolio: { code: string; label: string }
  account: {
    initial_cash: number
    cash: number
    invested: number
    unrealized_pnl: number
    realized_pnl: number
    equity: number
    total_pnl: number
    day_change: number | null
    priced_positions: number
    open_positions: number
  }
  positions: Array<{
    symbol: string
    direction: string
    timeframe: string
    status: string
    notional: number | null
    unrealized_pnl: number | null
    unrealized_pct: number | null
    entry_price: number | null
    current_price: number | null
  }>
  equity_curve: Array<{ t: string; equity: number }>
}

interface ActivityFeedRaw {
  items: Array<{
    time: string
    title?: string
    headline?: string
    detail?: string
    body?: string
    kind?: string
    tone?: string
  }>
}

interface ShadowRaw {
  n_closed: number
  mean_pnl_r: number | null
  filter_verdict: string | null
}

interface EvidenceRaw {
  total_rows: number
  distinct_days: number
  latest_pairs: number
  last_run_at: string | null
  pipeline_beats_ichimoku_sharpe: { beats: number; compared: number } | null
}

interface SummaryRaw {
  decisions: { last_24h: number }
  paper: { opened_24h: number; closed_24h: number; open_now: number }
  shadow: { blocked_24h: number }
}

interface PerfRaw {
  num_closed_trades: number
  total_return: number | null
  win_rate: number | null
}

function mapTone(raw: string | undefined): BriefingTone {
  if (raw === 'up' || raw === 'bull' || raw === 'green' || raw === 'good') return 'green'
  if (raw === 'down' || raw === 'bear' || raw === 'red' || raw === 'bad' || raw === 'blocked') return 'red'
  return 'flat'
}

function mapTape(items: ActivityFeedRaw['items']): BriefingActivityItem[] {
  const dayAgo = Date.now() - 24 * 60 * 60 * 1000
  return items
    .filter((it) => {
      const t = Date.parse(it.time)
      return Number.isFinite(t) && t >= dayAgo
    })
    .slice(0, 12)
    .map((it) => ({
      time: it.time,
      title: it.title ?? it.headline ?? it.kind ?? 'Événement',
      detail: it.detail ?? it.body ?? '',
      tone: mapTone(it.tone),
    }))
}

export async function buildDailyBriefing(): Promise<DailyBriefing> {
  const generatedAtIso = new Date().toISOString()
  const generatedAt = new Date().toLocaleString('fr-FR', {
    timeZone: 'Europe/Paris',
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })

  const appUrl = config.appUrl.replace(/\/$/, '')

  const [overview, feed, shadowRaw, evidenceRaw, summaryRaw, perfRaw] = await Promise.all([
    fetchEngineJson<OverviewRaw>(`/api/engine/paper/portfolios/${PORTFOLIO}/overview`),
    fetchEngineJson<ActivityFeedRaw>('/api/engine/activity/feed?limit=80'),
    fetchEngineJson<ShadowRaw>('/api/engine/shadow/stats'),
    fetchEngineJson<EvidenceRaw>('/api/engine/backtest/evidence'),
    fetchEngineJson<SummaryRaw>('/api/engine/activity/summary'),
    fetchEngineJson<PerfRaw>('/api/engine/paper/performance?source=auto_watchlist'),
  ])

  const a = overview?.account
  const kpis: BriefingKpis = {
    equity: a?.equity ?? 0,
    initialCash: a?.initial_cash ?? 0,
    cash: a?.cash ?? 0,
    invested: a?.invested ?? 0,
    totalPnl: a?.total_pnl ?? 0,
    totalPnlPct: a && a.initial_cash ? a.total_pnl / a.initial_cash : null,
    dayChange: a?.day_change ?? null,
    dayChangePct:
      a?.day_change != null && a.equity
        ? a.day_change / Math.max(1e-9, a.equity - a.day_change)
        : null,
    unrealizedPnl: a?.unrealized_pnl ?? 0,
    realizedPnl: a?.realized_pnl ?? 0,
    openPositions: a?.open_positions ?? 0,
    pricedPositions: a?.priced_positions ?? 0,
  }

  const openBook: BriefingPosition[] = (overview?.positions ?? [])
    .filter((p) => p.status === 'OPEN')
    .map((p) => ({
      symbol: p.symbol,
      label: assetLabel(p.symbol),
      direction: p.direction,
      timeframe: p.timeframe,
      notional: Math.abs(p.notional ?? 0),
      unrealizedPnl: p.unrealized_pnl,
      unrealizedPct: p.unrealized_pct,
      entryPrice: p.entry_price,
      currentPrice: p.current_price,
    }))
    .sort((x, y) => y.notional - x.notional)

  const equityCurve = overview?.equity_curve ?? []
  const sparkSrc = equityCurve.length > 0 ? equityCurve : []
  const step = Math.max(1, Math.floor(sparkSrc.length / 28))
  const equitySpark = sparkSrc.filter((_, i) => i % step === 0 || i === sparkSrc.length - 1).map((p) => p.equity)

  const circuit: BriefingCircuit | null = summaryRaw
    ? {
        decisions24h: summaryRaw.decisions.last_24h,
        opened24h: summaryRaw.paper.opened_24h,
        closed24h: summaryRaw.paper.closed_24h,
        blocked24h: summaryRaw.shadow.blocked_24h,
        openNow: summaryRaw.paper.open_now,
      }
    : null

  const edge = evidenceRaw?.pipeline_beats_ichimoku_sharpe
  const evidence: BriefingEvidence | null = evidenceRaw
    ? {
        totalRows: evidenceRaw.total_rows,
        distinctDays: evidenceRaw.distinct_days,
        latestPairs: evidenceRaw.latest_pairs,
        lastRunAt: evidenceRaw.last_run_at,
        pipelineBeats: edge?.beats ?? 0,
        pipelineCompared: edge?.compared ?? 0,
        edgePlain:
          edge && edge.compared > 0
            ? `PIPELINE bat Ichimoku (Sharpe) sur ${edge.beats}/${edge.compared} paires comparables.`
            : 'Pas encore assez de paires comparables PIPELINE vs Ichimoku.',
      }
    : null

  const shadow: BriefingShadow | null = shadowRaw
    ? {
        nClosed: shadowRaw.n_closed,
        meanPnlR: shadowRaw.mean_pnl_r,
        filterVerdict: shadowRaw.filter_verdict,
        plain: shadowPlain(shadowRaw.filter_verdict, shadowRaw.n_closed, shadowRaw.mean_pnl_r),
      }
    : null

  const tape = mapTape(feed?.items ?? [])

  return {
    portfolioCode: overview?.portfolio.code ?? PORTFOLIO,
    portfolioLabel: overview?.portfolio.label ?? 'Baseline V1',
    generatedAt,
    generatedAtIso,
    appUrl,
    headline: buildHeadline(kpis, circuit),
    narrative: buildNarrative(kpis, openBook, shadow, evidence, circuit),
    kpis,
    equityCurve,
    equitySpark,
    openBook,
    tape,
    shadow,
    evidence,
    circuit,
    paperStats: perfRaw
      ? {
          closedTrades: perfRaw.num_closed_trades,
          winRate: perfRaw.win_rate,
          totalReturn: perfRaw.total_return,
        }
      : null,
  }
}

export { eur, pct, assetLabel }
