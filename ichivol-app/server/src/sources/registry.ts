export interface SourceEntry {
  id: string
  kind: 'kb' | 'live-api'
  title: string
  description: string
  baseUrl: string
  endpoints?: string[]
}

export const SOURCES: Record<string, SourceEntry> = {
  'binance-academy': {
    id: 'binance-academy',
    kind: 'kb',
    title: 'Binance Academy',
    description:
      'Articles de théorie trading/TA (Ichimoku, volume, breakout, support/résistance, stratégies) scrapés une fois et versionnés dans server/src/knowledge/docs.',
    baseUrl: 'https://www.binance.com/en/academy',
  },
  'binance-market-data': {
    id: 'binance-market-data',
    kind: 'live-api',
    title: 'Binance Market Data API',
    description:
      "Données de marché réelles (klines, ticker 24h) consommées par l'app via le proxy Vite /binance.",
    baseUrl: 'https://data-api.binance.vision',
    endpoints: ['/api/v3/klines', '/api/v3/ticker/24hr'],
  },
}
