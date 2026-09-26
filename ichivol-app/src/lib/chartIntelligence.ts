/**
 * Chart Intelligence — contrat de données (V3 prototype).
 *
 * PRINCIPE : on NE crée PAS un nouveau type « DrawingObject ». Le moteur
 * Python sert déjà un contrat canonique `ChartObject` (engine/app/chart_objects/
 * types.py ↔ src/lib/chartObjects.ts) avec layer structure / fibonacci / fvg /
 * breaks. Chart Intelligence réutilise ce contrat tel quel et ajoute seulement :
 *   - 2 valeurs de `layer` additives : 'liquidity' | 'confluence'
 *   - des clés `origin.*` documentées (IntelligenceOrigin) — pas de nouveau champ racine
 *   - une enveloppe de réponse (OHLCV + Ichimoku + market_state + analysis)
 *
 * React n'effectue AUCUN calcul financier ici : uniquement typage, lecture de
 * champs fournis par Python et libellés d'affichage.
 */

import type { ChartObject, ChartObjectLayer, ChartObjectsResponse } from './chartObjects'
import type { ProjectedKumoPoint } from './engineIndicators'
import { OBJECT_LAYER_META, type ObjectLayerKey } from './marketPrefs'
import type { Candle } from './types'

/* ------------------------------------------------------------------ */
/* Objets                                                              */
/* ------------------------------------------------------------------ */

/** Layers existants + 2 additions proposées côté Python (ChartObjectLayer enum). */
export type IntelligenceLayer = ChartObjectLayer | 'liquidity' | 'confluence'

/** Statuts moteur (FVG T9d : open/partial/filled/invalidated) + cycle de vie des niveaux. */
export type IntelligenceStatus =
  | 'open'
  | 'partial'
  | 'filled'
  | 'tested'
  | 'broken'
  | 'swept'
  | 'invalidated'
  | 'archived'

/** Clés `origin` lues par Chart Intelligence. Toutes optionnelles (additives). */
export interface IntelligenceOrigin extends Record<string, unknown> {
  /** Famille métier : fibonacci | fvg | structure_event | swing | zone | trendline | liquidity | confluence */
  kind?: string
  /** Producteur Python (clé machine) — voir PRODUCER_LABELS. */
  producer?: string
  /** Premier instant (unix s) où Python pouvait connaître l'objet → anti-lookahead. */
  known_at?: number
  status?: IntelligenceStatus
  /** Explication courte fournie par Python / agent (« WHY? »). */
  reason?: string
  /** L'objet a-t-il été consommé par le Decision Engine ? */
  used_by_decision?: boolean
  /** Regroupe plusieurs ChartObject en un seul dessin (ex. niveaux d'un même Fib). */
  group_id?: string
  /** Fib : ancres (déjà présentes côté engine sous forme swing_low/swing_high + bars). */
  anchor_start?: { time: number; price: number }
  anchor_end?: { time: number; price: number }
  ratio?: number
  swing_low?: number
  swing_high?: number
  /** Zones S/R. */
  touch_count?: number
  /** Timeframe de l'objet si différent du graphique (ex. support 4H affiché en 1H). */
  htf?: string
  /** FVG. */
  direction?: 'bullish' | 'bearish'
  fill_ratio?: number
  /** BOS / CHOCH : swing cassé (point de départ du segment). */
  event_type?: 'BOS' | 'CHOCH'
  swing_time?: number
  level?: number
  internal?: boolean
  /** Swing labels (HH / HL / LH / LL). */
  swing?: 'HH' | 'HL' | 'LH' | 'LL'
  /** Confluence : composants listés par Python. */
  components?: ConfluenceComponent[]
  /** true tant que le score est fictif (prototype). */
  score_is_mock?: boolean
  /** Walk-forward replay (CI-R1) : historique d’état ≤ as_of. */
  status_history?: Array<{
    at: number
    status?: IntelligenceStatus
    touch_count?: number
    confidence?: number
    price_low?: number
    price_high?: number
  }>
  /**
   * Identité stable hors empreinte d’id (CI-R8).
   * FVG / zone / BOS / Fib group / breakout — utilisée pour known_at.
   */
  lineage_key?: string
}

export interface ConfluenceComponent {
  /** Famille pipeline (engine/app/confluence/families.py) : direction | participation | structure | location | regime */
  family: string
  label: string
  /** Valeur lisible (prix, ratio…) — fournie telle quelle par Python. */
  value?: string
  /** false = composant présent mais non confirmé (ex. RVOL sous seuil). */
  satisfied?: boolean
}

/** ChartObject existant, avec layer élargi et origin typé. */
export type IntelligenceObject = Omit<ChartObject, 'layer' | 'origin'> & {
  layer?: IntelligenceLayer | null
  origin: IntelligenceOrigin
}

/* ------------------------------------------------------------------ */
/* Enveloppe de réponse                                                */
/* ------------------------------------------------------------------ */

export interface IntelligenceIchimokuPoint {
  time: number
  tenkan: number | null
  kijun: number | null
}

export interface MarketState {
  trend: 'bullish' | 'bearish' | 'range'
  /** Ex. HH_HL, LH_LL, MIXED */
  structure: string
  volatility: 'dead' | 'normal' | 'extreme'
  rvol: number
}

export interface IntelligenceAnalysis {
  /** Libellé fourni par Python (ex. PRUDENCE / BUY). Mappé via analysisTone(). */
  state: string
  confidence: number
  summary: string
  /** Lignes « Confluence : … » déjà rédigées par Python / agent. */
  confluence?: string[]
  /** Conditions attendues (ex. « RVOL > 1.5 »). */
  waiting?: string[]
  /** Producteur du texte (agent / LLM) — jamais autorité de décision. */
  producer?: string
  /** `pipeline` = Option B (portes) ; `combiner` = brut Ichimoku×RVOL. */
  kind?: 'pipeline' | 'combiner' | string
  strategy_version?: string
}

/** Réponse attendue de GET /api/engine/chart-intelligence/{symbol}?timeframe&as_of (à créer). */
export interface ChartIntelligenceResponse extends Omit<ChartObjectsResponse, 'objects'> {
  as_of: number | null
  candles: Candle[]
  ichimoku: IntelligenceIchimokuPoint[]
  projection: ProjectedKumoPoint[]
  market_state: MarketState
  objects: IntelligenceObject[]
  analysis: IntelligenceAnalysis | null
  /** Métadonnées de replay (bornes disponibles côté moteur). */
  replay?: { first: number; last: number; bar_seconds: number }
  /** true = réponse simulée (mock). */
  mock?: boolean
}

/* ------------------------------------------------------------------ */
/* Couches UI (affichage uniquement)                                   */
/* ------------------------------------------------------------------ */

export type IntelligenceLayerKey =
  | 'market_structure'
  | 'support_resistance'
  | 'trendlines'
  | 'fibonacci'
  | 'fvg'
  | 'liquidity'
  | 'ichimoku'
  | 'confluence'

export type IntelligenceLayerPrefs = Record<IntelligenceLayerKey, boolean>

export const DEFAULT_INTELLIGENCE_LAYERS: IntelligenceLayerPrefs = {
  market_structure: true,
  support_resistance: false,
  trendlines: false,
  fibonacci: true,
  fvg: true,
  liquidity: false,
  ichimoku: true,
  confluence: false,
}

/** Couleurs : reprises de OBJECT_LAYER_META (palette Calques du Marché) quand la couche existe. */
const metaColor = (k: ObjectLayerKey) => OBJECT_LAYER_META.find((m) => m.key === k)?.color ?? '#7d8288'

export const INTELLIGENCE_LAYER_META: {
  key: IntelligenceLayerKey
  label: string
  subtitle: string
  color: string
}[] = [
  { key: 'market_structure', label: 'Market Structure', subtitle: 'HH / HL / LH / LL · BOS / CHOCH', color: metaColor('breaks') },
  { key: 'support_resistance', label: 'Support / Resistance', subtitle: 'Zones S/R moteur (+ HTF)', color: metaColor('structure') },
  { key: 'trendlines', label: 'Trendlines', subtitle: 'Obliques pivots', color: metaColor('structure') },
  { key: 'fibonacci', label: 'Fibonacci', subtitle: 'Auto Fib ancré sur la structure', color: metaColor('fibonacci') },
  { key: 'fvg', label: 'FVG', subtitle: 'Fair value gaps', color: metaColor('fvg') },
  { key: 'liquidity', label: 'Liquidity', subtitle: 'BSL / SSL (sommets / creux égaux)', color: '#a76c17' },
  { key: 'ichimoku', label: 'Ichimoku', subtitle: 'Tenkan / Kijun / Kumo', color: '#baa37e' },
  { key: 'confluence', label: 'Confluence', subtitle: 'Zones multi-calculs (score mock)', color: '#1a7df5' },
]

/**
 * Classement d'un ChartObject dans une couche UI, à partir des champs déjà
 * fournis par Python (layer / type / origin.kind). Pas de calcul.
 */
export function intelligenceLayerOf(o: IntelligenceObject): IntelligenceLayerKey {
  const layer = o.layer ?? 'structure'
  if (layer === 'fibonacci') return 'fibonacci'
  if (layer === 'fvg') return 'fvg'
  if (layer === 'breaks') return 'market_structure'
  if (layer === 'liquidity') return 'liquidity'
  if (layer === 'confluence') return 'confluence'
  if (o.type === 'trend_line' || o.type === 'ray' || o.type === 'channel') return 'trendlines'
  return 'support_resistance'
}

/** Identifiant de sélection : un Fib (N niveaux) se sélectionne d'un bloc. */
export function selectionKeyOf(o: IntelligenceObject): string {
  return o.origin.group_id ?? o.id
}

/* ------------------------------------------------------------------ */
/* Libellés                                                            */
/* ------------------------------------------------------------------ */

export const PRODUCER_LABELS: Record<string, string> = {
  structure_engine: 'Python Structure Engine',
  fibonacci_engine: 'Python Fibonacci Engine',
  fvg_engine: 'Python FVG Engine',
  liquidity_engine: 'Python Liquidity Engine',
  confluence_engine: 'Python Confluence Engine',
  agent: 'Agent IchiVol',
}

export function producerLabel(o: IntelligenceObject): string {
  const key = o.origin.producer
  if (key && PRODUCER_LABELS[key]) return PRODUCER_LABELS[key]
  if (key) return key
  if (o.source === 'engine') return 'Python Engine'
  if (o.source === 'claude') return 'Agent'
  if (o.source === 'user') return 'Manuel'
  return o.source
}

export const STATUS_LABELS: Record<IntelligenceStatus, string> = {
  open: 'ACTIVE',
  partial: 'PARTIALLY FILLED',
  filled: 'FILLED',
  tested: 'TESTED',
  broken: 'BROKEN',
  swept: 'SWEPT',
  invalidated: 'INVALIDATED',
  archived: 'ARCHIVED',
}

export type Tone = 'green' | 'amber' | 'red' | 'gray' | 'blue'

export function statusTone(s: IntelligenceStatus | undefined): Tone {
  if (s === 'open') return 'green'
  if (s === 'partial' || s === 'tested') return 'amber'
  if (s === 'broken' || s === 'invalidated') return 'red'
  if (s === 'swept') return 'blue'
  return 'gray'
}

/**
 * Ton d'affichage d'un état d'analyse. Les libellés gate existants
 * (BUY / SELL / WATCH / NO_TRADE, lib/verdict.ts) sont reconnus ; tout autre
 * libellé Python (ex. PRUDENCE) reste affiché tel quel en ambre.
 */
export function analysisTone(state: string): Tone {
  if (state === 'BUY') return 'green'
  if (state === 'SELL' || state === 'NO_TRADE') return 'red'
  if (state === 'WATCH' || state === 'PRUDENCE') return 'amber'
  return 'gray'
}

export function objectTitle(o: IntelligenceObject): string {
  const kind = o.origin.kind
  if (kind === 'fibonacci') return 'Fibonacci retracement'
  if (kind === 'fvg') return `${o.origin.direction === 'bearish' ? 'Bearish' : 'Bullish'} FVG`
  if (kind === 'structure_event') return o.origin.event_type === 'CHOCH' ? 'Change of character' : 'Break of structure'
  if (kind === 'swing') return `Swing ${o.origin.swing ?? ''}`.trim()
  if (kind === 'liquidity') return o.side === 'resistance' ? 'Buy-side liquidity' : 'Sell-side liquidity'
  if (kind === 'confluence') return 'Confluence'
  if (kind === 'trendline' || o.type === 'trend_line' || o.type === 'ray') return 'Trendline'
  if (o.side === 'resistance') return 'Resistance'
  return 'Support'
}

/** Instant à partir duquel l'objet peut être montré en replay (anti-lookahead UI). */
export function objectKnownAt(o: IntelligenceObject): number {
  const known = o.origin?.known_at
  if (typeof known === 'number' && Number.isFinite(known)) return known
  if (typeof o.as_of === 'number' && Number.isFinite(o.as_of)) return o.as_of
  const t = o.points?.[0]?.time
  if (typeof t === 'number' && Number.isFinite(t)) return t
  return Number.POSITIVE_INFINITY
}

/**
 * Coupe un snapshot à `asOf` pour le mock / fallback.
 * CI-R5 : kumo projeté connu à T si (time - 25 bougies) ≤ T.
 * Les objets d’un snapshot LIVE ne doivent PAS être rejoués ainsi en prod
 * (CI-R1) — utiliser le pack walk-forward `/replay`.
 */
export function sliceIntelligenceAt(
  live: ChartIntelligenceResponse,
  asOf: number,
): ChartIntelligenceResponse {
  const barSec = live.replay?.bar_seconds ?? 3600
  const candles = live.candles.filter((c) => c.time <= asOf)
  const ichimoku = live.ichimoku.filter((p) => p.time <= asOf)
  const projection = live.projection.filter((p) => p.time - 25 * barSec <= asOf)
  const objects = live.objects
    .filter((o) => objectKnownAt(o) <= asOf)
    .map((o) => applyStatusHistoryAt(o, asOf))
  return {
    ...live,
    as_of: asOf,
    candles,
    ichimoku,
    projection,
    objects,
    count: objects.length,
    // Analyse = verdict live ; masquée pendant le replay pour ne pas spoiler.
    analysis: null,
    mock: live.mock,
  }
}

/** Applique le dernier état de status_history ≤ asOf (CI-R1). */
export function applyStatusHistoryAt(o: IntelligenceObject, asOf: number): IntelligenceObject {
  const hist = o.origin?.status_history
  if (!Array.isArray(hist) || hist.length === 0) return o
  let last: { at: number; status?: string; touch_count?: number; confidence?: number; price_low?: number; price_high?: number } | null =
    null
  for (const row of hist) {
    if (typeof row?.at === 'number' && row.at <= asOf) last = row
  }
  if (!last) return o
  const origin = { ...o.origin }
  if (last.status != null) origin.status = last.status as IntelligenceObject['origin']['status']
  if (last.touch_count != null) origin.touch_count = last.touch_count
  return {
    ...o,
    confidence: last.confidence ?? o.confidence,
    price_low: last.price_low ?? o.price_low,
    price_high: last.price_high ?? o.price_high,
    origin,
  }
}

/** Format prix identique à l'axe fr-FR de PriceChart. */
export function fmtPrice(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return '—'
  const a = Math.abs(n)
  const digits = a >= 10_000 ? 0 : a >= 100 ? 2 : a >= 1 ? 2 : 4
  return n.toLocaleString('fr-FR', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export function fmtPct(conf: number | null | undefined): string {
  if (conf == null || !Number.isFinite(conf)) return '—'
  return `${Math.round(conf * 100)} %`
}

export function fmtTime(unix: number | null | undefined): string {
  if (unix == null) return '—'
  return new Date(unix * 1000).toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/* ------------------------------------------------------------------ */
/* Client API (Python) — branché plus tard                             */
/* ------------------------------------------------------------------ */

export interface ChartIntelligenceQuery {
  symbol: string
  timeframe: string
  /** Snapshot tel que recalculé à cet instant (as_of côté Python). */
  asOf?: number | null
  limit?: number
}

export interface ChartIntelligenceReplayQuery {
  symbol: string
  timeframe: string
  from?: number | null
  to?: number | null
  lookbackBars?: number
  limit?: number
}

export interface ChartIntelligenceReplayFrame {
  as_of: number
  /** CI-R7: candles/ichimoku/projection are on the pack root; front truncates by as_of. */
  objects: IntelligenceObject[]
  market_state: ChartIntelligenceResponse['market_state']
}

export interface ChartIntelligenceReplayPack extends ChartIntelligenceResponse {
  from: number
  to: number
  lookback_bars: number
  frames: ChartIntelligenceReplayFrame[]
  cached?: boolean
  replay_mode?: string
}

/**
 * Endpoint Python GET /api/engine/chart-intelligence/{symbol}
 * — cookie de session, proxy Node /api/engine/*, erreurs `detail`.
 */
export async function getChartIntelligence(q: ChartIntelligenceQuery): Promise<ChartIntelligenceResponse> {
  const params = new URLSearchParams({ timeframe: q.timeframe, limit: String(q.limit ?? 300) })
  if (q.asOf != null) params.set('as_of', String(q.asOf))
  const res = await fetch(
    `/api/engine/chart-intelligence/${encodeURIComponent(q.symbol)}?${params}`,
    { credentials: 'include' },
  )
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `Erreur ${res.status}`)
  }
  return (await res.json()) as ChartIntelligenceResponse
}

/** Walk-forward replay pack (CI-R1a). */
export async function getChartIntelligenceReplay(
  q: ChartIntelligenceReplayQuery,
): Promise<ChartIntelligenceReplayPack> {
  const params = new URLSearchParams({
    timeframe: q.timeframe,
    limit: String(q.limit ?? 300),
    lookback_bars: String(q.lookbackBars ?? 48),
    sources: 'engine',
  })
  if (q.from != null) params.set('from', String(q.from))
  if (q.to != null) params.set('to', String(q.to))
  const res = await fetch(
    `/api/engine/chart-intelligence/${encodeURIComponent(q.symbol)}/replay?${params}`,
    { credentials: 'include' },
  )
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: string } | null
    throw new Error(body?.detail ?? `Erreur ${res.status}`)
  }
  return (await res.json()) as ChartIntelligenceReplayPack
}
