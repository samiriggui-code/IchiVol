/**
 * OB-1 — qualité de la collecte du carnet d'ordres (GET /api/engine/orderbook/{symbol}/quality).
 * Données d'une seule plateforme (Binance spot) : pas tout le marché ; ni liquidations, ni stops.
 */

export type BookState = 'SYNCED' | 'PARTIAL' | 'STALE' | 'UNAVAILABLE'

export interface OrderbookQuality {
  symbol: string
  venue: string
  window_hours: number
  expected_minutes: number
  written_minutes: number
  missing_minutes: number
  states: Record<BookState, number>
  synced_pct: number | null
  book_gaps: number
  trade_gaps: number
  trades: number
  spread_bps_median: number | null
  spread_bps_p95: number | null
  first_minute: number | null
  last_minute: number | null
  status: {
    state: BookState | string
    reason?: string
    collector_alive?: boolean
    resyncs?: number
    disconnects?: number
    last_error?: string | null
    mid?: number | null
  }
}

export async function getOrderbookQuality(symbol = 'BTCUSDT', hours = 24): Promise<OrderbookQuality> {
  const res = await fetch(
    `/api/engine/orderbook/${encodeURIComponent(symbol)}/quality?hours=${hours}`,
    { credentials: 'include' },
  )
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<OrderbookQuality>
}

const STATE_FR: Record<string, string> = {
  SYNCED: 'Synchronisé',
  PARTIAL: 'Partiel',
  STALE: 'Périmé',
  UNAVAILABLE: 'Indisponible',
}

export function bookStateLabel(state: string, reason?: string): string {
  if (reason === 'collector_down') return 'Collecteur arrêté'
  if (reason === 'not_collected') return 'Non collecté'
  return STATE_FR[state] ?? state
}

export function bookStateTone(state: string): 'green' | 'amber' | 'red' | 'gray' {
  if (state === 'SYNCED') return 'green'
  if (state === 'PARTIAL') return 'amber'
  if (state === 'STALE') return 'red'
  return 'gray'
}
