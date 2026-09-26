/**
 * MOCK — réponse simulée du futur endpoint Python Chart Intelligence.
 *
 * Tout ce fichier est remplaçable par `getChartIntelligence()` (chartIntelligence.ts).
 * Les objets respectent le contrat ChartObject existant (type / source / layer /
 * points / price_low / price_high / side / label / confidence / as_of / origin / subtype).
 *
 * `mockChartIntelligenceAt(asOf)` simule le paramètre `as_of` de l'API : il ne
 * renvoie que ce que Python aurait pu connaître à cet instant (origin.known_at),
 * avec le statut valable à cet instant. C'est une SIMULATION du moteur (anti-
 * lookahead réalisé côté Python) — pas une logique React.
 *
 * Les scores / confidences sont FICTIFS (maquette). Aucune formule définitive.
 */

import type {
  ChartIntelligenceResponse,
  IntelligenceAnalysis,
  IntelligenceObject,
  IntelligenceOrigin,
  MarketState,
} from './chartIntelligence'
import {
  MOCK_BAR_SECONDS,
  MOCK_CANDLES,
  MOCK_ICHIMOKU,
  MOCK_PROJECTION,
  MOCK_T0,
} from './chartIntelligenceMock.data'

export const MOCK_SYMBOL = 'SOLUSDT'
export const MOCK_TIMEFRAME = '1h'

/** Temps unix de la bougie n°i. */
const b = (i: number) => MOCK_T0 + i * MOCK_BAR_SECONDS
const LAST_BAR = MOCK_CANDLES.length - 1

/** Définition mock : objet + évolution dans le temps (champs mock-only, retirés à la sortie). */
interface MockDef {
  obj: Omit<IntelligenceObject, 'id' | 'symbol' | 'timeframe' | 'as_of'> & { id: string }
  /** Le dernier point suit le curseur `as_of` (objet encore vivant). */
  extendsToAsOf?: boolean
  /** Mises à jour datées (statut, touches, confidence…) appliquées si at ≤ as_of. */
  history?: Array<{ at: number; confidence?: number; origin?: Partial<IntelligenceOrigin> }>
}

/* ------------------------------------------------------------------ */
/* Fibonacci — ancré sur l'impulsion 124,30 → 137,80 (T9e, anchor=auto) */
/* ------------------------------------------------------------------ */

const FIB_LOW = 124.3
const FIB_HIGH = 137.8
const FIB_GROUP = 'fib-1h-impulse-b40-b92'
const FIB_RATIOS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]

const fibDefs: MockDef[] = FIB_RATIOS.map((ratio) => ({
  obj: {
    id: `${FIB_GROUP}-${ratio}`,
    type: 'horizontal_line',
    source: 'engine',
    layer: 'fibonacci',
    // Prix du niveau tel que Python le sérialise (swing_high - ratio * span).
    points: [{ time: b(92), price: Number((FIB_HIGH - ratio * (FIB_HIGH - FIB_LOW)).toFixed(3)) }],
    price_low: null,
    price_high: null,
    side: 'support',
    label: String(ratio),
    confidence: 0.84,
    subtype: `up_${ratio}`,
    origin: {
      kind: 'fibonacci',
      producer: 'structure_engine',
      group_id: FIB_GROUP,
      known_at: b(95),
      ratio,
      impulse: 'up',
      anchor_source: 'impulse',
      swing_low: FIB_LOW,
      swing_high: FIB_HIGH,
      anchor_start: { time: b(40), price: FIB_LOW },
      anchor_end: { time: b(92), price: FIB_HIGH },
      reason:
        'Major bullish impulse confirmed by market structure and relative volume.',
      used_by_decision: true,
      status: 'open',
    },
  },
  extendsToAsOf: true,
}))

/* ------------------------------------------------------------------ */
/* Supports / résistances (zones) + support HTF                         */
/* ------------------------------------------------------------------ */

const zoneDefs: MockDef[] = [
  {
    obj: {
      id: 'zone-support-129.40',
      type: 'zone',
      source: 'engine',
      layer: 'structure',
      points: [
        { time: b(22), price: 129.4 },
        { time: b(35), price: 129.4 },
      ],
      price_low: 129.2,
      price_high: 129.6,
      side: 'support',
      label: 'S ×2',
      confidence: 0.62,
      subtype: 'consensus',
      origin: {
        kind: 'zone',
        producer: 'structure_engine',
        known_at: b(35),
        touch_count: 2,
        status: 'open',
        reason: 'Ancienne résistance 129,30 devenue support (flip S/R), défendue à plusieurs reprises.',
        used_by_decision: true,
      },
    },
    extendsToAsOf: true,
    history: [
      { at: b(55), confidence: 0.74, origin: { touch_count: 3, status: 'tested' } },
      { at: b(84), confidence: 0.89, origin: { touch_count: 4, status: 'tested' } },
    ],
  },
  {
    obj: {
      id: 'zone-resistance-136.20',
      type: 'zone',
      source: 'engine',
      layer: 'structure',
      points: [
        { time: b(90), price: 136.2 },
        { time: b(100), price: 136.2 },
      ],
      price_low: 136.0,
      price_high: 136.4,
      side: 'resistance',
      label: 'R ×3',
      confidence: 0.81,
      subtype: 'consensus',
      origin: {
        kind: 'zone',
        producer: 'structure_engine',
        known_at: b(100),
        touch_count: 3,
        status: 'tested',
        reason: 'Rejet du LH 136,35 sous le sommet 137,80 — offre récurrente.',
        used_by_decision: true,
      },
    },
    extendsToAsOf: true,
  },
  {
    obj: {
      id: 'zone-support-4h-131.05',
      type: 'zone',
      source: 'engine',
      layer: 'structure',
      points: [
        { time: b(48), price: 131.05 },
        { time: b(72), price: 131.05 },
      ],
      price_low: 130.85,
      price_high: 131.3,
      side: 'support',
      label: 'S 4H',
      confidence: 0.77,
      subtype: 'htf',
      origin: {
        kind: 'zone',
        producer: 'structure_engine',
        known_at: b(72),
        touch_count: 3,
        htf: '4h',
        status: 'open',
        reason: 'Zone S/R détectée en 4H, projetée sur le 1H.',
        used_by_decision: true,
      },
    },
    extendsToAsOf: true,
    history: [{ at: b(110), origin: { status: 'tested' } }],
  },
]

/* ------------------------------------------------------------------ */
/* Trendline                                                           */
/* ------------------------------------------------------------------ */

const trendDefs: MockDef[] = [
  {
    obj: {
      id: 'ray-support-b60-b84',
      type: 'ray',
      source: 'engine',
      layer: 'structure',
      points: [
        { time: b(60), price: 127.6 },
        { time: b(84), price: 129.4 },
      ],
      price_low: null,
      price_high: null,
      side: 'support',
      label: null,
      confidence: 0.72,
      subtype: 'pivot',
      origin: {
        kind: 'trendline',
        producer: 'structure_engine',
        known_at: b(87),
        touch_count: 2,
        status: 'open',
        reason: 'Oblique haussière reliant les HL 127,60 et 129,40.',
        used_by_decision: true,
      },
    },
    history: [{ at: b(110), confidence: 0.76, origin: { touch_count: 3, status: 'tested' } }],
  },
]

/* ------------------------------------------------------------------ */
/* FVG (T9d) — rectangles                                              */
/* ------------------------------------------------------------------ */

const fvgDefs: MockDef[] = [
  {
    obj: {
      id: 'fvg-bull-b64-130.00',
      type: 'rectangle',
      source: 'engine',
      layer: 'fvg',
      points: [
        { time: b(64), price: 130.0 },
        { time: b(80), price: 130.4 },
      ],
      price_low: 130.0,
      price_high: 130.4,
      side: 'support',
      label: 'FVG',
      confidence: 1,
      subtype: 'bullish',
      origin: {
        kind: 'fvg',
        producer: 'fvg_engine',
        direction: 'bullish',
        known_at: b(66),
        status: 'open',
        fill_ratio: 0,
        reason: 'Déséquilibre laissé par l’impulsion qui valide le BOS 129,90.',
        used_by_decision: false,
      },
    },
    extendsToAsOf: true,
    history: [
      { at: b(67), origin: { status: 'partial', fill_ratio: 0.55 } },
      { at: b(80), origin: { status: 'filled', fill_ratio: 1 } },
    ],
  },
  {
    obj: {
      id: 'fvg-bull-b86-131.20',
      type: 'rectangle',
      source: 'engine',
      layer: 'fvg',
      points: [
        { time: b(86), price: 131.2 },
        { time: b(88), price: 131.85 },
      ],
      price_low: 131.2,
      price_high: 131.85,
      side: 'support',
      label: 'FVG',
      confidence: 1,
      subtype: 'bullish',
      origin: {
        kind: 'fvg',
        producer: 'fvg_engine',
        direction: 'bullish',
        known_at: b(88),
        status: 'open',
        fill_ratio: 0,
        reason: 'Gap 3 bougies pendant l’impulsion 129,40 → 137,80 (RVOL élevé).',
        used_by_decision: true,
      },
    },
    extendsToAsOf: true,
    history: [{ at: b(110), origin: { status: 'partial', fill_ratio: 0.85 } }],
  },
  {
    obj: {
      id: 'fvg-bear-b100-134.60',
      type: 'rectangle',
      source: 'engine',
      layer: 'fvg',
      points: [
        { time: b(100), price: 134.6 },
        { time: b(102), price: 135.1 },
      ],
      price_low: 134.6,
      price_high: 135.1,
      side: 'resistance',
      label: 'FVG',
      confidence: 1,
      subtype: 'bearish',
      origin: {
        kind: 'fvg',
        producer: 'fvg_engine',
        direction: 'bearish',
        known_at: b(102),
        status: 'open',
        fill_ratio: 0,
        reason: 'Gap baissier sous le LH 136,35 — vendeurs agressifs.',
        used_by_decision: true,
      },
    },
    extendsToAsOf: true,
    history: [{ at: b(103), origin: { status: 'partial', fill_ratio: 0.5 } }],
  },
]

/* ------------------------------------------------------------------ */
/* Structure : swings (HH/HL/LH/LL) + BOS / CHOCH                      */
/* ------------------------------------------------------------------ */

const swing = (bar: number, price: number, s: 'HH' | 'HL' | 'LH' | 'LL'): MockDef => ({
  obj: {
    id: `swing-${s}-b${bar}`,
    type: 'text',
    source: 'engine',
    layer: 'breaks',
    points: [{ time: b(bar), price }],
    price_low: null,
    price_high: null,
    side: s === 'HH' || s === 'LH' ? 'resistance' : 'support',
    label: s,
    confidence: 1,
    subtype: `swing_${s.toLowerCase()}`,
    origin: {
      kind: 'swing',
      producer: 'structure_engine',
      swing: s,
      // Pivot confirmé après 3 bougies à droite.
      known_at: b(bar + 3),
      reason: `Pivot ${s} confirmé (3 bougies à droite).`,
      used_by_decision: true,
    },
  },
})

const event = (
  bar: number,
  level: number,
  swingBar: number,
  type: 'BOS' | 'CHOCH',
  dir: 'bullish' | 'bearish',
  confidence: number,
  reason: string,
  internal = false,
): MockDef => ({
  obj: {
    id: `${type.toLowerCase()}-${dir}-b${bar}`,
    type: 'marker',
    source: 'engine',
    layer: 'breaks',
    points: [{ time: b(bar), price: level }],
    price_low: null,
    price_high: null,
    side: dir === 'bullish' ? 'support' : 'resistance',
    label: `${type === 'CHOCH' ? 'CHoCH' : 'BOS'}${dir === 'bullish' ? '↑' : '↓'}`,
    confidence,
    subtype: type.toLowerCase(),
    origin: {
      kind: 'structure_event',
      producer: 'structure_engine',
      event_type: type,
      direction: dir,
      level,
      swing_time: b(swingBar),
      internal,
      break_quality: confidence >= 1 ? 'confirmed' : 'close',
      known_at: b(bar),
      reason,
      used_by_decision: true,
    },
  },
})

const structureDefs: MockDef[] = [
  swing(32, 129.3, 'LH'),
  swing(40, 124.3, 'LL'),
  swing(50, 129.9, 'HH'),
  swing(60, 127.6, 'HL'),
  swing(72, 133.0, 'HH'),
  swing(84, 129.4, 'HL'),
  swing(92, 137.8, 'HH'),
  swing(96, 134.9, 'HL'),
  swing(99, 136.35, 'LH'),
  event(48, 129.3, 32, 'CHOCH', 'bullish', 0.7, 'Clôture au-dessus du dernier LH 129,30 : fin de la séquence LH/LL.'),
  event(65, 129.9, 50, 'BOS', 'bullish', 1, 'Clôture au-dessus du HH 129,90 : structure HH/HL confirmée.'),
  event(88, 133.0, 72, 'BOS', 'bullish', 1, 'Cassure du HH 133,00 avec déplacement et RVOL élevé.'),
  event(
    101,
    134.9,
    96,
    'CHOCH',
    'bearish',
    0.55,
    'CHoCH interne : clôture sous le HL 134,90 après le LH 136,35. Structure majeure intacte.',
    true,
  ),
]

/* ------------------------------------------------------------------ */
/* Liquidité                                                           */
/* ------------------------------------------------------------------ */

const liquidityDefs: MockDef[] = [
  {
    obj: {
      id: 'liq-bsl-133.20',
      type: 'trend_line',
      source: 'engine',
      layer: 'liquidity',
      points: [
        { time: b(12), price: 133.2 },
        { time: b(88), price: 133.2 },
      ],
      price_low: null,
      price_high: null,
      side: 'resistance',
      label: 'BSL',
      confidence: 0.68,
      subtype: 'equal_highs',
      origin: {
        kind: 'liquidity',
        producer: 'liquidity_engine',
        known_at: b(75),
        status: 'open',
        reason: 'Sommets égaux 133,20 / 133,00 : stops acheteurs au-dessus.',
        used_by_decision: false,
      },
    },
    extendsToAsOf: false,
    history: [{ at: b(88), origin: { status: 'swept' } }],
  },
  {
    obj: {
      id: 'liq-ssl-127.60',
      type: 'trend_line',
      source: 'engine',
      layer: 'liquidity',
      points: [
        { time: b(26), price: 127.6 },
        { time: b(63), price: 127.6 },
      ],
      price_low: null,
      price_high: null,
      side: 'support',
      label: 'SSL',
      confidence: 0.6,
      subtype: 'equal_lows',
      origin: {
        kind: 'liquidity',
        producer: 'liquidity_engine',
        known_at: b(63),
        status: 'open',
        reason: 'Creux égaux 127,80 / 127,60 : stops vendeurs en dessous, non balayés.',
        used_by_decision: false,
      },
    },
    extendsToAsOf: true,
  },
]

/* ------------------------------------------------------------------ */
/* Confluence (score FICTIF)                                           */
/* ------------------------------------------------------------------ */

const confluenceDefs: MockDef[] = [
  {
    obj: {
      id: 'confluence-130.80-131.40',
      type: 'zone',
      source: 'engine',
      layer: 'confluence',
      points: [
        { time: b(95), price: 131.1 },
        { time: b(96), price: 131.1 },
      ],
      price_low: 130.8,
      price_high: 131.4,
      side: 'support',
      label: 'CONFLUENCE',
      confidence: 0.87,
      subtype: 'mock',
      origin: {
        kind: 'confluence',
        producer: 'confluence_engine',
        known_at: b(95),
        status: 'open',
        score_is_mock: true,
        reason: 'Plusieurs calculs indépendants convergent dans la même bande de prix.',
        used_by_decision: true,
        components: [
          { family: 'location', label: 'Fib 50 %', value: '131,05' },
          { family: 'structure', label: 'Support 4H', value: '130,85 – 131,30' },
          { family: 'structure', label: 'Bullish FVG', value: '131,20 – 131,85' },
          { family: 'structure', label: 'Trendline', value: '≈ 131,35' },
          { family: 'participation', label: 'RVOL', value: '1,42 (< 1,5)', satisfied: false },
        ],
      },
    },
    extendsToAsOf: true,
    history: [{ at: b(110), origin: { status: 'tested' } }],
  },
]

const ALL_DEFS: MockDef[] = [
  ...zoneDefs,
  ...trendDefs,
  ...liquidityDefs,
  ...fvgDefs,
  ...confluenceDefs,
  ...fibDefs,
  ...structureDefs,
]

/* ------------------------------------------------------------------ */
/* Market state + analyses datées                                      */
/* ------------------------------------------------------------------ */

const MARKET_STATES: Array<{ at: number; state: MarketState }> = [
  { at: b(0), state: { trend: 'bearish', structure: 'LH_LL', volatility: 'normal', rvol: 0.94 } },
  { at: b(48), state: { trend: 'range', structure: 'MIXED', volatility: 'normal', rvol: 1.31 } },
  { at: b(65), state: { trend: 'bullish', structure: 'HH_HL', volatility: 'normal', rvol: 1.58 } },
  { at: b(88), state: { trend: 'bullish', structure: 'HH_HL', volatility: 'normal', rvol: 1.9 } },
  { at: b(101), state: { trend: 'bullish', structure: 'HH_HL', volatility: 'normal', rvol: 1.12 } },
  { at: b(110), state: { trend: 'bullish', structure: 'HH_HL', volatility: 'normal', rvol: 1.42 } },
]

const ANALYSES: Array<{ at: number; analysis: IntelligenceAnalysis }> = [
  {
    at: b(48),
    analysis: {
      state: 'WATCH',
      confidence: 0.52,
      summary:
        'CHoCH haussier : le prix clôture au-dessus du dernier LH 129,30. La séquence baissière est interrompue mais aucun BOS ne confirme encore la nouvelle structure.',
      waiting: ['BOS au-dessus de 129,90', 'RVOL > 1.5'],
      producer: 'agent',
    },
  },
  {
    at: b(65),
    analysis: {
      state: 'WATCH',
      confidence: 0.6,
      summary:
        'BOS haussier au-dessus de 129,90 : la séquence HH/HL est confirmée. L’impulsion laisse un FVG 130,00 – 130,40 sous le prix.',
      waiting: ['HL au-dessus de 127,60', 'RVOL > 1.5'],
      producer: 'agent',
    },
  },
  {
    at: b(88),
    analysis: {
      state: 'WATCH',
      confidence: 0.66,
      summary:
        'BOS haussier au-dessus de 133,00 avec balayage de la liquidité 133,20. L’impulsion laisse un FVG 131,20 – 131,85 : zone de retour à surveiller.',
      waiting: ['Retour sur le FVG 131,20 – 131,85'],
      producer: 'agent',
    },
  },
  {
    at: b(101),
    analysis: {
      state: 'PRUDENCE',
      confidence: 0.61,
      summary:
        'CHoCH baissier interne sous 134,90 après un LH 136,35. La structure majeure reste haussière, mais le repli est en cours.',
      waiting: ['Réaction sur la zone de confluence'],
      producer: 'agent',
    },
  },
  {
    at: b(110),
    analysis: {
      state: 'PRUDENCE',
      confidence: 0.78,
      summary:
        'Le prix revient actuellement dans une zone de confluence située entre 130,80 et 131,40.',
      confluence: ['Fib 50 %', 'Support 4H', 'Bullish FVG', 'Trendline', 'RVOL reste sous le seuil de confirmation.'],
      waiting: ['RVOL > 1.5'],
      producer: 'agent',
    },
  },
]

/* ------------------------------------------------------------------ */
/* Snapshot « tel que connu à as_of » (simulation du moteur)           */
/* ------------------------------------------------------------------ */

function latestAt<T extends { at: number }>(rows: T[], asOf: number): T | undefined {
  let found: T | undefined
  for (const r of rows) if (r.at <= asOf) found = r
  return found
}

function materialize(def: MockDef, asOf: number): IntelligenceObject | null {
  const knownAt = def.obj.origin.known_at ?? 0
  if (knownAt > asOf) return null
  let confidence = def.obj.confidence
  let origin: IntelligenceOrigin = { ...def.obj.origin }
  for (const h of def.history ?? []) {
    if (h.at > asOf) continue
    if (h.confidence != null) confidence = h.confidence
    if (h.origin) origin = { ...origin, ...h.origin }
  }
  let points = def.obj.points.map((p) => ({ ...p }))
  if (def.extendsToAsOf && points.length === 2 && def.obj.type !== 'ray') {
    points[1] = { ...points[1]!, time: Math.max(points[1]!.time, asOf) }
  }
  points = points.map((p) => (p.time > asOf ? { ...p, time: asOf } : p))
  return {
    ...def.obj,
    symbol: MOCK_SYMBOL,
    timeframe: MOCK_TIMEFRAME,
    as_of: asOf,
    confidence,
    points,
    origin,
  }
}

export const MOCK_REPLAY_BOUNDS = {
  first: b(30),
  last: b(LAST_BAR),
  bar_seconds: MOCK_BAR_SECONDS,
}

/** Réponse mock telle que l'API la renverrait pour `as_of` (défaut : dernière bougie). */
export function mockChartIntelligenceAt(asOf: number = b(LAST_BAR)): ChartIntelligenceResponse {
  const t = Math.min(Math.max(asOf, MOCK_REPLAY_BOUNDS.first), MOCK_REPLAY_BOUNDS.last)
  const objects = ALL_DEFS.map((d) => materialize(d, t)).filter(
    (o): o is IntelligenceObject => o != null,
  )
  return {
    symbol: MOCK_SYMBOL,
    timeframe: MOCK_TIMEFRAME,
    as_of: t,
    provider: 'mock',
    provider_symbol: MOCK_SYMBOL,
    candles: MOCK_CANDLES.filter((c) => c.time <= t),
    ichimoku: MOCK_ICHIMOKU.filter((p) => p.time <= t),
    // Kumo projeté : chaque point est calculé à (time - 25 bougies) → connu si ≤ as_of.
    projection: MOCK_PROJECTION.filter((p) => p.time - 25 * MOCK_BAR_SECONDS <= t),
    market_state: (latestAt(MARKET_STATES, t) ?? MARKET_STATES[0]!).state,
    objects,
    count: objects.length,
    sources: ['engine'],
    analysis: latestAt(ANALYSES, t)?.analysis ?? null,
    replay: MOCK_REPLAY_BOUNDS,
    mock: true,
  }
}

/** Réponse finale « conceptuelle » (équivalent du chartIntelligenceResponse du cahier des charges). */
export const chartIntelligenceResponse: ChartIntelligenceResponse = mockChartIntelligenceAt()
