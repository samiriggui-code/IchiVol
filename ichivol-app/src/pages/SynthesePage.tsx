import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ActivityJournal } from '../components/ActivityJournal'
import { BrokerAccount, InvestmentCards } from '../components/BrokerAccount'
import { CostsPanel } from '../components/CostsPanel'
import { TestProgressPanel } from '../components/TestProgressPanel'
import { PaperCloseConfirmSheet } from '../components/PaperCloseConfirmSheet'
import { PaperTradeSheet } from '../components/PaperTradeSheet'
import {
  PortfolioChart,
  PORTFOLIO_RANGES,
  type PortfolioRange,
} from '../components/PortfolioChart'
import {
  closePaperPosition,
  getPaperActivity,
  getPaperOverview,
  getPaperReconcile,
  listPaperPositions,
  type PaperOrderRow,
  type PaperOverview,
  type PaperOverviewPosition,
  type PaperPosition,
  type PaperReconcileReport,
} from '../lib/paper'
import {
  assetName,
  directionWords,
  eur,
  exitReasonLabel,
  pct,
  signedEur,
} from '../lib/tradeStory'

type Tab = 'synthese' | 'historique'

function tone(v: number | null | undefined): string {
  if (v == null || v === 0) return ''
  return v > 0 ? 'up' : 'down'
}

type ResultFilter = 'all' | 'win' | 'loss' | 'flat'
type SourceFilter = 'all' | 'user_confirmed' | 'auto_watchlist'

const HISTORY_PAGE_SIZE = 25

function ClosedHistory({
  rows,
  onSelect,
}: {
  rows: PaperPosition[]
  onSelect: (p: PaperPosition) => void
}) {
  const [symbolQ, setSymbolQ] = useState('')
  const [resultFilter, setResultFilter] = useState<ResultFilter>('all')
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('all')
  const [page, setPage] = useState(0)

  const closedAll = useMemo(
    () =>
      rows
        .filter((p) => p.status === 'CLOSED')
        .sort(
          (a, b) =>
            +new Date(b.exit_time ?? b.entry_time) - +new Date(a.exit_time ?? a.entry_time),
        ),
    [rows],
  )

  const filtered = useMemo(() => {
    const q = symbolQ.trim().toLowerCase()
    return closedAll.filter((p) => {
      if (q) {
        const sym = p.symbol.toLowerCase()
        const label = assetName(p.symbol).toLowerCase()
        if (!sym.includes(q) && !label.includes(q) && !sym.replace(/usdt$/, '').includes(q)) {
          return false
        }
      }
      if (sourceFilter !== 'all' && p.source !== sourceFilter) return false
      if (resultFilter !== 'all') {
        const pnl = p.realized_pnl ?? (p.pnl_pct != null ? p.pnl_pct : null)
        if (pnl == null) return resultFilter === 'flat'
        if (resultFilter === 'win' && !(pnl > 0)) return false
        if (resultFilter === 'loss' && !(pnl < 0)) return false
        if (resultFilter === 'flat' && pnl !== 0) return false
      }
      return true
    })
  }, [closedAll, symbolQ, resultFilter, sourceFilter])

  const pageCount = Math.max(1, Math.ceil(filtered.length / HISTORY_PAGE_SIZE))
  const safePage = Math.min(page, pageCount - 1)
  const pageRows = filtered.slice(
    safePage * HISTORY_PAGE_SIZE,
    safePage * HISTORY_PAGE_SIZE + HISTORY_PAGE_SIZE,
  )
  const from = filtered.length === 0 ? 0 : safePage * HISTORY_PAGE_SIZE + 1
  const to = Math.min(filtered.length, (safePage + 1) * HISTORY_PAGE_SIZE)

  useEffect(() => {
    setPage(0)
  }, [symbolQ, resultFilter, sourceFilter])

  if (closedAll.length === 0) {
    return <p className="muted">Aucun trade terminé pour l’instant.</p>
  }

  return (
    <div className="synthese-history">
      <div className="synthese-history-filters" role="search">
        <label className="synthese-history-filter">
          <span>Symbole</span>
          <input
            type="search"
            value={symbolQ}
            onChange={(e) => setSymbolQ(e.target.value)}
            placeholder="NEAR, LINK…"
          />
        </label>
        <label className="synthese-history-filter">
          <span>Résultat</span>
          <select
            value={resultFilter}
            onChange={(e) => setResultFilter(e.target.value as ResultFilter)}
          >
            <option value="all">Tous</option>
            <option value="win">Gains</option>
            <option value="loss">Pertes</option>
            <option value="flat">Neutre / —</option>
          </select>
        </label>
        <label className="synthese-history-filter">
          <span>Source</span>
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value as SourceFilter)}
          >
            <option value="all">Toutes</option>
            <option value="auto_watchlist">Auto</option>
            <option value="user_confirmed">Manuel</option>
          </select>
        </label>
        {(symbolQ || resultFilter !== 'all' || sourceFilter !== 'all') && (
          <button
            type="button"
            className="ghost"
            onClick={() => {
              setSymbolQ('')
              setResultFilter('all')
              setSourceFilter('all')
            }}
          >
            Réinitialiser
          </button>
        )}
      </div>

      <p className="muted synthese-history-meta">
        {filtered.length === closedAll.length
          ? `${closedAll.length} trade${closedAll.length > 1 ? 's' : ''} · affichage ${from}–${to}`
          : `${filtered.length} / ${closedAll.length} · affichage ${from}–${to}`}
      </p>

      {filtered.length === 0 ? (
        <p className="muted">Aucun trade pour ces filtres.</p>
      ) : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Quand</th>
                  <th>Quoi</th>
                  <th>Investi</th>
                  <th>Résultat</th>
                  <th>Sortie</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {pageRows.map((p) => {
                  const dir = directionWords(p.direction)
                  const when = p.exit_time ?? p.entry_time
                  return (
                    <tr key={p.id}>
                      <td className="mono muted">
                        {new Date(when).toLocaleString('fr-FR', {
                          day: '2-digit',
                          month: '2-digit',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </td>
                      <td>
                        {dir.title} <strong>{assetName(p.symbol)}</strong>
                        <span className="muted"> · {p.timeframe}</span>
                      </td>
                      <td className="mono muted">{eur(p.notional)}</td>
                      <td className={`mono ${tone(p.realized_pnl ?? p.pnl_pct)}`}>
                        {p.realized_pnl != null ? signedEur(p.realized_pnl) : pct(p.pnl_pct, 2)}
                      </td>
                      <td>{exitReasonLabel(p.exit_reason)}</td>
                      <td>
                        <button type="button" className="ghost" onClick={() => onSelect(p)}>
                          Fiche
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="synthese-history-pager" role="navigation" aria-label="Pages historique">
            <button
              type="button"
              className="ghost"
              disabled={safePage <= 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              ← Précédent
            </button>
            <span className="muted mono">
              Page {safePage + 1} / {pageCount}
            </span>
            <button
              type="button"
              className="ghost"
              disabled={safePage >= pageCount - 1}
              onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
            >
              Suivant →
            </button>
          </div>
        </>
      )}
    </div>
  )
}

export function SynthesePage() {
  const [tab, setTab] = useState<Tab>('synthese')
  const [overview, setOverview] = useState<PaperOverview | null>(null)
  const [activity, setActivity] = useState<PaperOrderRow[]>([])
  const [history, setHistory] = useState<PaperPosition[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [closingId, setClosingId] = useState<string | null>(null)
  const [closeTarget, setCloseTarget] = useState<PaperOverviewPosition | null>(null)
  const [closeError, setCloseError] = useState<string | null>(null)
  const closeLock = useRef(false)
  const [sheetPos, setSheetPos] = useState<PaperPosition | null>(null)
  const [range, setRange] = useState<PortfolioRange>('1d')
  const [reconcile, setReconcile] = useState<PaperReconcileReport | null>(null)
  const [reconcileOpen, setReconcileOpen] = useState(false)
  const [reconcileLoading, setReconcileLoading] = useState(false)

  const reload = useCallback(async () => {
    setLoading(true)
    setError(null)
    setReconcileLoading(true)
    try {
      const [ov, act, mine, auto, rec] = await Promise.all([
        getPaperOverview('ICHIVOL_BASELINE_V1'),
        getPaperActivity('ICHIVOL_BASELINE_V1', 60).catch(() => [] as PaperOrderRow[]),
        listPaperPositions({ source: 'user_confirmed' }).catch(() => [] as PaperPosition[]),
        listPaperPositions({ source: 'auto_watchlist' }).catch(() => [] as PaperPosition[]),
        getPaperReconcile('ICHIVOL_BASELINE_V1').catch(() => null),
      ])
      setOverview(ov)
      setActivity(act)
      setHistory([...mine, ...auto])
      setReconcile(rec)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Impossible de charger le compte')
    } finally {
      setLoading(false)
      setReconcileLoading(false)
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  function requestClose(id: string) {
    const pos = overview?.positions.find((p) => p.id === id && p.status === 'OPEN') ?? null
    if (!pos) return
    setCloseError(null)
    setCloseTarget(pos)
  }

  async function executeClose() {
    if (!closeTarget || closeLock.current) return
    closeLock.current = true
    setClosingId(closeTarget.id)
    setCloseError(null)
    try {
      await closePaperPosition(closeTarget.id)
      setCloseTarget(null)
      await reload()
    } catch (e: unknown) {
      setCloseError(e instanceof Error ? e.message : 'Fermeture impossible')
    } finally {
      setClosingId(null)
      closeLock.current = false
    }
  }

  const closedCount = useMemo(
    () => history.filter((p) => p.status === 'CLOSED').length,
    [history],
  )

  const equity = overview?.account.equity ?? 0
  const initial = overview?.account.initial_cash ?? 0
  const up = equity >= initial
  const curvePts = overview?.equity_curve?.length ?? 0

  return (
    <div className="synthese-page">
      <header className="page-head market-head">
        <div className="market-head-copy">
          <h1>Synthèse</h1>
          <p className="muted">
            Compte virtuel baseline depuis sa création : liquidités, engagé, latent, réalisé.
            Positions techniques → <Link to="/app/portefeuille?tab=positions">Positions</Link>. Circuit auto →{' '}
            <Link to="/app/operations">Opérations</Link>.
          </p>
        </div>
        <div className="market-class-tabs" role="tablist" aria-label="Volets synthèse">
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'synthese'}
            className={tab === 'synthese' ? 'is-active' : undefined}
            onClick={() => setTab('synthese')}
          >
            Synthèse
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === 'historique'}
            className={tab === 'historique' ? 'is-active' : undefined}
            onClick={() => setTab('historique')}
          >
            Historique{closedCount > 0 ? ` (${closedCount})` : ''}
          </button>
          <button type="button" onClick={() => void reload()} disabled={loading}>
            {loading ? '…' : 'Actualiser'}
          </button>
        </div>
      </header>

      {error && (
        <div className="banner error" role="alert">
          {error}
        </div>
      )}

      {!overview && loading && <p className="muted">Chargement…</p>}

      {!overview && !loading && (
        <div className="panel">
          <p className="muted">
            Compte pas encore prêt. <Link to="/app/opportunites">Opportunités</Link>
          </p>
        </div>
      )}

      {overview && tab === 'synthese' && (
        <>
          <section className="panel synthese-account-panel">
            <header className="panel-head">
              <h2>Compte · {overview.portfolio.label}</h2>
              <button
                type="button"
                className={`ghost synthese-reconcile-badge${
                  reconcileLoading
                    ? ' is-checking'
                    : reconcile == null
                      ? ''
                      : reconcile.ok
                        ? ' is-ok'
                        : ' is-bad'
                }`}
                aria-expanded={reconcileOpen}
                disabled={reconcileLoading || reconcile == null}
                onClick={() => setReconcileOpen((v) => !v)}
                title="Audit comptable cash / ledger / ordres (lecture seule)"
              >
                {reconcileLoading
                  ? 'Comptabilité : …'
                  : reconcile == null
                    ? 'Comptabilité : —'
                    : reconcile.ok
                      ? 'Comptabilité : OK'
                      : `Comptabilité : ${reconcile.anomaly_count} anomalie${
                          reconcile.anomaly_count > 1 ? 's' : ''
                        }`}
              </button>
            </header>
            <div className="synthese-panel-body">
              {reconcileOpen && reconcile && (
                <div className="synthese-reconcile-detail" role="region" aria-label="Détail réconciliation">
                  <ul className="synthese-reconcile-list">
                    {reconcile.checks.map((c) => (
                      <li key={c.name} className={c.ok ? 'ok' : 'bad'}>
                        <strong>{c.name}</strong>
                        <span className="muted">
                          {c.ok ? 'OK' : `écart ${String(c.delta)}`}
                          {!c.ok && c.positions?.length ? ` · ${c.positions.length} position(s)` : ''}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <BrokerAccount overview={overview} />
            </div>
          </section>

          {overview.progress && (
            <section className="panel synthese-account-panel">
              <header className="panel-head">
                <h2>Progression du test en direct</h2>
                <span className="panel-meta">le système tourne seul — verdict quand l’échantillon est assez grand</span>
              </header>
              <div className="synthese-panel-body">
                <TestProgressPanel progress={overview.progress} />
              </div>
            </section>
          )}

          {overview.costs && (
            <section className="panel synthese-account-panel">
              <header className="panel-head">
                <h2>Bénéfice net et frais</h2>
                <span className="panel-meta">du brut au net, frais courtier inclus</span>
              </header>
              <div className="synthese-panel-body">
                <CostsPanel costs={overview.costs} />
              </div>
            </section>
          )}

          <section className="panel synthese-account-panel">
            <header className="panel-head">
              <h2>Investissements</h2>
              <span className="panel-meta">
                {overview.account.open_positions} ouvert
                {overview.account.open_positions > 1 ? 's' : ''}
                {overview.account.priced_positions != null &&
                  ` · ${overview.account.priced_positions} valorisée${overview.account.priced_positions > 1 ? 's' : ''}`}
                {(overview.account.incomplete_open ?? 0) > 0 &&
                  ` · ${overview.account.incomplete_open} incomplète${(overview.account.incomplete_open ?? 0) > 1 ? 's' : ''}`}
                {' · '}
                {eur(overview.account.invested)} engagé
              </span>
            </header>
            <div className="synthese-panel-body">
              <InvestmentCards
                overview={overview}
                onSelect={setSheetPos}
                onClose={requestClose}
                closingId={closingId}
              />
            </div>
          </section>

          <section className="chart-panel panel synthese-chart-panel">
            <header className="panel-head">
              <h2>
                <span className="market-pair-title">Valeur du portefeuille</span>
                <span className="market-pair-meta">€ · depuis création · {range}</span>
              </h2>
              <div className="panel-head-actions">
                <div className="tf-group" role="group" aria-label="Timeframe">
                  {PORTFOLIO_RANGES.map((tf) => (
                    <button
                      key={tf.id}
                      type="button"
                      className={tf.id === range ? 'is-active' : undefined}
                      onClick={() => setRange(tf.id)}
                    >
                      {tf.label}
                    </button>
                  ))}
                </div>
                <span className={`panel-meta ${up ? 'up' : 'down'}`}>
                  {curvePts > 0 ? eur(equity) : '…'}
                </span>
              </div>
            </header>

            <PortfolioChart
              points={overview.equity_curve}
              initial={overview.account.initial_cash}
              orders={activity}
              positions={overview.positions}
              range={range}
            />
          </section>

          <section className="panel">
            <header className="panel-head">
              <h2>Mouvements paper</h2>
              <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>
                Ordres du compte — pas la page{' '}
                <Link to="/app/operations">Opérations</Link> (circuit auto).
              </p>
            </header>
            <div className="synthese-panel-body">
              <ActivityJournal orders={activity} />
            </div>
          </section>
        </>
      )}

      {overview && tab === 'historique' && (
        <section className="panel">
          <header className="panel-head">
            <h2>Historique</h2>
          </header>
          <div className="synthese-panel-body">
            <ClosedHistory rows={history} onSelect={setSheetPos} />
          </div>
        </section>
      )}

      {sheetPos && <PaperTradeSheet position={sheetPos} onClose={() => setSheetPos(null)} />}

      {closeTarget && (
        <PaperCloseConfirmSheet
          position={closeTarget}
          confirming={closingId === closeTarget.id}
          error={closeError}
          onConfirm={() => void executeClose()}
          onCancel={() => {
            if (!closingId) {
              setCloseTarget(null)
              setCloseError(null)
            }
          }}
        />
      )}
    </div>
  )
}
