import type { Interval } from './types'

/** Ouvre (ou focus) la fenêtre TV Marché avec symbole + timeframe courants. */
export function openMarketTvWindow(symbol: string, interval: Interval): void {
  const q = new URLSearchParams({ symbol, interval })
  const url = `/app/tv?${q.toString()}`
  // Sur téléphone : même onglet (pas de popup).
  const narrow =
    typeof window !== 'undefined' &&
    window.matchMedia('(max-width: 800px), (pointer: coarse) and (max-width: 1024px)').matches
  if (narrow) {
    window.location.assign(url)
    return
  }
  const features = [
    'popup=yes',
    'width=1480',
    'height=920',
    'left=40',
    'top=40',
  ].join(',')
  const win = window.open(url, 'ichivol-market-tv', features)
  if (!win) {
    window.location.assign(url)
    return
  }
  win.focus()
}
