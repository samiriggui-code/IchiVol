/**
 * MTF-1 — matrice de tendance multi-horizons (GET /api/engine/mtf/{symbol}).
 *
 * Aucun calcul métier ici : le moteur fournit directions, états, relations, phrase et lecture portefeuille.
 * Ce module ne fait que typer la réponse et choisir libellés / tons d'affichage.
 */

export type MtfHorizonState = 'CONFIRMED' | 'LATE' | 'STALE' | 'UNAVAILABLE'
export type MtfRelation = 'self' | 'aligned' | 'opposed' | 'neutral' | 'unknown'
export type MtfDirection = 'LONG' | 'SHORT' | 'NEUTRAL'

export interface MtfHorizon {
  timeframe: string
  role: 'decision' | 'parent' | 'context' | string
  state: MtfHorizonState
  direction: MtfDirection | null
  score: number | null
  method: string
  bar_open: number | null
  bar_close: number | null
  lag_bars: number | null
  reasons: string[]
  unavailable_reason: string | null
  provisional_direction: MtfDirection | null
  provisional_bar_open: number | null
  rvol: number | null
  rvol_level: string | null
  atr: number | null
  atr_regime: string | null
  adx: number | null
  adx_strength: string | null
  relation: MtfRelation
}

export interface MtfSummary {
  decision_tf: string
  decision_direction: MtfDirection | null
  parent_tf: string | null
  parent_relation: MtfRelation | string
  aligned: string[]
  opposed: string[]
  neutral: string[]
  unknown: string[]
  n_available: number
  n_horizons: number
}

export interface MtfMatrix {
  version: string
  symbol: string
  venue: string | null
  decision_tf: string
  computed_at: number
  method: string
  horizons: MtfHorizon[]
  summary: MtfSummary
  observe_only: boolean
  used_by_decision: boolean
}

export interface MtfPortfolioReading {
  code: string
  allow_short: boolean
  exit_mode: string | null
  auto_timeframes: string[]
  open_long_on_tf: boolean
  reading: string
}

export interface MtfResponse {
  symbol: string
  timeframe: string
  as_of: number | null
  matrix: MtfMatrix
  pipeline: { decision: string; direction: string; stages: Array<{ id: string; status: string; codes: string[] }> } | null
  pipeline_reason: string | null
  sentence: string
  portfolio: MtfPortfolioReading | null
  observe_only: boolean
}

export async function getMtf(symbol: string, timeframe = '1h', asOf?: number | null): Promise<MtfResponse> {
  const params = new URLSearchParams({ timeframe })
  if (asOf != null) params.set('as_of', String(asOf))
  const res = await fetch(`/api/engine/mtf/${encodeURIComponent(symbol)}?${params}`, { credentials: 'include' })
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = (await res.json()) as { detail?: string }
      if (body?.detail) detail = String(body.detail)
    } catch {
      /* corps non JSON */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<MtfResponse>
}

/** Tons `.tag` existants : green / red / amber / gray. */
export type Tone = 'green' | 'red' | 'amber' | 'gray'

const DIRECTION_LABEL: Record<MtfDirection, string> = { LONG: 'Haussier', SHORT: 'Baissier', NEUTRAL: 'Neutre' }
const STATE_LABEL: Record<MtfHorizonState, string> = {
  CONFIRMED: 'Confirmé',
  LATE: 'En retard',
  STALE: 'Périmé',
  UNAVAILABLE: 'Indisponible',
}
const RELATION_LABEL: Record<MtfRelation, string> = {
  self: 'Horizon de décision',
  aligned: 'Aligné',
  opposed: 'Opposé',
  neutral: 'Neutre',
  unknown: 'Inconnu',
}
const UNAVAILABLE_REASON: Record<string, string> = {
  insufficient_history: 'historique insuffisant (Ichimoku incomplet)',
  provider_no_timeframe: 'horizon non servi par la source',
  provider_credit_budget: 'non demandé (budget de crédits de la source)',
  provider_error: 'erreur de la source',
  no_data: 'aucune donnée',
  unsupported_timeframe: 'horizon non pris en charge',
}

export function directionLabel(d: MtfDirection | null): string {
  return d ? DIRECTION_LABEL[d] ?? d : '—'
}

export function directionTone(d: MtfDirection | null): Tone {
  if (d === 'LONG') return 'green'
  if (d === 'SHORT') return 'red'
  return 'gray'
}

export function stateLabel(s: MtfHorizonState): string {
  return STATE_LABEL[s] ?? s
}

export function stateTone(s: MtfHorizonState): Tone {
  if (s === 'CONFIRMED') return 'green'
  if (s === 'LATE') return 'amber'
  if (s === 'STALE') return 'red'
  return 'gray'
}

export function relationLabel(r: MtfRelation): string {
  return RELATION_LABEL[r] ?? r
}

export function unavailableReasonLabel(reason: string | null): string {
  if (!reason) return 'indisponible'
  return UNAVAILABLE_REASON[reason] ?? reason
}

/** « 21/09 14:00 UTC » — heure de clôture de bougie, toujours en UTC (pas l'heure locale). */
export function fmtUtc(ts: number | null): string {
  if (ts == null) return '—'
  const d = new Date(ts * 1000)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getUTCDate())}/${p(d.getUTCMonth() + 1)} ${p(d.getUTCHours())}:${p(d.getUTCMinutes())} UTC`
}

/** Décompte affiché à la place d'un score (aucune pondération, aucune « probabilité »). */
export function agreementCount(s: MtfSummary): string {
  const parts = [`${s.aligned.length} aligné${s.aligned.length > 1 ? 's' : ''}`]
  parts.push(`${s.opposed.length} opposé${s.opposed.length > 1 ? 's' : ''}`)
  if (s.neutral.length) parts.push(`${s.neutral.length} neutre${s.neutral.length > 1 ? 's' : ''}`)
  if (s.unknown.length) parts.push(`${s.unknown.length} inconnu${s.unknown.length > 1 ? 's' : ''}`)
  return `${parts.join(' · ')} (sur ${s.n_horizons - 1} autres horizons)`
}

/** Matrice enregistrée dans `entry_signal` au moment de l'action (null si position antérieure à MTF-1). */
export function storedMatrix(entrySignal: Record<string, unknown> | null | undefined): MtfMatrix | null {
  const m = entrySignal?.mtf_matrix
  if (!m || typeof m !== 'object') return null
  const mm = m as MtfMatrix
  return Array.isArray(mm.horizons) && mm.summary ? mm : null
}
