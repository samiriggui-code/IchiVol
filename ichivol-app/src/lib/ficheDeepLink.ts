/** Deep-link fiches : `?fiche=decision:SYM:tf | position:id | run:id | agent:id`. */

export type FicheDecisionTab = 'synthese' | 'portes' | 'preuves' | 'plan' | 'historique'

export type FicheRef =
  | { kind: 'decision'; symbol: string; timeframe: string }
  | { kind: 'position'; id: string }
  | { kind: 'run'; id: string }
  | { kind: 'agent'; id: string }

const TAB_SET = new Set<FicheDecisionTab>([
  'synthese',
  'portes',
  'preuves',
  'plan',
  'historique',
])

export function normalizeFicheSymbol(raw: string): string {
  const s = raw.trim().toUpperCase().replace(/[^A-Z0-9]/g, '')
  if (!s) return ''
  if (/USDT$/.test(s) || /USD$/.test(s) || /EUR$/.test(s)) return s
  return `${s}USDT`
}

export function parseFicheParam(raw: string | null | undefined): FicheRef | null {
  if (!raw) return null
  const parts = raw.split(':').map((p) => p.trim()).filter(Boolean)
  if (parts.length < 2) return null
  const kind = parts[0].toLowerCase()
  if (kind === 'decision') {
    const symbol = normalizeFicheSymbol(parts[1] ?? '')
    if (!symbol) return null
    const timeframe = (parts[2] || '1h').toLowerCase()
    return { kind: 'decision', symbol, timeframe }
  }
  if (kind === 'position' || kind === 'run' || kind === 'agent') {
    const id = parts.slice(1).join(':').trim()
    if (!id) return null
    return { kind, id }
  }
  return null
}

export function serializeFicheParam(ref: FicheRef): string {
  if (ref.kind === 'decision') {
    return `decision:${ref.symbol}:${ref.timeframe || '1h'}`
  }
  return `${ref.kind}:${ref.id}`
}

export function parseFicheTab(raw: string | null | undefined): FicheDecisionTab {
  if (raw && TAB_SET.has(raw as FicheDecisionTab)) return raw as FicheDecisionTab
  return 'synthese'
}

export function ficheDecisionHref(
  symbol: string,
  timeframe = '1h',
  tab?: FicheDecisionTab,
): string {
  const fiche = serializeFicheParam({
    kind: 'decision',
    symbol: normalizeFicheSymbol(symbol),
    timeframe,
  })
  const q = new URLSearchParams()
  q.set('fiche', fiche)
  if (tab && tab !== 'synthese') q.set('tab', tab)
  return `?${q.toString()}`
}
