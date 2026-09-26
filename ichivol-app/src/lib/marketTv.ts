import type { Interval } from './types'

/** Ouvre (ou focus) la fenêtre TV Marché avec symbole + timeframe courants. */
export function openMarketTvWindow(symbol: string, interval: Interval): void {
  const q = new URLSearchParams({ symbol, interval })
  const url = `/app/tv?${q.toString()}`
  const features = [
    'popup=yes',
    'width=1480',
    'height=920',
    'left=40',
    'top=40',
  ].join(',')
  const win = window.open(url, 'ichivol-market-tv', features)
  win?.focus()
}
