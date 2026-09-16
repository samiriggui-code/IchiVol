import { type FormEvent, useEffect, useMemo, useState } from 'react'
import {
  getBacktestComparison,
  type BacktestComparison,
  type ExperimentName,
} from '../lib/backtest'
import {
  CLASS_BLURBS,
  CLASS_LABELS,
  getEngineUniverse,
  type EngineAssetClass,
  type EngineInstrument,
} from '../lib/universe'

const EXPERIMENT_ORDER: ExperimentName[] = [
  'ICHIMOKU_ONLY',
  'ICHIMOKU_RVOL',
  'ICHIMOKU_RVOL_ENTRY_GATE',
  'PIPELINE',
]

const EXPERIMENT_LABELS: Record<ExperimentName, string> = {
  ICHIMOKU_ONLY: 'Ichimoku seul',
  ICHIMOKU_RVOL: 'Ichimoku + RVOL (continu)',
  ICHIMOKU_RVOL_ENTRY_GATE: 'Ichimoku + RVOL (entrée)',
  PIPELINE: 'Pipeline (portes)',
}

const TIMEFRAMES = ['15m', '1h', '4h', '1d']

const CLASS_ORDER: EngineAssetClass[] = [
  'crypto',
  'forex',
  'metal',
  'index',
  'equity',
  'energy',
]

function fmtPct(v: number | null, digits = 1): string {
  return v == null ? '—' : `${(v * 100).toFixed(digits)}%`
}

function fmtNum(v: number | null, digits = 2): string {
  return v == null || !Number.isFinite(v) ? '—' : v.toFixed(digits)
}

function toneClass(v: number | null): string {
  if (v == null) return ''
  return v >= 0 ? 'up' : 'down'
}

function friendlyBacktestError(raw: string): string {
  const lower = raw.toLowerCase()
  if (lower.includes('credit') || lower.includes('rate limit') || lower.includes('8 api')) {
    return 'Quota Twelve Data dépassé — attends ~1 min avant un autre backtest equity.'
  }
  if (lower.includes('provider_not_wired')) {
    return 'Instrument non câblé côté moteur (pas encore de provider).'
  }
  if (lower.includes('engine_unreachable') || lower.includes('502')) {
    return 'Moteur Python injoignable — vérifie que le service tourne (ichivol-app/engine).'
  }
  return raw
}

export function BacktestsPage() {
  const [instruments, setInstruments] = useState<EngineInstrument[]>([])
  const [universeError, setUniverseError] = useState<string | null>(null)
  const [marketClass, setMarketClass] = useState<EngineAssetClass>('crypto')
  const [symbol, setSymbol] = useState('BTCUSDT')
  const [timeframe, setTimeframe] = useState('1h')
  const [limit, setLimit] = useState(1000)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<BacktestComparison | null>(null)

  const visibleClasses = useMemo(() => {
    const present = new Set(
      instruments.filter((i) => i.wired).map((i) => i.asset_class),
    )
    return CLASS_ORDER.filter((c) => present.has(c))
  }, [instruments])

  const classInstruments = useMemo(
    () => instruments.filter((i) => i.asset_class === marketClass && i.wired),
    [instruments, marketClass],
  )

  const current = useMemo(
    () => instruments.find((i) => i.id === symbol) ?? null,
    [instruments, symbol],
  )

  useEffect(() => {
    let cancelled = false
    getEngineUniverse()
      .then((u) => {
        if (cancelled) return
        setInstruments(u.instruments)
        setUniverseError(null)
        setSymbol((prev) => {
          if (u.instruments.some((i) => i.id === prev && i.wired)) return prev
          const first = u.instruments.find((i) => i.wired)
          if (first) {
            setMarketClass(first.asset_class)
            return first.id
          }
          return prev
        })
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setUniverseError(err instanceof Error ? err.message : 'Univers moteur indisponible')
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  function selectClass(next: EngineAssetClass) {
    setMarketClass(next)
    const list = instruments.filter((i) => i.asset_class === next && i.wired)
    if (list[0] && !list.some((i) => i.id === symbol)) {
      setSymbol(list[0].id)
    }
    // Biquote ~100 bars/call (accumulation) ; Twelve Data = crédits — plafonner défaut
    if (next !== 'crypto' && limit > 500) setLimit(300)
  }

  function run(e?: FormEvent) {
    e?.preventDefault()
    const sym = symbol.trim().toUpperCase()
    if (!sym) return
    setLoading(true)
    setError(null)
    getBacktestComparison(sym, timeframe, limit)
      .then(setResult)
      .catch((err: unknown) =>
        setError(friendlyBacktestError(err instanceof Error ? err.message : 'Erreur de chargement')),
      )
      .finally(() => setLoading(false))
  }

  const best = result
    ? EXPERIMENT_ORDER.filter((name) => result.experiments[name]).reduce((a, b) => {
        const sa = result.experiments[a]?.metrics.sharpe ?? Number.NEGATIVE_INFINITY
        const sb = result.experiments[b]?.metrics.sharpe ?? Number.NEGATIVE_INFINITY
        return sb > sa ? b : a
      })
    : null

  const columns = result
    ? EXPERIMENT_ORDER.filter((name) => result.experiments[name])
    : EXPERIMENT_ORDER

  return (
    <div className="backtests-page">
      <header className="page-head market-head">
        <div className="market-head-copy">
          <h1>Backtests</h1>
          <p className="muted">
            Compare Ichimoku seul, Ichimoku+RVOL (continu / entrée) et le pipeline à portes sur le
            même historique réel. Même univers que Marché (instruments câblés). Aucune optimisation
            de paramètres — seuils RVOL/ATR depuis Settings. Pas un conseil financier.
          </p>
          {current && (
            <p className="muted">{CLASS_BLURBS[current.asset_class]}</p>
          )}
        </div>
        {visibleClasses.length > 0 && (
          <div className="market-class-tabs" role="tablist" aria-label="Classe d’actif">
            {visibleClasses.map((c) => (
              <button
                key={c}
                type="button"
                role="tab"
                aria-selected={c === marketClass}
                className={c === marketClass ? 'is-active' : undefined}
                onClick={() => selectClass(c)}
              >
                {CLASS_LABELS[c]}
              </button>
            ))}
          </div>
        )}
      </header>

      <section className="panel">
        <header className="panel-head">
          <h2>Paramètres</h2>
          {current?.provider && (
            <span className="panel-meta">
              {current.provider === 'binance'
                ? 'Binance Vision'
                : current.provider === 'twelve_data'
                  ? 'Twelve Data'
                  : current.provider === 'biquote'
                    ? 'Biquote'
                    : current.provider}
            </span>
          )}
        </header>
        <form className="settings-body controls" onSubmit={run}>
          <label>
            Instrument
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              disabled={!classInstruments.length}
            >
              {classInstruments.map((inst) => (
                <option key={inst.id} value={inst.id}>
                  {inst.label} · {inst.id}
                </option>
              ))}
            </select>
          </label>
          <label>
            Timeframe
            <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
              {TIMEFRAMES.map((tf) => (
                <option key={tf} value={tf}>
                  {tf}
                </option>
              ))}
            </select>
          </label>
          <label>
            Bougies
            <input
              type="number"
              min={100}
              max={1000}
              step={50}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
            />
          </label>
          <button type="submit" className="ghost" disabled={loading || !classInstruments.length}>
            {loading ? 'Calcul…' : 'Lancer le backtest'}
          </button>
        </form>
        {current?.provider === 'twelve_data' && (
          <p className="muted" style={{ padding: '0 1rem 1rem' }}>
            Equity Twelve Data : 1 backtest = crédits API — évite les rafales.
          </p>
        )}
        {current?.provider === 'biquote' && (
          <p className="muted" style={{ padding: '0 1rem 1rem' }}>
            Biquote plafonne ~100 barres/appel ; l’historique long s’accumule côté moteur — commence
            avec 300 bougies si le run est lent.
          </p>
        )}
      </section>

      {(error || universeError) && (
        <div className="banner error" role="alert">
          {error ?? universeError}
        </div>
      )}

      {result && (
        <section className="panel">
          <header className="panel-head">
            <h2>
              {result.symbol} · {result.timeframe}
            </h2>
            <span className="panel-meta">
              {result.experiments.ICHIMOKU_ONLY?.backtest.n_bars ?? 0} bougies
            </span>
          </header>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Métrique</th>
                  {columns.map((name) => (
                    <th key={name}>
                      {EXPERIMENT_LABELS[name]}
                      {name === best && <span className="panel-meta"> · meilleur Sharpe</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Trades</td>
                  {columns.map((name) => (
                    <td key={name} className="mono">
                      {result.experiments[name]?.metrics.num_trades ?? '—'}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>Exposition</td>
                  {columns.map((name) => (
                    <td key={name} className="mono">
                      {fmtPct(result.experiments[name]?.metrics.exposure ?? null)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>Rendement total</td>
                  {columns.map((name) => {
                    const v = result.experiments[name]?.metrics.total_return ?? null
                    return (
                      <td key={name} className={`mono ${toneClass(v)}`}>
                        {fmtPct(v)}
                      </td>
                    )
                  })}
                </tr>
                <tr>
                  <td>CAGR</td>
                  {columns.map((name) => (
                    <td key={name} className="mono">
                      {fmtPct(result.experiments[name]?.metrics.cagr ?? null)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>Sharpe</td>
                  {columns.map((name) => {
                    const v = result.experiments[name]?.metrics.sharpe ?? null
                    return (
                      <td key={name} className={`mono ${toneClass(v)}`}>
                        {fmtNum(v)}
                      </td>
                    )
                  })}
                </tr>
                <tr>
                  <td>Sortino</td>
                  {columns.map((name) => (
                    <td key={name} className="mono">
                      {fmtNum(result.experiments[name]?.metrics.sortino ?? null)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>Max drawdown</td>
                  {columns.map((name) => (
                    <td key={name} className="mono down">
                      {fmtPct(result.experiments[name]?.metrics.max_drawdown ?? null)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>Win rate</td>
                  {columns.map((name) => (
                    <td key={name} className="mono">
                      {fmtPct(result.experiments[name]?.metrics.win_rate ?? null)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>Profit factor</td>
                  {columns.map((name) => (
                    <td key={name} className="mono">
                      {fmtNum(result.experiments[name]?.metrics.profit_factor ?? null)}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>Expectancy / trade</td>
                  {columns.map((name) => (
                    <td key={name} className="mono">
                      {fmtPct(result.experiments[name]?.metrics.expectancy ?? null)}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      )}

      {!result && !loading && !error && (
        <div className="panel placeholder-page">
          <p className="muted">Choisis un instrument et lance un backtest pour voir la comparaison.</p>
        </div>
      )}
    </div>
  )
}
