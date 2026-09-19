import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  closePaperPosition,
  getPaperPerformance,
  getPaperPortfolio,
  getShadowStats,
  listPaperPositions,
  type PaperPerformance,
  type PaperPortfolioSummary,
  type PaperPosition,
  type PaperSource,
  type ShadowStats,
} from '../lib/paper'

function fmtPct(v: number | null, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return `${(v * 100).toFixed(digits)}%`
}

function fmtNum(v: number | null, digits = 2): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return v.toFixed(digits)
}

function tone(v: number | null): string {
  if (v == null) return ''
  return v >= 0 ? 'up' : 'down'
}

function sourceLabel(s: string): string {
  if (s === 'auto_watchlist') return 'Auto screener'
  if (s === 'user_confirmed') return 'Mes confirms'
  return s
}

function ShadowCards({ stats }: { stats: ShadowStats | null }) {
  if (!stats) {
    return <p className="muted">ShadowBroker pas encore peuplé (filtres Structure/Fib/Ctx).</p>
  }
  const verdictLabel =
    stats.filter_verdict === 'filter_too_aggressive'
      ? 'Filtre trop agressif'
      : stats.filter_verdict === 'filter_helpful'
        ? 'Filtre utile'
        : stats.filter_verdict === 'inconclusive'
          ? 'Inconclusif'
          : 'Pas assez de closes (≥5)'
  return (
    <div className="paper-perf-block">
      <h3 className="subhead">ShadowBroker · counterfactuels</h3>
      <div className="paper-perf-grid">
        <div className="context-card">
          <span className="context-label">Ouvertes</span>
          <strong className="context-value">{stats.n_open}</strong>
        </div>
        <div className="context-card">
          <span className="context-label">Fermées</span>
          <strong className="context-value">{stats.n_closed}</strong>
        </div>
        <div className="context-card">
          <span className="context-label">Win rate shadow</span>
          <strong className="context-value">{fmtPct(stats.win_rate)}</strong>
        </div>
        <div className="context-card">
          <span className="context-label">Mean R (bloqués)</span>
          <strong className={`context-value ${tone(stats.mean_pnl_r)}`}>
            {fmtNum(stats.mean_pnl_r, 2)} R
          </strong>
        </div>
        <div className="context-card">
          <span className="context-label">Verdict filtre</span>
          <strong className="context-value">{verdictLabel}</strong>
        </div>
      </div>
      <p className="muted paper-perf-note">
        Hors cash. Si mean R &gt; 0 sur trades bloqués, le filtre a écarté des winners.
      </p>
    </div>
  )
}

function BrokerCards({ summary }: { summary: PaperPortfolioSummary | null }) {
  if (!summary) {
    return (
      <p className="muted">
        PaperBroker pas encore initialisé (migration / redémarrage moteur).
      </p>
    )
  }
  const { portfolio, performance: perf } = summary
  return (
    <div className="paper-perf-block">
      <h3 className="subhead">PaperBroker · {portfolio.code}</h3>
      <div className="paper-perf-grid">
        <div className="context-card">
          <span className="context-label">Capital initial</span>
          <strong className="context-value">{fmtNum(portfolio.initial_cash, 0)} €</strong>
        </div>
        <div className="context-card">
          <span className="context-label">Cash</span>
          <strong className="context-value">{fmtNum(portfolio.cash, 2)} €</strong>
        </div>
        <div className="context-card">
          <span className="context-label">Equity</span>
          <strong className={`context-value ${tone(perf.equity != null && portfolio.initial_cash ? perf.equity - portfolio.initial_cash : null)}`}>
            {fmtNum(perf.equity ?? null, 2)} €
          </strong>
        </div>
        <div className="context-card">
          <span className="context-label">PnL réalisé</span>
          <strong className={`context-value ${tone(portfolio.realized_pnl)}`}>
            {fmtNum(portfolio.realized_pnl, 2)} €
          </strong>
        </div>
        <div className="context-card">
          <span className="context-label">Max drawdown</span>
          <strong className="context-value">{fmtPct(perf.max_drawdown ?? null)}</strong>
        </div>
        <div className="context-card">
          <span className="context-label">Expectancy €</span>
          <strong className={`context-value ${tone(perf.expectancy_eur ?? null)}`}>
            {fmtNum(perf.expectancy_eur ?? null, 2)} €
          </strong>
        </div>
      </div>
      <p className="muted paper-perf-note">
        Risk 1% / TP 2R / max 5 positions · valuation {portfolio.valuation_mode} · jamais d’ordre réel.
      </p>
    </div>
  )
}

function PerfCards({ perf, title }: { perf: PaperPerformance | null; title: string }) {
  return (
    <div className="paper-perf-block">
      <h3 className="subhead">{title}</h3>
      {!perf ? (
        <p className="muted">Perf indisponible (redémarre le moteur si 404)…</p>
      ) : (
        <div className="paper-perf-grid">
          <div className="context-card">
            <span className="context-label">Ouvertes</span>
            <strong className="context-value">{perf.num_open_positions}</strong>
          </div>
          <div className="context-card">
            <span className="context-label">Fermées</span>
            <strong className="context-value">{perf.num_closed_trades}</strong>
          </div>
          <div className="context-card">
            <span className="context-label">Return composé</span>
            <strong className={`context-value ${tone(perf.total_return)}`}>
              {fmtPct(perf.total_return)}
            </strong>
          </div>
          <div className="context-card">
            <span className="context-label">Win rate</span>
            <strong className="context-value">{fmtPct(perf.win_rate)}</strong>
          </div>
          <div className="context-card">
            <span className="context-label">Profit factor</span>
            <strong className="context-value">{fmtNum(perf.profit_factor)}</strong>
          </div>
          <div className="context-card">
            <span className="context-label">Expectancy</span>
            <strong className={`context-value ${tone(perf.expectancy)}`}>
              {fmtPct(perf.expectancy)}
            </strong>
          </div>
        </div>
      )}
      <p className="muted paper-perf-note">
        Pas de Sharpe ici (closes irrégulières). Stats utiles dès qu’assez de trades fermés.
      </p>
    </div>
  )
}

function PositionsTable({
  rows,
  onClose,
  closingId,
}: {
  rows: PaperPosition[]
  onClose?: (id: string) => void
  closingId?: string | null
}) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Symbole</th>
            <th>Sens</th>
            <th>Statut</th>
            <th>Qty</th>
            <th>Entrée</th>
            <th>Prix</th>
            <th>Stop</th>
            <th>TP</th>
            <th>Sortie</th>
            <th>PnL</th>
            <th>Evidence</th>
            <th>Raison</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.id}>
              <td>
                <strong>{p.symbol.replace(/USDT$/i, '')}</strong>
                <span className="muted"> · {p.timeframe}</span>
              </td>
              <td>{p.direction}</td>
              <td>{p.status}</td>
              <td className="mono muted">
                {p.qty != null && Number.isFinite(p.qty) ? p.qty.toPrecision(4) : '—'}
              </td>
              <td className="mono muted">
                {new Date(p.entry_time).toLocaleString('fr-FR', {
                  day: '2-digit',
                  month: '2-digit',
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </td>
              <td className="mono">{p.entry_price.toPrecision(6)}</td>
              <td className="mono muted">
                {p.stop_price != null ? p.stop_price.toPrecision(6) : '—'}
              </td>
              <td className="mono muted">
                {p.take_profit_price != null ? p.take_profit_price.toPrecision(6) : '—'}
              </td>
              <td className="mono">{p.exit_price != null ? p.exit_price.toPrecision(6) : '—'}</td>
              <td className={`mono ${tone(p.pnl_pct)}`}>{fmtPct(p.pnl_pct, 2)}</td>
              <td>
                {p.evidence_id || p.decision_id ? (
                  <Link
                    to={`/app/decisions?symbol=${encodeURIComponent(p.symbol)}`}
                    className="paper-evidence-link"
                    title={p.evidence_id ?? p.decision_id ?? undefined}
                  >
                    Voir
                  </Link>
                ) : (
                  <span className="muted">—</span>
                )}
              </td>
              <td className="muted">{p.exit_reason ?? p.entry_decision}</td>
              <td>
                {p.status === 'OPEN' && onClose && (
                  <button
                    type="button"
                    className="ghost"
                    disabled={closingId === p.id}
                    onClick={() => onClose(p.id)}
                  >
                    Fermer
                  </button>
                )}
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={13} className="muted center">
                Aucune position.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

export function PaperPage() {
  const [tab, setTab] = useState<PaperSource>('user_confirmed')
  const [mineCache, setMineCache] = useState<PaperPosition[]>([])
  const [autoCache, setAutoCache] = useState<PaperPosition[]>([])
  const [perfMine, setPerfMine] = useState<PaperPerformance | null>(null)
  const [perfAuto, setPerfAuto] = useState<PaperPerformance | null>(null)
  const [broker, setBroker] = useState<PaperPortfolioSummary | null>(null)
  const [shadow, setShadow] = useState<ShadowStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [closingId, setClosingId] = useState<string | null>(null)

  const reload = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [mine, auto] = await Promise.all([
        listPaperPositions({ source: 'user_confirmed' }),
        listPaperPositions({ source: 'auto_watchlist' }),
      ])
      setMineCache(mine)
      setAutoCache(auto)
      const [pMine, pAuto, port, sh] = await Promise.all([
        getPaperPerformance({ source: 'user_confirmed' }).catch(() => null),
        getPaperPerformance({ source: 'auto_watchlist' }).catch(() => null),
        getPaperPortfolio('ICHIVOL_BASELINE_V1').catch(() => null),
        getShadowStats().catch(() => null),
      ])
      setPerfMine(pMine)
      setPerfAuto(pAuto)
      setBroker(port)
      setShadow(sh)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erreur paper')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  const positions = tab === 'user_confirmed' ? mineCache : autoCache

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

  return (
    <div className="paper-page">
      <header className="page-head">
        <h1>Paper</h1>
        <p className="muted">
          Positions <strong>virtuelles</strong> — PaperBroker 5 000 € (risk 1%, TP 2R). Ouvertes par
          le screener (auto) ou quand tu confirmes. Stop/TP + MFE/MAE quand l’ATR est dispo. Jamais
          d’ordre réel.
        </p>
      </header>

      {error && (
        <div className="banner error" role="alert">
          {error}
        </div>
      )}

      <section className="panel">
        <header className="panel-head">
          <h2>PaperBroker</h2>
          <button type="button" className="ghost" onClick={() => void reload()} disabled={loading}>
            {loading ? '…' : 'Actualiser'}
          </button>
        </header>
        <BrokerCards summary={broker} />
        <ShadowCards stats={shadow} />
      </section>

      <section className="panel">
        <header className="panel-head">
          <h2>Performance (% trades)</h2>
        </header>
        <div className="paper-perf-columns">
          <PerfCards perf={perfMine} title="Mes confirms" />
          <PerfCards perf={perfAuto} title="Auto screener" />
        </div>
      </section>

      <section className="panel">
        <header className="panel-head">
          <div className="panel-head-actions journal-tabs">
            <button
              type="button"
              className={tab === 'user_confirmed' ? 'is-active ghost' : 'ghost'}
              onClick={() => setTab('user_confirmed')}
            >
              Mes confirms
            </button>
            <button
              type="button"
              className={tab === 'auto_watchlist' ? 'is-active ghost' : 'ghost'}
              onClick={() => setTab('auto_watchlist')}
            >
              Auto screener
            </button>
          </div>
          <span className="panel-meta">{sourceLabel(tab)}</span>
        </header>

        {tab === 'user_confirmed' && positions.length === 0 && !loading && (
          <p className="muted paper-empty-hint">
            Vide — sur <Link to="/app/decisions">Décisions</Link>, ouvre le détail puis confirme
            l’ordre paper proposé (BUY/SELL portes).
          </p>
        )}

        <PositionsTable
          rows={positions}
          onClose={tab === 'user_confirmed' ? onClose : undefined}
          closingId={closingId}
        />
      </section>
    </div>
  )
}
