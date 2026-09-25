/** Persisted Marché layer prefs (Ichimoku / S-R / volume). Pas de prefs drawer/dock. */

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

/** Primary Ichimoku toggles (maquette checkbox). */
export const ICHIMOKU_LAYER_KEYS: IndicatorLayerKey[] = [
  'tenkan',
  'kijun',
  'spanA',
  'spanB',
]

/** Meta for object overlays still drawn by PriceChart when enabled. */
export const OBJECT_LAYER_META: {
  key: ObjectLayerKey
  label: string
  subtitle: string
  color: string
  emptyUntil?: string
}[] = [
  {
    key: 'structure',
    label: 'Supports / résistances',
    subtitle: 'Zones S/R et trendlines moteur',
    color: 'var(--bull)',
  },
  {
    key: 'breaks',
    label: 'BOS / CHoCH',
    subtitle: 'Cassures structure (T9b)',
    color: 'var(--neutral)',
  },
  {
    key: 'fibonacci',
    label: 'Fibonacci',
    subtitle: 'Retracements impulsifs (T9e)',
    color: 'var(--tenkan)',
  },
  {
    key: 'fvg',
    label: 'FVG',
    subtitle: 'Fair value gaps (T9d)',
    color: 'var(--kijun)',
  },
  {
    key: 'claude',
    label: 'Dessins Claude',
    subtitle: 'Objets dessinés par l’agent',
    color: 'var(--primary)',
  },
  {
    key: 'user_trades',
    label: 'Mes trades',
    subtitle: 'ENTRY / STOP / TARGET utilisateur',
    color: 'var(--bear)',
  },
  {
    key: 'backtest',
    label: 'Backtest',
    subtitle: 'Overlay stratégie catalogue',
    color: 'var(--muted-foreground)',
  },
]

/** Bump when DEFAULT_LAYERS change so devices pick up maquette defaults. */
export const LAYERS_PREFS_VERSION = 3
const LAYERS_KEY = `ichivol.market.layers.v${LAYERS_PREFS_VERSION}`

/** Maquette : Ichimoku + S/R cochés ; calques avancés off. */
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

export function isIchimokuOn(prefs: LayerPrefs): boolean {
  return ICHIMOKU_LAYER_KEYS.every((k) => prefs[k])
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
  const counts = {
    structure: 0,
    fibonacci: 0,
    fvg: 0,
    breaks: 0,
    claude: 0,
    user_trades: 0,
    backtest: 0,
  } satisfies Record<ObjectLayerKey, number>
  if (!objects) return counts
  for (const o of objects) {
    const k = layerFromSource(o.source, o.layer)
    counts[k] += 1
  }
  return counts
}
