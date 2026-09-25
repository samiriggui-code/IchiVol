/** Persisted Market page prefs (UI-MARKET) — layout, sort, layers, volume. */

export type DrawerPos = 'closed' | 'half' | 'full'
export type DrawerTab = 'list' | 'analysis' | 'backtest'
export type SortDir = 'asc' | 'desc'
export type WatchlistSortKey =
  | 'symbol'
  | 'change24h'
  | 'rvol'
  | 'bias'
  | 'score'
  | 'context'

export interface MarketLayoutPrefs {
  rightOpen: boolean
  rightWidth: number
  bottomOpen: boolean
  bottomHeight: number
  volumeHeight: number
  sortKey: WatchlistSortKey
  sortDir: SortDir
  drawerPos: DrawerPos
  drawerTab: DrawerTab
  classFilter: string | null
  /** Bottom dock tab when panel open (desktop). */
  bottomTab: 'backtest' | 'mark' | 'journal'
}

const LAYOUT_KEY = 'ichivol.market.layout'
/** Bump when DEFAULT_LAYERS change so existing devices pick up new defaults. */
export const LAYERS_PREFS_VERSION = 2
const LAYERS_KEY = `ichivol.market.layers.v${LAYERS_PREFS_VERSION}`

export const DEFAULT_LAYOUT: MarketLayoutPrefs = {
  rightOpen: true,
  rightWidth: 380,
  bottomOpen: false,
  bottomHeight: 250,
  volumeHeight: 150,
  sortKey: 'rvol',
  sortDir: 'desc',
  drawerPos: 'closed',
  drawerTab: 'list',
  classFilter: null,
  bottomTab: 'backtest',
}

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

/** Primary Calques toggles (maquette). */
export const ICHIMOKU_LAYER_KEYS: IndicatorLayerKey[] = [
  'tenkan',
  'kijun',
  'spanA',
  'spanB',
]

export type AdvancedLayerKey = ObjectLayerKey | 'signals'

/** Advanced layers under the collapsed Calques section (maquette). */
export const ADVANCED_LAYER_META: {
  key: AdvancedLayerKey
  label: string
  subtitle: string
  color: string
}[] = [
  {
    key: 'signals',
    label: 'Signaux',
    subtitle: 'Marqueurs volume-confirmés',
    color: 'var(--neutral)',
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

/** Maquette defaults: candles + volume + Ichimoku cloud/TK only. */
export const DEFAULT_LAYERS: LayerPrefs = {
  candles: true,
  tenkan: true,
  kijun: true,
  spanA: true,
  spanB: true,
  volume: true,
  signals: false,
  structure: false,
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

export function loadLayoutPrefs(): MarketLayoutPrefs {
  return readJson(LAYOUT_KEY, DEFAULT_LAYOUT)
}

export function saveLayoutPrefs(prefs: MarketLayoutPrefs): void {
  try {
    localStorage.setItem(LAYOUT_KEY, JSON.stringify(prefs))
  } catch {
    /* ignore quota */
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
