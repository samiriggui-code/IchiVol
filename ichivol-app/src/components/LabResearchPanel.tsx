/** Strategy Lab — Research tab (T5b / T6 / T7 / Researcher). Observation only. */

import { useEffect, useState } from 'react'
import {
  buildAuditReport,
  compareFamilyWeights,
  listFamilyWeightProfiles,
  proposeExperimentPlan,
  runFamilyWeightsStudy,
  runMonteCarlo,
  type AuditReportResult,
  type ExperimentPlanResult,
  type FamilyWeightCompareResult,
  type FamilyWeightProfilesResult,
  type FamilyWeightStudyResult,
  type MonteCarloResult,
} from '../lib/labResearch'
import type { RulesetSummary } from '../lib/backtest'
import type { EngineInstrument } from '../lib/universe'

const TIMEFRAMES = ['15m', '1h', '4h', '1d']

function fmtPct(v: number | null | undefined, digits = 1): string {
  return v == null || !Number.isFinite(v) ? '—' : `${(v * 100).toFixed(digits)}%`
}

function fmtNum(v: number | null | undefined, digits = 3): string {
  return v == null || !Number.isFinite(v) ? '—' : v.toFixed(digits)
}

function friendlyError(raw: string): string {
  const lower = raw.toLowerCase()
  if (lower.includes('no_trades')) return 'Aucun trade sur cette fenêtre — change ruleset / limite.'
  if (lower.includes('provider_not_wired')) return 'Instrument non câblé côté moteur.'
  if (lower.includes('engine_unreachable') || lower.includes('502')) {
    return 'Moteur Python injoignable.'
  }
  return raw
}

type Props = {
  symbol: string
  setSymbol: (s: string) => void
  timeframe: string
  setTimeframe: (tf: string) => void
  rulesetId: string
  setRulesetId: (id: string) => void
  limit: number
  setLimit: (n: number) => void
  classInstruments: EngineInstrument[]
  rulesets: RulesetSummary[]
  universeError: string | null
}

export function LabResearchPanel({
  symbol,
  setSymbol,
  timeframe,
  setTimeframe,
  rulesetId,
  setRulesetId,
  limit,
  setLimit,
  classInstruments,
  rulesets,
  universeError,
}: Props) {
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [profiles, setProfiles] = useState<FamilyWeightProfilesResult | null>(null)
  const [compare, setCompare] = useState<FamilyWeightCompareResult | null>(null)
  const [study, setStudy] = useState<FamilyWeightStudyResult | null>(null)
  const [audit, setAudit] = useState<AuditReportResult | null>(null)
  const [mc, setMc] = useState<MonteCarloResult | null>(null)
  const [plan, setPlan] = useState<ExperimentPlanResult | null>(null)
  const [tradeIndex, setTradeIndex] = useState(0)

  useEffect(() => {
    let cancelled = false
    listFamilyWeightProfiles()
      .then((p) => {
        if (!cancelled) setProfiles(p)
      })
      .catch(() => {
        /* catalog optional until engine up */
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function run(label: string, fn: () => Promise<void>) {
    setBusy(label)
    setError(null)
    try {
      await fn()
    } catch (e) {
      setError(friendlyError(e instanceof Error ? e.message : String(e)))
    } finally {
      setBusy(null)
    }
  }

  return (
    <>
      <section className="panel">
        <header className="panel-head">
          <h2>Research (observation)</h2>
          <span className="panel-meta">T5b · T6 · T7 · Researcher — jamais auto-appliqué</span>
        </header>
        <p className="muted" style={{ padding: '0 1rem 0.5rem' }}>
          Panneaux lecture seule sur les modules déjà livrés. Les hypothèses et plans restent{' '}
          <code>proposed</code> — pas de changement de score live ni de gate.
        </p>
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
          <label>
            Bougies
            <input
              type="number"
              min={100}
              max={2000}
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
          <label>
            Trade #
            <input
              type="number"
              min={0}
              max={99}
              value={tradeIndex}
              onChange={(e) => setTradeIndex(Number(e.target.value))}
            />
          </label>
        </form>
        {(error || universeError) && (
          <p
            className="muted"
            style={{ padding: '0 1rem 0.75rem', color: 'var(--danger, #c44)' }}
            role="alert"
          >
            {error ?? universeError}
          </p>
        )}
        <div className="lab-research-actions" style={{ padding: '0 1rem 1rem', display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
          <button
            type="button"
            className="ghost"
            disabled={!!busy || !classInstruments.length}
            onClick={() =>
              run('compare', async () => {
                setCompare(await compareFamilyWeights(symbol, timeframe, Math.min(limit, 500)))
              })
            }
          >
            {busy === 'compare' ? 'Compare…' : 'Comparer poids'}
          </button>
          <button
            type="button"
            className="ghost"
            disabled={!!busy || !classInstruments.length}
            onClick={() =>
              run('study', async () => {
                setStudy(await runFamilyWeightsStudy(symbol, timeframe, limit))
              })
            }
          >
            {busy === 'study' ? 'Étude…' : 'Étude historique'}
          </button>
          <button
            type="button"
            className="ghost"
            disabled={!!busy || !classInstruments.length}
            onClick={() =>
              run('audit', async () => {
                const rep = await buildAuditReport({
                  symbol,
                  timeframe,
                  limit,
                  rulesetId,
                  tradeIndex,
                })
                setAudit(rep)
                setPlan(null)
              })
            }
          >
            {busy === 'audit' ? 'Audit…' : 'Audit trade'}
          </button>
          <button
            type="button"
            className="ghost"
            disabled={!!busy || !audit}
            onClick={() =>
              run('plan', async () => {
                if (!audit) return
                setPlan(await proposeExperimentPlan(audit))
              })
            }
          >
            {busy === 'plan' ? 'Plan…' : 'Plan d’expérience'}
          </button>
          <button
            type="button"
            className="ghost"
            disabled={!!busy || !classInstruments.length}
            onClick={() =>
              run('mc', async () => {
                setMc(
                  await runMonteCarlo({
                    symbol,
                    timeframe,
                    limit,
                    rulesetId,
                  }),
                )
              })
            }
          >
            {busy === 'mc' ? 'Monte Carlo…' : 'Monte Carlo'}
          </button>
        </div>
      </section>

      {profiles && (
        <section className="panel">
          <header className="panel-head">
            <h2>Profils poids (catalogue)</h2>
            <span className="panel-meta">{profiles.profiles.length} profils</span>
          </header>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Id</th>
                  <th>Label</th>
                  <th>Version</th>
                </tr>
              </thead>
              <tbody>
                {profiles.profiles.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <code>{p.id}</code>
                    </td>
                    <td>{p.label}</td>
                    <td className="muted">{p.version}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted" style={{ padding: '0.5rem 1rem 1rem' }}>
            {profiles.disclaimer}
          </p>
        </section>
      )}

      {compare && (
        <section className="panel">
          <header className="panel-head">
            <h2>Compare poids</h2>
            <span className="panel-meta">
              {compare.symbol} · {compare.decision} · conf {fmtPct(compare.confidence)}
            </span>
          </header>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Profil</th>
                  <th>Support</th>
                  <th>Version</th>
                </tr>
              </thead>
              <tbody>
                {Object.values(compare.profiles)
                  .sort((a, b) => b.weighted_support - a.weighted_support)
                  .map((p) => (
                    <tr key={p.id}>
                      <td>{p.label}</td>
                      <td>{fmtNum(p.weighted_support)}</td>
                      <td className="muted">{p.version}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          <p className="muted" style={{ padding: '0.5rem 1rem 1rem' }}>
            {compare.disclaimer}
          </p>
        </section>
      )}

      {study && (
        <section className="panel">
          <header className="panel-head">
            <h2>Étude historique</h2>
            <span className="panel-meta">
              {study.n_signals} signaux · {study.n_bars} barres
            </span>
          </header>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Profil</th>
                  <th>N</th>
                  <th>Support moy.</th>
                </tr>
              </thead>
              <tbody>
                {study.aggregates.map((a) => (
                  <tr key={a.profile_id}>
                    <td>
                      <code>{a.profile_id}</code>
                    </td>
                    <td>{a.n_signals}</td>
                    <td>{fmtNum(a.mean_support)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted" style={{ padding: '0.5rem 1rem 1rem' }}>
            {study.disclaimer}
          </p>
        </section>
      )}

      {audit && (
        <section className="panel">
          <header className="panel-head">
            <h2>AuditReport</h2>
            <span className="panel-meta">
              trade #{audit.trade_index}
              {audit.n_trades != null ? ` / ${audit.n_trades}` : ''} · {audit.ruleset_id ?? '—'}
            </span>
          </header>
          <div style={{ padding: '0 1rem 0.75rem' }}>
            <p className="muted">
              worked: {audit.what_worked.length ? audit.what_worked.join(', ') : '—'}
            </p>
            <p className="muted">
              failed: {audit.what_failed.length ? audit.what_failed.join(', ') : '—'}
            </p>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Hypothèse</th>
                  <th>Status</th>
                  <th>Suggestion</th>
                </tr>
              </thead>
              <tbody>
                {audit.hypotheses.map((h) => (
                  <tr key={h.id}>
                    <td>
                      <code>{h.id}</code>
                      <div className="muted">{h.statement}</div>
                    </td>
                    <td>{h.status}</td>
                    <td className="muted">{h.suggested_experiment}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted" style={{ padding: '0.5rem 1rem 1rem' }}>
            {audit.disclaimer}
          </p>
        </section>
      )}

      {plan && (
        <section className="panel">
          <header className="panel-head">
            <h2>Plan d’expérience</h2>
            <span className="panel-meta">{plan.status} · {plan.steps.length} steps</span>
          </header>
          <ol style={{ padding: '0 1.5rem 0.75rem', margin: 0 }}>
            {plan.steps.map((s, i) => (
              <li key={`${s.tool}-${i}`} style={{ marginBottom: '0.4rem' }}>
                <code>{s.tool}</code> — {s.purpose}
              </li>
            ))}
          </ol>
          <p className="muted" style={{ padding: '0.5rem 1rem 1rem' }}>
            {plan.disclaimer}
          </p>
        </section>
      )}

      {mc && (
        <section className="panel">
          <header className="panel-head">
            <h2>Monte Carlo</h2>
            <span className="panel-meta">
              {mc.n_trades} trades · {mc.n_paths} paths ·{' '}
              {mc.sufficient ? 'suffisant' : 'échantillon insuffisant'}
            </span>
          </header>
          <div className="table-wrap">
            <table>
              <tbody>
                <tr>
                  <th>Risk of ruin</th>
                  <td>{fmtPct(mc.risk_of_ruin)}</td>
                </tr>
                <tr>
                  <th>Equity médiane</th>
                  <td>{fmtNum(mc.p50_final_equity)}</td>
                </tr>
                <tr>
                  <th>Equity p05 / p95</th>
                  <td>
                    {fmtNum(mc.p05_final_equity)} / {fmtNum(mc.p95_final_equity)}
                  </td>
                </tr>
                <tr>
                  <th>Max DD moy. / p95</th>
                  <td>
                    {fmtPct(mc.mean_max_drawdown)} / {fmtPct(mc.p95_max_drawdown)}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="muted" style={{ padding: '0.5rem 1rem 1rem' }}>
            {mc.disclaimer}
          </p>
        </section>
      )}
    </>
  )
}
