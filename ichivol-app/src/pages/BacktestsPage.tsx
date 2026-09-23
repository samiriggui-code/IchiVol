import { type FormEvent, useEffect, useMemo, useState } from 'react'
import { BacktestRunsList } from '../components/BacktestRunsPanel'
import './BacktestsPage.css'
import {
  compareStoredRulesets,
  getAblation,
  getBacktestComparison,
  getBacktestEvidence,
  getEventStudy,
  getRegimeSlices,
  getRulesetEventStudy,
  getWalkForward,
  getWalkForwardOpt,
  listRulesets,
  listStoredExperiments,
  type AblationResult,
  type BacktestComparison,
  type BacktestEvidenceSummary,
  type EventStudyResult,
  type ExperimentName,
  type RegimeSlicesResult,
  type RulesetStudyResult,
  type RulesetSummary,
  type StoredExperimentSummary,
  type WalkForwardOptResult,
  type WalkForwardResult,
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

type LabTab = 'compare' | 'regimes' | 'experiments' | 'live'

const LAB_TABS: { id: LabTab; label: string }[] = [
  { id: 'compare', label: 'Compare' },
  { id: 'regimes', label: 'Regimes' },
  { id: 'experiments', label: 'Experiments' },
  { id: 'live', label: 'Live' },
]

const REGIME_FILTERS = ['ALL', 'GLOBAL', 'TRENDING', 'RANGING', 'HIGH_VOL', 'LOW_VOL', 'BULL', 'BEAR'] as const

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

function fmtWhen(iso: string | null): string {
  if (!iso) return 'jamais'
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return '—'
  const ageSec = (Date.now() - t) / 1000
  if (ageSec < 3600) return `il y a ${Math.max(1, Math.floor(ageSec / 60))} min`
  if (ageSec < 86400) return `il y a ${Math.floor(ageSec / 3600)} h`
  return `il y a ${Math.floor(ageSec / 86400)} j`
}

function StoredMetricsTable({
  rows,
  emptyHint,
  showRegime = false,
}: {
  rows: StoredExperimentSummary[]
  emptyHint: string
  showRegime?: boolean
}) {
  if (rows.length === 0) {
    return (
      <div className="panel placeholder-page">
        <p className="muted">{emptyHint}</p>
      </div>
    )
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Ruleset</th>
            {showRegime && <th>Régime</th>}
            <th>Trades</th>
            <th>WR</th>
            <th>PF</th>
            <th>Expect.</th>
            <th>Sharpe</th>
            <th>DD</th>
            <th>Quand</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((e) => (
            <tr key={e.experiment_id}>
              <td className="mono" style={{ fontSize: '0.8em' }}>
                {e.ruleset_id}
              </td>
              {showRegime && (
                <td className="mono" style={{ fontSize: '0.8em' }}>
                  {e.market_regime ?? '—'}
                </td>
              )}
              <td className="mono">{e.number_of_trades}</td>
              <td className="mono">{fmtPct(e.win_rate)}</td>
              <td className="mono">{fmtNum(e.profit_factor)}</td>
              <td className={`mono ${toneClass(e.expectancy)}`}>{fmtPct(e.expectancy)}</td>
              <td className="mono">{fmtNum(e.sharpe)}</td>
              <td className="mono down">{fmtPct(e.max_drawdown)}</td>
              <td className="mono" style={{ fontSize: '0.8em' }}>
                {e.created_at ? fmtWhen(e.created_at) : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
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
  const [eventStudy, setEventStudy] = useState<EventStudyResult | null>(null)
  const [rulesets, setRulesets] = useState<RulesetSummary[]>([])
  const [rulesetId, setRulesetId] = useState('IV_ICHIMOKU_RVOL_LONG_001')
  const [rulesetStudy, setRulesetStudy] = useState<RulesetStudyResult | null>(null)
  const [stored, setStored] = useState<StoredExperimentSummary[]>([])
  const [ablation, setAblation] = useState<AblationResult | null>(null)
  const [regimeSlices, setRegimeSlices] = useState<RegimeSlicesResult | null>(null)
  const [walkForward, setWalkForward] = useState<WalkForwardResult | null>(null)
  const [walkForwardOpt, setWalkForwardOpt] = useState<WalkForwardOptResult | null>(null)
  const [evidence, setEvidence] = useState<BacktestEvidenceSummary | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [labTab, setLabTab] = useState<LabTab>('compare')
  const [dbCompare, setDbCompare] = useState<StoredExperimentSummary[]>([])
  const [dbLoading, setDbLoading] = useState(false)
  const [dbError, setDbError] = useState<string | null>(null)
  const [regimeFilter, setRegimeFilter] = useState<(typeof REGIME_FILTERS)[number]>('ALL')

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
    getBacktestEvidence()
      .then((summary) => {
        if (!cancelled) setEvidence(summary)
      })
      .catch(() => {
        if (!cancelled) setEvidence(null)
      })
    listRulesets()
      .then((payload) => {
        if (cancelled) return
        setRulesets(payload.rulesets)
        if (payload.rulesets[0] && !payload.rulesets.some((r) => r.id === rulesetId)) {
          setRulesetId(payload.rulesets[0].id)
        }
      })
      .catch(() => {
        if (!cancelled) setRulesets([])
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (labTab === 'live') return
    const sym = symbol.trim().toUpperCase()
    if (!sym) return
    let cancelled = false
    setDbLoading(true)
    setDbError(null)
    const ids = rulesets.map((r) => r.id)
    const tasks: Promise<void>[] = [
      listStoredExperiments({
        symbol: sym,
        timeframe,
        limit: 50,
        market_regime: regimeFilter === 'ALL' ? undefined : regimeFilter,
      })
        .then((hist) => {
          if (!cancelled) setStored(hist.experiments)
        })
        .catch((err: unknown) => {
          if (!cancelled) {
            setStored([])
            setDbError(err instanceof Error ? err.message : String(err))
          }
        }),
    ]
    if (labTab === 'compare' && ids.length > 0) {
      tasks.push(
        compareStoredRulesets({
          symbol: sym,
          timeframe,
          ruleset_ids: ids,
          market_regime: 'GLOBAL',
        })
          .then((cmp) => {
            if (!cancelled) setDbCompare(cmp.experiments)
          })
          .catch((err: unknown) => {
            if (!cancelled) {
              setDbCompare([])
              setDbError(err instanceof Error ? err.message : String(err))
            }
          }),
      )
    }
    Promise.allSettled(tasks).finally(() => {
      if (!cancelled) setDbLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [labTab, symbol, timeframe, rulesets, regimeFilter])

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
    setEventStudy(null)
    setRulesetStudy(null)
    setAblation(null)
    setRegimeSlices(null)
    setWalkForward(null)
    setWalkForwardOpt(null)
    Promise.allSettled([
      getBacktestComparison(sym, timeframe, limit),
      getEventStudy(sym, timeframe, limit, 'PIPELINE'),
      getRulesetEventStudy(rulesetId, sym, timeframe, limit),
      getAblation(sym, timeframe, limit, false),
      getRegimeSlices(sym, timeframe, limit, rulesetId, false),
      getWalkForward(sym, timeframe, limit, rulesetId, { persist: false }),
      getWalkForwardOpt(sym, timeframe, limit, rulesetId, { persist: false }),
    ])
      .then((results) => {
        const [bt, es, rs, ab, rg, wf, wfo] = results
        const errors: string[] = []
        if (bt.status === 'fulfilled') setResult(bt.value)
        else errors.push(bt.reason instanceof Error ? bt.reason.message : String(bt.reason))
        if (es.status === 'fulfilled') setEventStudy(es.value)
        else errors.push(es.reason instanceof Error ? es.reason.message : String(es.reason))
        if (rs.status === 'fulfilled') setRulesetStudy(rs.value)
        else errors.push(rs.reason instanceof Error ? rs.reason.message : String(rs.reason))
        if (ab.status === 'fulfilled') setAblation(ab.value)
        if (rg.status === 'fulfilled') setRegimeSlices(rg.value)
        if (wf.status === 'fulfilled') setWalkForward(wf.value)
        else errors.push(wf.reason instanceof Error ? wf.reason.message : String(wf.reason))
        if (wfo.status === 'fulfilled') setWalkForwardOpt(wfo.value)
        else errors.push(wfo.reason instanceof Error ? wfo.reason.message : String(wfo.reason))

        if (bt.status === 'fulfilled') {
          listStoredExperiments({ symbol: sym, timeframe, limit: 10 })
            .then((hist) => setStored(hist.experiments))
            .catch(() => setStored([]))
        }
        if (errors.length && bt.status !== 'fulfilled') {
          setError(friendlyBacktestError(errors[0]))
        } else if (errors.length) {
          setError(friendlyBacktestError(`Partiel : ${errors[0]}`))
        }
      })
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

  const edge = evidence?.pipeline_beats_ichimoku_sharpe
  const edgeLabel = edge
    ? `${edge.beats}/${edge.compared}`
    : evidence?.total_rows
      ? 'en cours'
      : '—'

  return (
    <div className="backtests-page">
      <header className="page-head market-head">
        <div className="market-head-copy">
          <h1>Strategy Lab</h1>
          <p className="muted">
            Chiffres depuis la Performance DB (expériences persistées). Onglet{' '}
            <strong>Live</strong> = recalcul ponctuel (ne remplace pas la DB). Historique =
            backtests auto C1. Pas un conseil financier.
          </p>
          {current && (
            <p className="muted">{CLASS_BLURBS[current.asset_class]}</p>
          )}
        </div>
        <div className="bt-head-actions">
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
          <button
            type="button"
            className={`ghost${historyOpen ? ' is-active' : ''}`}
            aria-pressed={historyOpen}
            onClick={() => setHistoryOpen((o) => !o)}
          >
            Historique
          </button>
        </div>
      </header>

      <div className="market-class-tabs" role="tablist" aria-label="Strategy Lab" style={{ marginBottom: '0.75rem' }}>
        {LAB_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={labTab === tab.id}
            className={labTab === tab.id ? 'is-active' : undefined}
            onClick={() => setLabTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className={`bt-split${historyOpen ? ' is-open' : ''}`}>
        <div className="bt-main">

      {labTab !== 'live' && (
        <section className="panel">
          <header className="panel-head">
            <h2>
              {labTab === 'compare'
                ? 'Compare (DB)'
                : labTab === 'regimes'
                  ? 'Regimes (DB)'
                  : 'Experiments (DB)'}
            </h2>
            <span className="panel-meta">
              {symbol} · {timeframe}
              {dbLoading ? ' · chargement…' : ''}
            </span>
          </header>
          <form
            className="settings-body controls"
            onSubmit={(e) => {
              e.preventDefault()
            }}
          >
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
            {(labTab === 'regimes' || labTab === 'experiments') && (
              <label>
                Régime
                <select
                  value={regimeFilter}
                  onChange={(e) =>
                    setRegimeFilter(e.target.value as (typeof REGIME_FILTERS)[number])
                  }
                >
                  {REGIME_FILTERS.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </form>
          {dbError && (
            <p className="muted" style={{ padding: '0 1rem 0.75rem', color: 'var(--danger, #c44)' }}>
              {friendlyBacktestError(dbError)}
            </p>
          )}
          {universeError && (
            <p className="muted" style={{ padding: '0 1rem 0.75rem' }}>
              {universeError}
            </p>
          )}
          {labTab === 'compare' && (
            <StoredMetricsTable
              rows={dbCompare}
              emptyHint="Aucun run persisté pour ces rulesets (GLOBAL). Lance un Live avec persist, ou un event-study ruleset."
            />
          )}
          {(labTab === 'regimes' || labTab === 'experiments') && (
            <StoredMetricsTable
              rows={stored}
              showRegime
              emptyHint="Aucune expérience en Performance DB pour ce filtre."
            />
          )}
        </section>
      )}

      {labTab === 'live' && (
      <>
      <section className="panel">
        <header className="panel-head">
          <h2>Comparaison manuelle</h2>
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
          <label>
            Ruleset
            <select value={rulesetId} onChange={(e) => setRulesetId(e.target.value)}>
              {(rulesets.length
                ? rulesets
                : [{ id: rulesetId, description: rulesetId } as RulesetSummary]
              ).map((r) => (
                <option key={r.id} value={r.id}>
                  {r.id}
                </option>
              ))}
            </select>
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

      {eventStudy && (
        <section className="panel">
          <header className="panel-head">
            <h2>Event Study · {eventStudy.variant}</h2>
            <span className="panel-meta">
              {eventStudy.n_events} signaux · {eventStudy.n_bars} bougies · sans capital
            </span>
          </header>
          <p className="muted" style={{ padding: '0 1rem 0.75rem' }}>
            Après chaque entrée PIPELINE : retour ATR-normé à +N bougies, MFE/MAE, et % touchant
            +{eventStudy.r_multiple}R avant −{eventStudy.r_multiple}R (conservateur intra-barre).
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Horizon</th>
                  <th>n</th>
                  <th>Moyenne (ATR)</th>
                  <th>Médiane (ATR)</th>
                  <th>Moyenne %</th>
                </tr>
              </thead>
              <tbody>
                {eventStudy.horizon_stats.map((h) => (
                  <tr key={h.horizon}>
                    <td>+{h.horizon}</td>
                    <td className="mono">{h.n}</td>
                    <td className={`mono ${toneClass(h.mean_atr)}`}>{fmtNum(h.mean_atr)}</td>
                    <td className={`mono ${toneClass(h.median_atr)}`}>{fmtNum(h.median_atr)}</td>
                    <td className={`mono ${toneClass(h.mean_pct)}`}>{fmtPct(h.mean_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="table-wrap" style={{ marginTop: '0.75rem' }}>
            <table>
              <tbody>
                <tr>
                  <td>MFE moyen (ATR)</td>
                  <td className="mono up">{fmtNum(eventStudy.mean_mfe_atr)}</td>
                  <td>MAE moyen (ATR)</td>
                  <td className="mono down">{fmtNum(eventStudy.mean_mae_atr)}</td>
                </tr>
                <tr>
                  <td>+R avant −R</td>
                  <td className="mono">
                    {eventStudy.pct_hit_plus_r_before_minus_r == null
                      ? '—'
                      : fmtPct(eventStudy.pct_hit_plus_r_before_minus_r)}
                  </td>
                  <td>Résolus / signaux</td>
                  <td className="mono">
                    {eventStudy.n_resolved_r}/{eventStudy.n_events}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      )}

      {rulesetStudy && (
        <section className="panel">
          <header className="panel-head">
            <h2>Ruleset · {rulesetStudy.ruleset.id}</h2>
            <span className="panel-meta">
              {rulesetStudy.n_signals} signaux · {rulesetStudy.n_matching_bars} barres match ·{' '}
              {rulesetStudy.n_bars} bougies
            </span>
          </header>
          <p className="muted" style={{ padding: '0 1rem 0.75rem' }}>
            {rulesetStudy.ruleset.description || 'Hypothèse déclarative → Event Study (rising-edge).'}{' '}
            Direction {rulesetStudy.ruleset.direction} · stop {rulesetStudy.ruleset.stop_atr}R · target{' '}
            {rulesetStudy.ruleset.target_atr}R.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Horizon</th>
                  <th>n</th>
                  <th>Moyenne (ATR)</th>
                  <th>Médiane (ATR)</th>
                  <th>Moyenne %</th>
                </tr>
              </thead>
              <tbody>
                {rulesetStudy.event_study.horizon_stats.map((h) => (
                  <tr key={h.horizon}>
                    <td>+{h.horizon}</td>
                    <td className="mono">{h.n}</td>
                    <td className={`mono ${toneClass(h.mean_atr)}`}>{fmtNum(h.mean_atr)}</td>
                    <td className={`mono ${toneClass(h.median_atr)}`}>{fmtNum(h.median_atr)}</td>
                    <td className={`mono ${toneClass(h.mean_pct)}`}>{fmtPct(h.mean_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="table-wrap" style={{ marginTop: '0.75rem' }}>
            <table>
              <tbody>
                <tr>
                  <td>MFE moyen (ATR)</td>
                  <td className="mono up">{fmtNum(rulesetStudy.event_study.mean_mfe_atr)}</td>
                  <td>MAE moyen (ATR)</td>
                  <td className="mono down">{fmtNum(rulesetStudy.event_study.mean_mae_atr)}</td>
                </tr>
                <tr>
                  <td>+R avant −R</td>
                  <td className="mono">
                    {rulesetStudy.event_study.pct_hit_plus_r_before_minus_r == null
                      ? '—'
                      : fmtPct(rulesetStudy.event_study.pct_hit_plus_r_before_minus_r)}
                  </td>
                  <td>Conditions</td>
                  <td className="mono" style={{ fontSize: '0.85em' }}>
                    {Object.entries(rulesetStudy.ruleset.conditions)
                      .map(([k, v]) => `${k}=${String(v)}`)
                      .join(' · ')}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          {rulesetStudy.backtest && (
            <>
              <h3 style={{ padding: '1rem 1rem 0.5rem', margin: 0, fontSize: '1rem' }}>
                Backtest SL/TP (stop {rulesetStudy.ruleset.stop_atr}R · target{' '}
                {rulesetStudy.ruleset.target_atr}R)
              </h3>
              <div className="table-wrap">
                <table>
                  <tbody>
                    <tr>
                      <td>Trades</td>
                      <td className="mono">{rulesetStudy.backtest.metrics.num_trades}</td>
                      <td>Win rate</td>
                      <td className="mono">
                        {fmtPct(rulesetStudy.backtest.metrics.win_rate)}
                      </td>
                    </tr>
                    <tr>
                      <td>Profit factor</td>
                      <td className="mono">
                        {fmtNum(rulesetStudy.backtest.metrics.profit_factor)}
                      </td>
                      <td>Expectancy</td>
                      <td className={`mono ${toneClass(rulesetStudy.backtest.metrics.expectancy)}`}>
                        {fmtPct(rulesetStudy.backtest.metrics.expectancy)}
                      </td>
                    </tr>
                    <tr>
                      <td>Total return</td>
                      <td className={`mono ${toneClass(rulesetStudy.backtest.metrics.total_return)}`}>
                        {fmtPct(rulesetStudy.backtest.metrics.total_return)}
                      </td>
                      <td>Max DD</td>
                      <td className="mono down">
                        {fmtPct(rulesetStudy.backtest.metrics.max_drawdown)}
                      </td>
                    </tr>
                    <tr>
                      <td>Sharpe</td>
                      <td className="mono">{fmtNum(rulesetStudy.backtest.metrics.sharpe)}</td>
                      <td>Sorties</td>
                      <td className="mono" style={{ fontSize: '0.85em' }}>
                        {Object.entries(rulesetStudy.backtest.exit_reasons)
                          .map(([k, v]) => `${k}:${v}`)
                          .join(' · ') || '—'}
                        {rulesetStudy.backtest.n_skipped_in_position > 0
                          ? ` · skip ${rulesetStudy.backtest.n_skipped_in_position}`
                          : ''}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}

      {ablation && (
        <section className="panel">
          <header className="panel-head">
            <h2>Ablation · {ablation.mode}</h2>
            <span className="panel-meta">
              {ablation.steps.length} étapes · {ablation.n_bars} bougies · même fenêtre
            </span>
          </header>
          <p className="muted" style={{ padding: '0 1rem 0.75rem' }}>
            Escalier A→E (Ichimoku → +RVOL → +BOS → +ATR → +CMF). Un filtre ne se justifie que s’il
            améliore expectancy et/ou profit factor.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Étape</th>
                  <th>Signaux</th>
                  <th>Trades</th>
                  <th>WR</th>
                  <th>PF</th>
                  <th>Expect.</th>
                  <th>Sharpe</th>
                  <th>DD</th>
                </tr>
              </thead>
              <tbody>
                {ablation.steps.map((s) => {
                  const m = s.study.backtest?.metrics
                  return (
                    <tr key={s.label}>
                      <td className="mono">{s.label}</td>
                      <td className="mono">{s.n_signals}</td>
                      <td className="mono">{m?.num_trades ?? '—'}</td>
                      <td className="mono">{fmtPct(m?.win_rate ?? null)}</td>
                      <td className="mono">{fmtNum(m?.profit_factor ?? null)}</td>
                      <td className={`mono ${toneClass(m?.expectancy ?? null)}`}>
                        {fmtPct(m?.expectancy ?? null)}
                      </td>
                      <td className="mono">{fmtNum(m?.sharpe ?? null)}</td>
                      <td className="mono down">{fmtPct(m?.max_drawdown ?? null)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          {ablation.deltas.length > 0 && (
            <div className="table-wrap" style={{ marginTop: '0.75rem' }}>
              <table>
                <thead>
                  <tr>
                    <th>Transition</th>
                    <th>Ajout</th>
                    <th>Δ signaux</th>
                    <th>Δ expect.</th>
                    <th>Δ PF</th>
                    <th>Verdict</th>
                  </tr>
                </thead>
                <tbody>
                  {ablation.deltas.map((d) => (
                    <tr key={`${d.from_label}-${d.to_label}`}>
                      <td className="mono">
                        {d.from_label} → {d.to_label}
                      </td>
                      <td className="mono" style={{ fontSize: '0.8em' }}>
                        {d.added_conditions.join(', ') || '—'}
                      </td>
                      <td className="mono">{d.n_signals_delta}</td>
                      <td className={`mono ${toneClass(d.expectancy_delta)}`}>
                        {fmtPct(d.expectancy_delta)}
                      </td>
                      <td className={`mono ${toneClass(d.profit_factor_delta)}`}>
                        {fmtNum(d.profit_factor_delta)}
                      </td>
                      <td>{d.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {regimeSlices && (
        <section className="panel">
          <header className="panel-head">
            <h2>Régimes · {regimeSlices.ruleset.id}</h2>
            <span className="panel-meta">
              {regimeSlices.slices.length} slices · {regimeSlices.n_bars} bougies
            </span>
          </header>
          <p className="muted" style={{ padding: '0 1rem 0.75rem' }}>
            Tags causaux ADX+ATR au moment du signal. Un PF faible en GLOBAL mais fort en TRENDING
            = edge conditionnel au régime.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Régime</th>
                  <th>Bars</th>
                  <th>Signaux</th>
                  <th>Trades</th>
                  <th>WR</th>
                  <th>PF</th>
                  <th>Expect.</th>
                  <th>Sharpe</th>
                  <th>DD</th>
                </tr>
              </thead>
              <tbody>
                {regimeSlices.slices.map((s) => {
                  const m = s.study.backtest?.metrics
                  return (
                    <tr key={s.regime}>
                      <td className="mono">{s.regime}</td>
                      <td className="mono">{s.n_bars_in_regime}</td>
                      <td className="mono">{s.n_signals}</td>
                      <td className="mono">{m?.num_trades ?? '—'}</td>
                      <td className="mono">{fmtPct(m?.win_rate ?? null)}</td>
                      <td className="mono">{fmtNum(m?.profit_factor ?? null)}</td>
                      <td className={`mono ${toneClass(m?.expectancy ?? null)}`}>
                        {fmtPct(m?.expectancy ?? null)}
                      </td>
                      <td className="mono">{fmtNum(m?.sharpe ?? null)}</td>
                      <td className="mono down">{fmtPct(m?.max_drawdown ?? null)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {walkForward && (
        <section className="panel">
          <header className="panel-head">
            <h2>Walk-forward · {walkForward.mode}</h2>
            <span className="panel-meta">
              {walkForward.folds.length} folds · train {walkForward.train_bars} / test{' '}
              {walkForward.test_bars} · {walkForward.ruleset.id}
            </span>
          </header>
          <p className="muted" style={{ padding: '0 1rem 0.75rem' }}>
            Même ruleset sur fenêtres IS/OOS (pas d&apos;optimizer). L&apos;anti-overfitting se lit
            sur le résumé OOS — pas sur l&apos;IS.
          </p>
          <div
            className="metrics-strip"
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '1rem',
              padding: '0 1rem 0.75rem',
              fontFamily: 'var(--mono, monospace)',
              fontSize: '0.85rem',
            }}
          >
            <span>
              mean OOS expect.{' '}
              <strong className={toneClass(walkForward.oos_summary.mean_oos_expectancy)}>
                {fmtPct(walkForward.oos_summary.mean_oos_expectancy)}
              </strong>
            </span>
            <span>
              mean OOS PF{' '}
              <strong>{fmtNum(walkForward.oos_summary.mean_oos_profit_factor)}</strong>
            </span>
            <span>
              folds PF&gt;1{' '}
              <strong>{fmtPct(walkForward.oos_summary.pct_folds_pf_gt_1)}</strong>
            </span>
            <span>
              trades OOS <strong>{walkForward.oos_summary.total_oos_trades}</strong>
            </span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Fold</th>
                  <th>IS bars</th>
                  <th>OOS bars</th>
                  <th>OOS trades</th>
                  <th>OOS WR</th>
                  <th>OOS PF</th>
                  <th>OOS Expect.</th>
                  <th>OOS Sharpe</th>
                  <th>IS Expect.</th>
                </tr>
              </thead>
              <tbody>
                {walkForward.folds.map((f) => {
                  const oos = f.oos.backtest?.metrics
                  const is = f.is?.backtest?.metrics
                  return (
                    <tr key={f.fold_index}>
                      <td className="mono">{f.fold_index}</td>
                      <td className="mono">{f.train_bars}</td>
                      <td className="mono">{f.test_bars}</td>
                      <td className="mono">{oos?.num_trades ?? '—'}</td>
                      <td className="mono">{fmtPct(oos?.win_rate ?? null)}</td>
                      <td className="mono">{fmtNum(oos?.profit_factor ?? null)}</td>
                      <td className={`mono ${toneClass(oos?.expectancy ?? null)}`}>
                        {fmtPct(oos?.expectancy ?? null)}
                      </td>
                      <td className="mono">{fmtNum(oos?.sharpe ?? null)}</td>
                      <td className={`mono ${toneClass(is?.expectancy ?? null)}`}>
                        {fmtPct(is?.expectancy ?? null)}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {walkForwardOpt && (
        <section className="panel">
          <header className="panel-head">
            <h2>Walk-forward opt · {walkForwardOpt.objective}</h2>
            <span className="panel-meta">
              {walkForwardOpt.folds.length} folds · {walkForwardOpt.base_ruleset.id} · grid{' '}
              {Object.keys(walkForwardOpt.grid).join(', ')}
            </span>
          </header>
          <p className="muted" style={{ padding: '0 1rem 0.75rem' }}>
            Best params choisis sur IS, mesurés sur OOS. Si OOS s&apos;effondre alors que IS
            brille → overfitting. Stabilite des params = signal de robustesse.
          </p>
          <div
            className="metrics-strip"
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '1rem',
              padding: '0 1rem 0.75rem',
              fontFamily: 'var(--mono, monospace)',
              fontSize: '0.85rem',
            }}
          >
            <span>
              mean OOS expect.{' '}
              <strong className={toneClass(walkForwardOpt.oos_summary.mean_oos_expectancy)}>
                {fmtPct(walkForwardOpt.oos_summary.mean_oos_expectancy)}
              </strong>
            </span>
            <span>
              mean OOS PF{' '}
              <strong>{fmtNum(walkForwardOpt.oos_summary.mean_oos_profit_factor)}</strong>
            </span>
            <span>
              folds PF&gt;1{' '}
              <strong>{fmtPct(walkForwardOpt.oos_summary.pct_folds_pf_gt_1)}</strong>
            </span>
            <span>
              trades OOS <strong>{walkForwardOpt.oos_summary.total_oos_trades}</strong>
            </span>
          </div>
          {Object.keys(walkForwardOpt.param_stability.keys).length > 0 && (
            <p className="muted" style={{ padding: '0 1rem 0.75rem', fontSize: '0.85rem' }}>
              Stabilité ·{' '}
              {Object.entries(walkForwardOpt.param_stability.keys)
                .map(([k, v]) => `${k}=${v.mode} (${v.unique} uniques)`)
                .join(' · ')}
            </p>
          )}
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Fold</th>
                  <th>Best params (IS)</th>
                  <th>IS score</th>
                  <th>OOS trades</th>
                  <th>OOS PF</th>
                  <th>OOS Expect.</th>
                  <th>OOS Sharpe</th>
                </tr>
              </thead>
              <tbody>
                {walkForwardOpt.folds.map((f) => {
                  const oos = f.oos.backtest?.metrics
                  const paramsLabel =
                    Object.keys(f.best_params).length === 0
                      ? '(base)'
                      : Object.entries(f.best_params)
                          .map(([k, v]) => `${k}=${v}`)
                          .join(', ')
                  return (
                    <tr key={f.fold_index}>
                      <td className="mono">{f.fold_index}</td>
                      <td className="mono" style={{ fontSize: '0.75em' }}>
                        {paramsLabel}
                      </td>
                      <td className={`mono ${toneClass(f.is_score)}`}>{fmtNum(f.is_score)}</td>
                      <td className="mono">{oos?.num_trades ?? '—'}</td>
                      <td className="mono">{fmtNum(oos?.profit_factor ?? null)}</td>
                      <td className={`mono ${toneClass(oos?.expectancy ?? null)}`}>
                        {fmtPct(oos?.expectancy ?? null)}
                      </td>
                      <td className="mono">{fmtNum(oos?.sharpe ?? null)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {stored.length > 0 && (
        <section className="panel">
          <header className="panel-head">
            <h2>Performance DB</h2>
            <span className="panel-meta">{stored.length} expériences stockées</span>
          </header>
          <p className="muted" style={{ padding: '0 1rem 0.75rem' }}>
            Runs persistés (`strategy_lab_experiments`) — évite de tout recalculer. Ablation :
            compare les rulesets sur le même symbole/TF.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Ruleset</th>
                  <th>Trades</th>
                  <th>WR</th>
                  <th>PF</th>
                  <th>Expect.</th>
                  <th>Sharpe</th>
                  <th>DD</th>
                  <th>Quand</th>
                </tr>
              </thead>
              <tbody>
                {stored.map((e) => (
                  <tr key={e.experiment_id}>
                    <td className="mono" style={{ fontSize: '0.8em' }}>
                      {e.ruleset_id}
                    </td>
                    <td className="mono">{e.number_of_trades}</td>
                    <td className="mono">{fmtPct(e.win_rate)}</td>
                    <td className="mono">{fmtNum(e.profit_factor)}</td>
                    <td className={`mono ${toneClass(e.expectancy)}`}>{fmtPct(e.expectancy)}</td>
                    <td className="mono">{fmtNum(e.sharpe)}</td>
                    <td className="mono down">{fmtPct(e.max_drawdown)}</td>
                    <td className="mono" style={{ fontSize: '0.8em' }}>
                      {e.created_at ? fmtWhen(e.created_at) : '—'}
                    </td>
                  </tr>
                ))}
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
      </>
      )}
        </div>

        {historyOpen && (
          <aside className="panel decision-sheet bt-sheet" aria-label="Historique des backtests automatiques">
            <header className="panel-head decision-sheet-head">
              <div>
                <h2>Historique automatique</h2>
                <span className="panel-meta">backtests quotidiens · preuve C1</span>
              </div>
              <button type="button" className="ghost decision-sheet-close" onClick={() => setHistoryOpen(false)}>
                Fermer
              </button>
            </header>
            <div className="decision-sheet-scroll">
      <section className="overview-collect backtests-evidence" aria-label="Collecte automatique">
        <div className="panel overview-stat">
          <span className="overview-stat-label muted">Collecte auto (C1)</span>
          <strong className="mono">
            {evidence?.enabled === false
              ? 'off'
              : evidence
                ? `${evidence.runs_total ?? evidence.total_rows} ${evidence.runs_total != null ? 'lancements' : 'lignes'}`
                : '—'}
          </strong>
          <span className="overview-stat-meta muted">
            {evidence?.enabled === false
              ? 'Job désactivé (ENABLE_BACKTEST_EVIDENCE)'
              : evidence?.note
                ? evidence.note
                : `Dernier cycle ${fmtWhen(evidence?.last_run_at ?? null)}`}
            {evidence && evidence.distinct_days > 0
              ? ` · ${evidence.distinct_days} j d’historique · ${evidence.total_rows} résultats`
              : ''}
          </span>
        </div>
        <div className="panel overview-stat">
          <span className="overview-stat-label muted">PIPELINE &gt; Ichimoku (Sharpe)</span>
          <strong className="mono">{edgeLabel}</strong>
          <span className="overview-stat-meta muted">
            {edge
              ? `paires du dernier cycle · ${evidence?.latest_pairs ?? 0} paires scorées`
              : 'Indicateur descriptif — ne promeut pas Option C ni le live'}
          </span>
        </div>
      </section>
              <BacktestRunsList />
            </div>
          </aside>
        )}
      </div>
    </div>
  )
}
