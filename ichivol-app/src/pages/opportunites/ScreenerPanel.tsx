import { GateMatrix } from '../../components/GateMatrix'
import { VerdictBadge } from '../../components/VerdictBadge'
import { labelDecision } from '../../lib/decisionLabels'
import type { DecisionLabel, PipelineGateLabel, ScreenerDecisionRow } from '../../lib/decisions'
import type { EngineAssetClass } from '../../lib/universe'
import { CLASS_LABELS } from '../../lib/universe'
import {
  DECISION_FILTERS,
  fmtCacheAge,
  sortMarker,
  type ListView,
  type SortDir,
  type SortKey,
} from './shared'

export function ScreenerPanel({
  marketClass,
  listView,
  setListView,
  loading,
  visibleRows,
  classRows,
  cacheAge,
  onRefresh,
  gateFilter,
  setGateFilter,
  setActionableOnly,
  timeframe,
  setTimeframe,
  symbolQuery,
  setSymbolQuery,
  decisionFilter,
  setDecisionFilter,
  rvolMin,
  setRvolMin,
  actionableOnly,
  sheetOpen,
  selected,
  onSelect,
  instrumentLabel,
  onOpenPaperFromMatrix,
  paperBusySymbol,
  openPaperSymbols,
  paperMsg,
  error,
  sortKey,
  sortDir,
  toggleSort,
  colCount,
}: {
  marketClass: EngineAssetClass
  listView: ListView
  setListView: (v: ListView) => void
  loading: boolean
  visibleRows: ScreenerDecisionRow[]
  classRows: ScreenerDecisionRow[]
  cacheAge: number | null
  onRefresh: () => void
  gateFilter: 'all' | PipelineGateLabel
  setGateFilter: (v: 'all' | PipelineGateLabel) => void
  setActionableOnly: (v: boolean) => void
  timeframe: string
  setTimeframe: (v: string) => void
  symbolQuery: string
  setSymbolQuery: (v: string) => void
  decisionFilter: 'all' | DecisionLabel
  setDecisionFilter: (v: 'all' | DecisionLabel) => void
  rvolMin: string
  setRvolMin: (v: string) => void
  actionableOnly: boolean
  sheetOpen: boolean
  selected: string | null
  onSelect: (symbol: string) => void
  instrumentLabel: (id: string) => string
  onOpenPaperFromMatrix: (row: ScreenerDecisionRow) => void
  paperBusySymbol: string | null
  openPaperSymbols: ReadonlySet<string>
  paperMsg: string | null
  error: string | null
  sortKey: SortKey
  sortDir: SortDir
  toggleSort: (key: SortKey) => void
  colCount: number
}) {
  return (
    <section className="panel decisions-table-panel">
      <header className="panel-head">
        <h2>Screener · {CLASS_LABELS[marketClass]}</h2>
        <div className="panel-head-actions">
          <div className="decisions-view-tabs" role="tablist" aria-label="Vue screener">
            <button
              type="button"
              role="tab"
              aria-selected={listView === 'liste'}
              className={listView === 'liste' ? 'is-active' : undefined}
              onClick={() => setListView('liste')}
            >
              Liste
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={listView === 'matrice'}
              className={listView === 'matrice' ? 'is-active' : undefined}
              onClick={() => setListView('matrice')}
            >
              Matrice
            </button>
          </div>
          <span className="panel-meta">
            {loading
              ? 'scan…'
              : marketClass === 'equity'
                ? `${visibleRows.length} · détail au clic (pas de scan masse)`
                : `${visibleRows.length}/${classRows.length}${cacheAge != null ? ` · ${fmtCacheAge(cacheAge)}` : ''}`}
          </span>
          {marketClass !== 'equity' && (
            <button type="button" className="ghost" onClick={onRefresh} disabled={loading}>
              Rafraîchir
            </button>
          )}
        </div>
      </header>

      <div className="decisions-filters" role="search">
        <div className="opp-gate-segmented" role="group" aria-label="Filtrer par état Portes">
          {(
            [
              ['all', 'Tous'],
              ['BUY', 'Achat'],
              ['SELL', 'Vente'],
              ['WATCH', 'Surveillance'],
              ['NO_TRADE', 'No trade'],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={gateFilter === id ? 'is-active' : undefined}
              aria-pressed={gateFilter === id}
              onClick={() => {
                setGateFilter(id)
                if (id === 'BUY' || id === 'SELL') setActionableOnly(false)
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <label className="decisions-filter">
          <span className="muted">TF</span>
          <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
            <option value="15m">15m</option>
            <option value="1h">1h</option>
            <option value="4h">4h</option>
            <option value="1d">1d</option>
          </select>
        </label>
        <label className="decisions-filter">
          <span className="muted">Symbole</span>
          <input
            type="search"
            value={symbolQuery}
            onChange={(e) => setSymbolQuery(e.target.value)}
            placeholder="BTC, EUR, XAU…"
            autoComplete="off"
          />
        </label>
        <label className="decisions-filter">
          <span className="muted">Décision brute</span>
          <select
            value={decisionFilter}
            onChange={(e) => setDecisionFilter(e.target.value as 'all' | DecisionLabel)}
          >
            {DECISION_FILTERS.map((d) => (
              <option key={d} value={d}>
                {d === 'all' ? 'Toutes' : labelDecision(d)}
              </option>
            ))}
          </select>
        </label>
        <label className="decisions-filter">
          <span className="muted">RVOL ≥</span>
          <input
            type="number"
            min={0}
            step={0.1}
            value={rvolMin}
            onChange={(e) => setRvolMin(e.target.value)}
            placeholder="ex. 1.5"
          />
        </label>
        <label className="decisions-filter dec-filter-check">
          <input
            type="checkbox"
            checked={actionableOnly}
            onChange={(e) => setActionableOnly(e.target.checked)}
          />
          <span className="muted">Actionnables (Portes Achat/Vente)</span>
        </label>
        {(symbolQuery ||
          decisionFilter !== 'all' ||
          gateFilter !== 'all' ||
          rvolMin ||
          actionableOnly) && (
          <button
            type="button"
            className="ghost decisions-filter-reset"
            onClick={() => {
              setSymbolQuery('')
              setDecisionFilter('all')
              setGateFilter('all')
              setRvolMin('')
              setActionableOnly(false)
            }}
          >
            Reset
          </button>
        )}
      </div>

      <div className="table-wrap">
        {listView === 'matrice' ? (
          loading && visibleRows.length === 0 ? (
            <p className="muted center">Chargement du screener…</p>
          ) : (
            <>
              <GateMatrix
                rows={visibleRows}
                selected={selected}
                onSelect={onSelect}
                symbolLabel={instrumentLabel}
                onOpenPaper={onOpenPaperFromMatrix}
                paperBusySymbol={paperBusySymbol}
                openPaperSymbols={openPaperSymbols}
                emptyHint={
                  classRows.length === 0
                    ? marketClass === 'equity'
                      ? 'Aucune action câblée'
                      : 'Aucune ligne pour cette classe — clique Rafraîchir.'
                    : 'Aucun résultat pour ces filtres'
                }
              />
              {paperMsg && <p className="muted decisions-paper-msg">{paperMsg}</p>}
            </>
          )
        ) : (
          <table className="decisions-table">
            <thead>
              <tr>
                <th>
                  <button type="button" className="th-sort" onClick={() => toggleSort('symbol')}>
                    Symbole{sortMarker(sortKey === 'symbol', sortDir)}
                  </button>
                </th>
                <th>
                  <button
                    type="button"
                    className="th-sort"
                    onClick={() => toggleSort('decision')}
                    title="Tri sur le verdict Portes (pipeline) ; Brut = diagnostic Ichi+RVOL"
                  >
                    Portes{sortMarker(sortKey === 'decision', sortDir)}
                  </button>
                </th>
                {!sheetOpen && (
                  <th>
                    <button
                      type="button"
                      className="th-sort"
                      onClick={() => toggleSort('confidence')}
                    >
                      Confiance{sortMarker(sortKey === 'confidence', sortDir)}
                    </button>
                  </th>
                )}
                {!sheetOpen && (
                  <th>
                    <button
                      type="button"
                      className="th-sort"
                      onClick={() => toggleSort('ichimoku_score')}
                    >
                      Ichimoku{sortMarker(sortKey === 'ichimoku_score', sortDir)}
                    </button>
                  </th>
                )}
                <th>
                  <button type="button" className="th-sort" onClick={() => toggleSort('rvol')}>
                    RVOL{sortMarker(sortKey === 'rvol', sortDir)}
                  </button>
                </th>
                {!sheetOpen && (
                  <th>
                    <button type="button" className="th-sort" onClick={() => toggleSort('price')}>
                      Prix{sortMarker(sortKey === 'price', sortDir)}
                    </button>
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((r) => (
                <tr
                  key={r.symbol}
                  className={r.symbol === selected ? 'is-active' : undefined}
                  onClick={() => onSelect(r.symbol)}
                >
                  <td>
                    <strong title={r.symbol}>{instrumentLabel(r.symbol)}</strong>
                  </td>
                  <td>
                    <VerdictBadge decision={r.decision} pipeline={r.pipeline} />
                  </td>
                  {!sheetOpen && <td className="mono">{(r.confidence * 100).toFixed(0)}%</td>}
                  {!sheetOpen && (
                    <td className="mono">
                      {r.ichimoku_score != null ? r.ichimoku_score.toFixed(0) : '—'}
                    </td>
                  )}
                  <td className="mono">{r.rvol != null ? `${r.rvol.toFixed(2)}×` : '—'}</td>
                  {!sheetOpen && (
                    <td className="mono">
                      {r.price > 0 ? r.price.toFixed(r.price >= 100 ? 2 : 4) : '—'}
                    </td>
                  )}
                </tr>
              ))}
              {loading && visibleRows.length === 0 && (
                <tr>
                  <td colSpan={colCount} className="muted center">
                    Chargement du screener…
                  </td>
                </tr>
              )}
              {!loading && visibleRows.length === 0 && !error && (
                <tr>
                  <td colSpan={colCount} className="muted center">
                    {classRows.length === 0
                      ? marketClass === 'equity'
                        ? 'Aucune action câblée'
                        : 'Aucune ligne pour cette classe — clique Rafraîchir (le cache se reconstruit après un redémarrage moteur).'
                      : 'Aucun résultat pour ces filtres'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}
