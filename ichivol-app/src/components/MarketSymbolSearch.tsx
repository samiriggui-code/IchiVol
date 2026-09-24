/** Symbol search sheet / popover — screen 07 + desktop symbole ▾. */

import { useMemo } from 'react'
import { displaySymbol } from '../lib/markets'
import {
  CLASS_LABELS,
  type EngineAssetClass,
  type EngineInstrument,
} from '../lib/universe'
import type { ScreenerRow } from '../lib/types'

const CLASS_ORDER: EngineAssetClass[] = [
  'crypto',
  'forex',
  'metal',
  'index',
  'equity',
  'energy',
]

interface Props {
  open: boolean
  onClose: () => void
  instruments: EngineInstrument[]
  rows: ScreenerRow[]
  selected: string
  search: string
  onSearch: (q: string) => void
  classFilter: EngineAssetClass | null
  onClassFilter: (c: EngineAssetClass | null) => void
  onSelect: (symbol: string) => void
  /** Desktop popover under the symbol button vs mobile full sheet. */
  variant?: 'sheet' | 'popover'
}

export function MarketSymbolSearch({
  open,
  onClose,
  instruments,
  rows,
  selected,
  search,
  onSearch,
  classFilter,
  onClassFilter,
  onSelect,
  variant = 'sheet',
}: Props) {
  const priceBySym = useMemo(() => new Map(rows.map((r) => [r.symbol, r])), [rows])

  const classes = useMemo(() => {
    const present = new Set(instruments.map((i) => i.asset_class))
    return CLASS_ORDER.filter((c) => present.has(c))
  }, [instruments])

  const results = useMemo(() => {
    const q = search.trim().toLowerCase()
    let list = instruments
    if (classFilter) list = list.filter((i) => i.asset_class === classFilter)
    if (q) {
      list = list.filter((i) => {
        const hay = `${i.id} ${i.label} ${displaySymbol(i.id)}`.toLowerCase()
        return hay.includes(q)
      })
    }
    return list.slice(0, 80)
  }, [instruments, classFilter, search])

  if (!open) return null

  return (
    <div
      className={`mkt-search ${variant === 'sheet' ? 'is-sheet' : 'is-popover'}`}
      role="dialog"
      aria-label="Recherche symbole"
    >
      {variant === 'sheet' && (
        <button type="button" className="mkt-search-backdrop" aria-label="Fermer" onClick={onClose} />
      )}
      <div className="mkt-search-panel">
        <div className="mkt-search-bar">
          <input
            autoFocus
            type="search"
            placeholder="Rechercher un symbole…"
            value={search}
            onChange={(e) => onSearch(e.target.value)}
          />
          <button type="button" className="ghost" onClick={onClose}>
            Annuler
          </button>
        </div>
        <div className="mkt-search-classes" role="group" aria-label="Classe d’actif">
          <button
            type="button"
            className={classFilter == null ? 'is-active' : undefined}
            onClick={() => onClassFilter(null)}
          >
            Tous
          </button>
          {classes.map((c) => (
            <button
              key={c}
              type="button"
              className={classFilter === c ? 'is-active' : undefined}
              onClick={() => onClassFilter(c)}
            >
              {CLASS_LABELS[c]}
            </button>
          ))}
        </div>
        <ul className="mkt-search-results">
          {results.map((inst) => {
            const row = priceBySym.get(inst.id)
            const pct = row?.change24h
            return (
              <li key={inst.id}>
                <button
                  type="button"
                  className={`${inst.id === selected ? 'is-active' : ''}${inst.wired ? '' : ' is-unwired'}`}
                  disabled={!inst.wired}
                  onClick={() => {
                    if (!inst.wired) return
                    onSelect(inst.id)
                    onClose()
                  }}
                >
                  <span className="mkt-search-sym">
                    <strong>{displaySymbol(inst.id)}</strong>
                    <small>
                      {inst.label} · {CLASS_LABELS[inst.asset_class]}
                      {!inst.wired ? ' · non câblé' : ''}
                    </small>
                  </span>
                  <span className={`mono ${pct != null && pct >= 0 ? 'up' : 'down'}`}>
                    {pct == null || (pct === 0 && !row?.price)
                      ? '—'
                      : `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`}
                  </span>
                </button>
              </li>
            )
          })}
          {results.length === 0 && (
            <li className="muted center" style={{ padding: '1rem' }}>
              Aucun résultat
            </li>
          )}
        </ul>
      </div>
    </div>
  )
}
