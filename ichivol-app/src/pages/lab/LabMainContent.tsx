import { LabResearchPanel } from '../../components/LabResearchPanel'
import {
  EquitySparkline,
  EXPERIMENT_LABELS,
  IDEA_TO_PROOF_STEPS,
  REGIME_FILTERS,
  StoredMetricsTable,
  TIMEFRAMES,
  fmtNum,
  fmtPct,
  fmtWhen,
  friendlyBacktestError,
  metricsBasisLabel,
  toneClass,
} from './labShared'
import type { RulesetSummary } from '../../lib/backtest'
import type { useLabController } from './useLabController'

type Ctrl = ReturnType<typeof useLabController>

export function LabMainContent({ c }: { c: Ctrl }) {
  const universeError = c.universeError
  const symbol = c.symbol
  const setSymbol = c.setSymbol
  const timeframe = c.timeframe
  const setTimeframe = c.setTimeframe
  const limit = c.limit
  const setLimit = c.setLimit
  const loading = c.loading
  const error = c.error
  const result = c.result
  const eventStudy = c.eventStudy
  const rulesets = c.rulesets
  const rulesetId = c.rulesetId
  const setRulesetId = c.setRulesetId
  const rulesetStudy = c.rulesetStudy
  const stored = c.stored
  const ablation = c.ablation
  const regimeSlices = c.regimeSlices
  const walkForward = c.walkForward
  const walkForwardOpt = c.walkForwardOpt
  const labTab = c.labTab
  const dbCompare = c.dbCompare
  const dbLoading = c.dbLoading
  const dbError = c.dbError
  const regimeFilter = c.regimeFilter
  const setRegimeFilter = c.setRegimeFilter
  const classInstruments = c.classInstruments
  const current = c.current
  const run = c.run
  const best = c.best
  const columns = c.columns
  const equitySeries = c.equitySeries

  return (
    <>
      {labTab !== 'live' && labTab !== 'research' && (
        <section className="panel">
          <header className="panel-head">
            <h2>Expériences comparées</h2>
            <span className="panel-meta">
              {symbol} · {timeframe}
              {dbLoading ? ' · chargement…' : ''}
              {labTab === 'regimes' ? ' · régimes' : ''}
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

      {labTab === 'research' && (
        <LabResearchPanel
          symbol={symbol}
          setSymbol={setSymbol}
          timeframe={timeframe}
          setTimeframe={setTimeframe}
          rulesetId={rulesetId}
          setRulesetId={setRulesetId}
          limit={limit}
          setLimit={setLimit}
          classInstruments={classInstruments}
          rulesets={rulesets}
          universeError={universeError}
        />
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
            compare les rulesets sur le même symbole/TF. Bases :{' '}
            <strong>net_v1</strong> (ruleset), <strong>net_v2</strong> (engine/pipeline),{' '}
            <em>brut (ancien)</em> — ne jamais comparer sans le dire.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Ruleset</th>
                  <th>Base</th>
                  <th>Essais</th>
                  <th>Cx</th>
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
                      {e.hypothesis_id ? (
                        <div className="muted" style={{ fontSize: '0.85em' }}>
                          hyp:{e.hypothesis_id}
                        </div>
                      ) : null}
                    </td>
                    <td className="mono" style={{ fontSize: '0.75em' }}>
                      {metricsBasisLabel(e.metrics_basis)}
                    </td>
                    <td className="mono">{e.lineage_count ?? '—'}</td>
                    <td className="mono" title="complexité display-only (T10b)">
                      {e.complexity?.score ?? '—'}
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

      {equitySeries.length > 0 && (
        <section className="panel bt-trajectories">
          <header className="panel-head">
            <h2>Comparer les trajectoires</h2>
            <span className="panel-meta">
              {equitySeries.length} série{equitySeries.length > 1 ? 's' : ''}
            </span>
          </header>
          <div className="bt-pad">
            <EquitySparkline series={equitySeries} />
          </div>
        </section>
      )}

      <section className="panel bt-idea-proof" aria-label="De l’idée à la preuve">
        <header className="panel-head">
          <h2>De l’idée à la preuve</h2>
        </header>
        <div className="bt-proof-steps">
          {IDEA_TO_PROOF_STEPS.map((step) => (
            <div key={step.title} className="bt-proof-step">
              <b>{step.title}</b>
              <p>{step.body}</p>
            </div>
          ))}
        </div>
      </section>

    </>
  )
}
