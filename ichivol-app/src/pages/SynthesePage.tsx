import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ActivityJournal } from '../components/ActivityJournal'
import { BrokerAccount, InvestmentCards } from '../components/BrokerAccount'
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
  listPaperPositions,
  type PaperOrderRow,
  type PaperOverview,
  type PaperPosition,
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

function ClosedHistory({
  rows,
  onSelect,
}: {
  rows: PaperPosition[]
  onSelect: (p: PaperPosition) => void
}) {
  const closed = useMemo(
    () =>
      rows
        .filter((p) => p.status === 'CLOSED')
        .sort((a, b) => +new Date(b.exit_time ?? b.entry_time) - +new Date(a.exit_time ?? a.entry_time))
        .slice(0, 40),
    [rows],
  )

  if (closed.length === 0) {
    return (
      <p className="muted">
        Aucun trade terminé pour l’instant.
      </p>
    )
  }

  return (
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
          {closed.map((p) => {
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
  const [sheetPos, setSheetPos] = useState<PaperPosition | null>(null)
  const [range, setRange] = useState<PortfolioRange>('1d')

  const reload = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [ov, act, mine, auto] = await Promise.all([
        getPaperOverview('ICHIVOL_BASELINE_V1'),
        getPaperActivity('ICHIVOL_BASELINE_V1', 60).catch(() => [] as PaperOrderRow[]),
        listPaperPositions({ source: 'user_confirmed' }).catch(() => [] as PaperPosition[]),
        listPaperPositions({ source: 'auto_watchlist' }).catch(() => [] as PaperPosition[]),
      ])
      setOverview(ov)
      setActivity(act)
      setHistory([...mine, ...auto])
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Impossible de charger le compte')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  async function onClose(id: string) {
    setClosingId(id)
    try {
      await closePaperPosition(id)
      await reload()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Fermeture impossible')
    } finally {
      setClosingId(null)
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
      <header className="page-head">
        <h1>Synthèse</h1>
      </header>

      <div className="synthese-tabs journal-tabs" role="tablist" aria-label="Volets synthèse">
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'synthese'}
          className={tab === 'synthese' ? 'is-active ghost' : 'ghost'}
          onClick={() => setTab('synthese')}
        >
          Synthèse
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'historique'}
          className={tab === 'historique' ? 'is-active ghost' : 'ghost'}
          onClick={() => setTab('historique')}
        >
          Historique{closedCount > 0 ? ` (${closedCount})` : ''}
        </button>
        <button type="button" className="ghost" onClick={() => void reload()} disabled={loading}>
          {loading ? '…' : 'Actualiser'}
        </button>
      </div>

      {error && (
        <div className="banner error" role="alert">
          {error}
        </div>
      )}

      {!overview && loading && <p className="muted">Chargement…</p>}

      {!overview && !loading && (
        <div className="panel">
          <p className="muted">
            Compte pas encore prêt.{' '}
            <Link to="/app/decisions">Décisions</Link>
          </p>
        </div>
      )}

      {overview && tab === 'synthese' && (
        <>
          <section className="panel synthese-strip">
            <BrokerAccount overview={overview} />
          </section>

          <section className="panel synthese-strip">
            <header className="panel-head">
              <h2>Investissements</h2>
              <span className="panel-meta">
                {overview.account.open_positions} · {eur(overview.account.invested)}
              </span>
            </header>
            <InvestmentCards
              overview={overview}
              onSelect={setSheetPos}
              onClose={onClose}
              closingId={closingId}
            />
          </section>

          <section className="chart-panel panel synthese-chart-panel">
            <header className="panel-head">
              <h2>
                <span className="market-pair-title">Capital</span>
                <span className="market-pair-meta">portefeuille · {range}</span>
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
              <h2>Activité</h2>
            </header>
            <ActivityJournal orders={activity} />
          </section>
        </>
      )}

      {overview && tab === 'historique' && (
        <section className="panel">
          <header className="panel-head">
            <h2>Historique</h2>
          </header>
          <ClosedHistory rows={history} onSelect={setSheetPos} />
        </section>
      )}

      {sheetPos && <PaperTradeSheet position={sheetPos} onClose={() => setSheetPos(null)} />}
    </div>
  )
}
