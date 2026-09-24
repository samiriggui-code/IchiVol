/** Sortable Market watchlist — screens 01 / 04. */

import { useMemo } from 'react'
import { displaySymbol } from '../lib/markets'
import type { ContextBadge, ScreenerRow } from '../lib/types'
import type { SortDir, WatchlistSortKey } from '../lib/marketPrefs'
import { VerdictBadge } from './VerdictBadge'
import type { EngineAssetClass, EngineInstrument } from '../lib/universe'
import { CLASS_LABELS } from '../lib/universe'

export interface WatchlistProps {
  rows: ScreenerRow[]
  instruments: EngineInstrument[]
  loading: boolean
  selected: string
  onSelect: (symbol: string) => void
  sortKey: WatchlistSortKey
  sortDir: SortDir
  onSort: (key: WatchlistSortKey) => void
  classFilter: EngineAssetClass | null
  onClassFilter: (c: EngineAssetClass | null) => void
  contextActiveOnly?: boolean
  onContextActiveOnly?: (v: boolean) => void
  onRescan?: () => void
  scanLoading?: boolean
  showEngine?: boolean
  /** Hide Score column (mobile list). */
  hideScore?: boolean
}

const DESKTOP_COLS: { key: WatchlistSortKey; label: string }[] = [
  { key: 'symbol', label: 'Symbole' },
  { key: 'change24h', label: '%' },
  { key: 'rvol', label: 'RVOL' },
  { key: 'score', label: 'Score' },
  { key: 'context', label: 'Contexte' },
]

const MOBILE_COLS: { key: WatchlistSortKey; label: string }[] = [
  { key: 'symbol', label: 'Symbole' },
  { key: 'change24h', label: '%' },
  { key: 'rvol', label: 'RVOL' },
  { key: 'context', label: 'Contexte' },
]

function contextSortKey(badges: ContextBadge[] | undefined): number {
  if (!badges?.length) return 0
  return badges.filter((b) => !b.placeholder).length * 10 + badges.length
}

function hasLiveContext(row: ScreenerRow): boolean {
  return (row.context ?? []).some((b) => !b.placeholder)
}

function compareRows(a: ScreenerRow, b: ScreenerRow, key: WatchlistSortKey, dir: SortDir): number {
  const mul = dir === 'asc' ? 1 : -1
  let cmp = 0
  switch (key) {
    case 'symbol':
      cmp = a.symbol.localeCompare(b.symbol)
      break
    case 'change24h':
      cmp = a.change24h - b.change24h
      break
    case 'rvol':
      cmp = a.rvol - b.rvol
      break
    case 'bias':
      cmp = a.bias.localeCompare(b.bias)
      break
    case 'score':
      cmp = (a.engineConfidence ?? 0) - (b.engineConfidence ?? 0)
      break
    case 'context':
      cmp = contextSortKey(a.context) - contextSortKey(b.context)
      break
    default: {
      const _exhaustive: never = key
      void _exhaustive
      cmp = 0
    }
  }
  return cmp * mul
}

export function MarketWatchlist({
  rows,
  instruments,
  loading,
  selected,
  onSelect,
  sortKey,
  sortDir,
  onSort,
  classFilter,
  onClassFilter,
  contextActiveOnly = false,
  onContextActiveOnly,
  onRescan,
  scanLoading,
  showEngine = true,
  hideScore = false,
}: WatchlistProps) {
  const byId = useMemo(() => new Map(instruments.map((i) => [i.id, i])), [instruments])
  const cols = hideScore ? MOBILE_COLS : DESKTOP_COLS

  const classes = useMemo(() => {
    const present = new Set(instruments.map((i) => i.asset_class))
    return (['crypto', 'forex', 'metal', 'index', 'equity', 'energy'] as EngineAssetClass[]).filter(
      (c) => present.has(c),
    )
  }, [instruments])

  const filtered = useMemo(() => {
    let list = rows
    if (classFilter) {
      list = list.filter((r) => byId.get(r.symbol)?.asset_class === classFilter)
    }
    if (contextActiveOnly) {
      list = list.filter(hasLiveContext)
    }
    return [...list].sort((a, b) => compareRows(a, b, sortKey, sortDir))
  }, [rows, classFilter, contextActiveOnly, byId, sortKey, sortDir])

  return (
    <section className="market-watchlist">
      <div className="mw-toolbar">
        <div className="mw-class-filters" role="group" aria-label="Classe d’actif">
          <button
            type="button"
            className={classFilter == null && !contextActiveOnly ? 'is-active' : undefined}
            onClick={() => {
              onClassFilter(null)
              onContextActiveOnly?.(false)
            }}
          >
            Tous
          </button>
          {classes.map((c) => (
            <button
              key={c}
              type="button"
              className={classFilter === c ? 'is-active' : undefined}
              onClick={() => {
                onClassFilter(c)
                onContextActiveOnly?.(false)
              }}
            >
              {CLASS_LABELS[c]}
            </button>
          ))}
          {onContextActiveOnly && (
            <button
              type="button"
              className={contextActiveOnly ? 'is-active' : undefined}
              onClick={() => onContextActiveOnly(!contextActiveOnly)}
            >
              Contexte actif
            </button>
          )}
        </div>
        {onRescan && (
          <button
            type="button"
            className="ghost mw-rescan"
            disabled={scanLoading}
            onClick={onRescan}
          >
            {scanLoading ? 'Scan…' : 'Rescan'}
          </button>
        )}
      </div>
      <div className="mw-meta muted">
        {loading ? 'Scan…' : `${filtered.length} symbole${filtered.length === 1 ? '' : 's'}`}
      </div>
      <div className="table-wrap mw-table-wrap">
        <table className="mw-table">
          <thead>
            <tr>
              {cols.map((c) => (
                <th key={c.key}>
                  <button
                    type="button"
                    className={`mw-sort${sortKey === c.key ? ' is-active' : ''}`}
                    onClick={() => onSort(c.key)}
                  >
                    {c.label}
                    {sortKey === c.key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr
                key={r.symbol}
                className={r.symbol === selected ? 'is-active' : undefined}
                onClick={() => onSelect(r.symbol)}
              >
                <td>
                  <div className="sym">
                    <strong>{displaySymbol(r.symbol)}</strong>
                    <small>{byId.get(r.symbol)?.label ?? r.symbol}</small>
                  </div>
                </td>
                <td className={r.change24h >= 0 ? 'up' : 'down'}>
                  {r.change24h === 0 && !r.price
                    ? '—'
                    : `${r.change24h >= 0 ? '+' : ''}${r.change24h.toFixed(1)}%`}
                </td>
                <td className="mono">{r.rvol > 0 ? `${r.rvol.toFixed(2)}×` : '—'}</td>
                {!hideScore && (
                  <td>
                    {showEngine && r.engineDecision ? (
                      <VerdictBadge decision={r.engineDecision} pipeline={r.enginePipeline} />
                    ) : (
                      <span className="muted mono">
                        {r.engineConfidence != null ? r.engineConfidence.toFixed(2) : '—'}
                      </span>
                    )}
                  </td>
                )}
                <td>
                  <div className="mw-context">
                    {(r.context ?? [])
                      .filter((b) => !b.placeholder)
                      .map((b) => (
                        <span
                          key={`${b.kind}-${b.label}`}
                          className={`mw-badge mw-badge-${b.kind}`}
                          title={b.label}
                        >
                          {b.label}
                        </span>
                      ))}
                    {(r.context ?? []).filter((b) => !b.placeholder).length === 0 && (
                      <span className="muted">—</span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {!loading && filtered.length === 0 && (
              <tr>
                <td colSpan={cols.length} className="muted center">
                  Aucun symbole
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}

/** Build Contexte badges from screener pipeline + bias. Placeholders for T9f kept off the table. */
export function buildContextBadges(row: ScreenerRow): ContextBadge[] {
  const out: ContextBadge[] = []
  if (row.bias === 'bull') out.push({ kind: 'bias', label: 'Bias↑' })
  else if (row.bias === 'bear') out.push({ kind: 'bias', label: 'Bias↓' })

  const stages = row.enginePipeline?.stages ?? []
  const structure = stages.find((s) => s.id === 'structure')
  if (structure) {
    const codes = structure.codes ?? []
    const summary = (structure.summary ?? '').toUpperCase()
    if (codes.some((c) => c.includes('bos')) || summary.includes('BOS')) {
      const bull = summary.includes('BULL') || codes.some((c) => c.includes('bos_confirm'))
      out.push({ kind: 'bos', label: bull ? 'BOS↑' : 'BOS' })
    }
    if (
      codes.some((c) => c.includes('break') || c.includes('sr')) ||
      summary.includes('BREAK') ||
      summary.includes('S/R')
    ) {
      out.push({ kind: 'sr_break', label: 'S/R' })
    }
  }

  // T9f placeholders — reserved for filters later, not shown in Contexte column yet
  out.push({ kind: 'fvg', label: 'FVG', placeholder: true })
  out.push({ kind: 'fib', label: 'Fib', placeholder: true })
  out.push({ kind: 'choch', label: 'CHoCH', placeholder: true })
  return out
}
