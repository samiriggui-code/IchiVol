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
  /** Left watchlist rail (desktop market-layout). */
  leftOpen: boolean
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
const LAYERS_KEY = 'ichivol.market.layers'

export const DEFAULT_LAYOUT: MarketLayoutPrefs = {
  leftOpen: true,
  rightOpen: true,
  rightWidth: 280,
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
    color: 'var(--bull)',
  },
  {
    key: 'breaks',
    label: 'Cassures',
    subtitle: 'BOS / CHoCH / breakouts (T9b)',
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
    label: 'Claude',
    subtitle: 'Objets dessinés par l’agent',
    color: 'var(--primary)',
  },
  {
    key: 'user_trades',
    label: 'Trades',
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

export const DEFAULT_LAYERS: LayerPrefs = {
  candles: true,
  tenkan: true,
  kijun: true,
  spanA: true,
  spanB: true,
  volume: true,
  signals: true,
  structure: true,
  fibonacci: false,
  fvg: false,
  breaks: true,
  claude: true,
  user_trades: true,
  backtest: true,
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
