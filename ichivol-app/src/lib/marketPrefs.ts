/** Persisted Marché layer prefs (Ichimoku / S-R / Fib / FVG / breaks…). */

export type ObjectLayerKey =
  | 'structure'
  | 'fibonacci'
  | 'fvg'
  | 'breaks'
  | 'claude'
  | 'user_trades'
  | 'backtest'

export type IndicatorLayerKey =
  | 'candles'
  | 'tenkan'
  | 'kijun'
  | 'spanA'
  | 'spanB'
  | 'volume'
  | 'signals'

export type LayerPrefs = Record<ObjectLayerKey | IndicatorLayerKey, boolean> & {
  fadeFilledFvg: boolean
  showInvalidated: boolean
}

/** Cases maquette « Ichimoku 9 / 26 / 52 » → ces 4 calques ensemble. */
const ICHIMOKU_LAYER_KEYS: IndicatorLayerKey[] = ['tenkan', 'kijun', 'spanA', 'spanB']

/** Calques d'objets moteur que PriceChart sait dessiner. */
export const OBJECT_LAYER_KEYS: ObjectLayerKey[] = [
  'structure',
  'breaks',
  'fibonacci',
  'fvg',
  'claude',
  'user_trades',
  'backtest',
]

export const OBJECT_LAYER_META: {
  key: ObjectLayerKey
  label: string
  subtitle: string
  color: string
  emptyUntil?: string
}[] = [
  {
    key: 'structure',
    label: 'Structure',
    subtitle: 'Zones S/R et trendlines moteur',
    color: '#0b8f83',
  },
  {
    key: 'breaks',
    label: 'Cassures',
    subtitle: 'BOS / CHoCH / breakouts',
    color: '#7d8288',
  },
  {
    key: 'fibonacci',
    label: 'Fibonacci',
    subtitle: 'Retracements impulsifs',
    color: '#a4a9c2',
  },
  {
    key: 'fvg',
    label: 'FVG',
    subtitle: 'Fair value gaps',
    color: '#6b7c93',
  },
  {
    key: 'claude',
    label: 'Claude',
    subtitle: 'Objets dessinés par l’agent',
    color: '#1a7df5',
  },
  {
    key: 'user_trades',
    label: 'Trades',
    subtitle: 'ENTRY / STOP / TARGET utilisateur',
    color: '#c8412f',
  },
  {
    key: 'backtest',
    label: 'Backtest',
    subtitle: 'Overlay stratégie catalogue',
    color: '#91989d',
  },
]

/** Bump when DEFAULT_LAYERS change so devices pick up restored object layers. */
const LAYERS_PREFS_VERSION = 5
const LAYERS_KEY = `ichivol.market.layers.v${LAYERS_PREFS_VERSION}`

/**
 * Defaults sobres : Ichimoku + Structure (S/R) seulement.
 * Fib / FVG / Cassures / agent / trades off — à activer via palette Calques.
 */
export const DEFAULT_LAYERS: LayerPrefs = {
  candles: true,
  tenkan: true,
  kijun: true,
  spanA: true,
  spanB: true,
  volume: true,
  signals: false,
  structure: true,
  fibonacci: false,
  fvg: false,
  breaks: false,
  claude: false,
  user_trades: false,
  backtest: false,
  fadeFilledFvg: true,
  showInvalidated: false,
}

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return fallback
    return { ...fallback, ...JSON.parse(raw) } as T
  } catch {
    return fallback
  }
}

export function loadLayerPrefs(): LayerPrefs {
  return readJson(LAYERS_KEY, DEFAULT_LAYERS)
}

export function saveLayerPrefs(prefs: LayerPrefs): void {
  try {
    localStorage.setItem(LAYERS_KEY, JSON.stringify(prefs))
  } catch {
    /* ignore */
  }
}

export function withIchimoku(prefs: LayerPrefs, on: boolean): LayerPrefs {
  const next = { ...prefs }
  for (const k of ICHIMOKU_LAYER_KEYS) next[k] = on
  return next
}

export function layerFromSource(
  source: string,
  layer?: string | null,
): ObjectLayerKey {
  if (
    layer === 'structure' ||
    layer === 'fibonacci' ||
    layer === 'fvg' ||
    layer === 'breaks' ||
    layer === 'claude' ||
    layer === 'user_trades' ||
    layer === 'backtest'
  ) {
    return layer
  }
  if (source === 'user') return 'user_trades'
  if (source === 'claude') return 'claude'
  if (source === 'backtest') return 'backtest'
  return 'structure'
}

export function countObjectsByLayer(
  objects: { source: string; layer?: string | null }[] | null | undefined,
): Record<ObjectLayerKey, number> {
  const counts: Record<ObjectLayerKey, number> = {
    structure: 0,
    fibonacci: 0,
    fvg: 0,
    breaks: 0,
    claude: 0,
    user_trades: 0,
    backtest: 0,
  }
  if (!objects) return counts
  for (const o of objects) {
    const k = layerFromSource(o.source, o.layer)
    counts[k] += 1
  }
  return counts
}
