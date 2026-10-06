/**
 * Strategy Lab — vérifier sur l'historique ce que chaque brique de la stratégie apporte, avant le paper.
 * Toutes les valeurs viennent du moteur : backtest quotidien (/backtest/runs), ablation A→E,
 * résultats par régime et walk-forward (/strategy-lab/*). Rien n'est inventé : absent → « — ».
 */

import { Fragment, useCallback, useEffect, useState, type ReactNode } from 'react'
import {
  getBacktestCoverage,
  getBacktestRuns,
  type BacktestCoverage,
  type BacktestRuns,
} from '../lib/activity'
import {
  getAblation,
  getRegimeSlices,
  getWalkForward,
  type AblationResult,
  type BacktestMetrics,
  type RegimeSlicesResult,
  type RulesetStudyResult,
  type WalkForwardResult,
} from '../lib/backtest'
import {
  VARIANT_LABELS,
  ablationVerdict,
  layerLabel,
  num,
  pct,
  regimeLabel,
  type Verdict,
} from '../lib/labFormat'
import './BacktestsPage.css'

type LabTab = 'Backtests' | 'Ablations' | 'Régimes' | 'Walk-forward'
type BadgeTone = 'green' | 'amber' | 'red' | 'gray' | ''

const LAB_TABS: { id: LabTab; hint: string }[] = [
  { id: 'Backtests', hint: 'Backtest automatique quotidien, toutes paires : chaque variante de la stratégie comparée.' },
  { id: 'Ablations', hint: 'On ajoute les filtres un par un (A → E) : chacun doit améliorer le résultat pour mériter sa place.' },
  { id: 'Régimes', hint: 'Mêmes signaux, triés selon l’état du marché au moment du signal : où la stratégie gagne-t-elle ?' },
  { id: 'Walk-forward', hint: 'La règle est testée sur des périodes successives jamais vues : le contrôle anti-sur-optimisation.' },
]

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT', 'AVAXUSDT', 'LINKUSDT']
const TIMEFRAMES = ['1h', '4h', '1d']
const DEPTHS = [500, 1000, 2000]

const STEPS: [string, string, string, LabTab | null][] = [
  ['01', 'Hypothèse', 'Définir ce que l’on cherche à améliorer.', null],
  ['02', 'Backtest', 'Mesurer rendement, risque et coûts.', 'Backtests'],
  ['03', 'Ablation', 'Garder seulement les filtres qui apportent quelque chose.', 'Ablations'],
  ['04', 'Walk-forward', 'Vérifier hors échantillon.', 'Walk-forward'],
  ['05', 'Paper', 'Observer avant toute exécution réelle.', null],
]

function badge(text: string, tone: BadgeTone = 'gray'): ReactNode {
  return <span className={`tag ${tone}`.trim()}>{text}</span>
}

function verdictBadge(v: Verdict): ReactNode {
  return badge(v.text, v.tone)
}

function metricsOf(study: RulesetStudyResult | null | undefined): BacktestMetrics | null {
  return study?.backtest?.metrics ?? null
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? '—'
    : d.toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

/** Ligne de métriques communes aux tableaux Ablations / Régimes. */
function MetricCells({ m }: { m: BacktestMetrics | null }) {
  return (
    <>
      <td>{m ? m.num_trades : '—'}</td>
      <td>{pct(m?.win_rate)}</td>
      <td className={m?.expectancy != null ? (m.expectancy > 0 ? 'lab-up' : 'lab-down') : ''}>
        {pct(m?.expectancy, 2, true)}
      </td>
      <td>{num(m?.profit_factor)}</td>
      <td>{pct(m?.max_drawdown)}</td>
    </>
  )
}

export function BacktestsPage() {
  const [labTab, setLabTab] = useState<LabTab>('Backtests')
  const [coverage, setCoverage] = useState<BacktestCoverage | null>(null)
  const [runs, setRuns] = useState<BacktestRuns | null>(null)
  const [loading, setLoading] = useState(true)
  const [open, setOpen] = useState<string | null>(null)

  const [symbol, setSymbol] = useState('BTCUSDT')
  const [timeframe, setTimeframe] = useState('1h')
  const [depth, setDepth] = useState(1000)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [ablation, setAblation] = useState<AblationResult | null>(null)
  const [regimes, setRegimes] = useState<RegimeSlicesResult | null>(null)
  const [walk, setWalk] = useState<WalkForwardResult | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [c, r] = await Promise.all([
        getBacktestCoverage().catch(() => null),
        getBacktestRuns(10).catch(() => null),
      ])
      setCoverage(c)
      setRuns(r)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  async function runStudy() {
    if (labTab === 'Backtests' || busy) return
    setBusy(true)
    setError(null)
    setOpen(null)
    try {
      if (labTab === 'Ablations') setAblation(await getAblation(symbol, timeframe, depth))
      else if (labTab === 'Régimes') setRegimes(await getRegimeSlices(symbol, timeframe, depth))
      else setWalk(await getWalkForward(symbol, timeframe, depth))
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Calcul impossible')
    } finally {
      setBusy(false)
    }
  }

  const latest = runs?.runs?.[0] ?? null
  const variants = latest ? Object.entries(latest.experiments) : []
  const hint = LAB_TABS.find((t) => t.id === labTab)?.hint
  const toggle = (key: string) => setOpen((cur) => (cur === key ? null : key))

  return (
    <div className="lab-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">05 / ICHIVOL WORKSPACE</div>
          <h1>Strategy Lab</h1>
          <p className="subtitle">Vérifier sur l’historique ce que chaque brique de la stratégie apporte.</p>
        </div>
        <div className="actions">{badge('DONNÉES MOTEUR')}</div>
      </div>

      <div className="tabs">
        {LAB_TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={labTab === t.id ? 'active' : ''}
            onClick={() => {
              setLabTab(t.id)
              setError(null)
              setOpen(null)
            }}
          >
            {t.id}
          </button>
        ))}
      </div>

      <div className="notice blue">
        ◈ <span>{hint} Résultats nets de frais, sur bougies clôturées uniquement.</span>
      </div>

      {labTab === 'Backtests' ? (
        <div className="metrics">
          <div className="metric">
            <div className="metric-label">Univers</div>
            <div className="metric-value">{coverage?.crypto_symbols ?? '—'}</div>
            <small>Cryptos couvertes par le backtest quotidien</small>
          </div>
          <div className="metric">
            <div className="metric-label">Dernier calcul</div>
            <div className="metric-value">{fmtDate(latest?.ended_at)}</div>
            <small>{latest ? `${latest.n_pairs} paires × unités de temps` : loading ? 'chargement…' : 'aucun run'}</small>
          </div>
          <div className="metric">
            <div className="metric-label">Pipeline vs Ichimoku seul</div>
            <div className="metric-value">
              {latest && latest.pipeline_vs_ichimoku.compared > 0
                ? `${latest.pipeline_vs_ichimoku.beats} / ${latest.pipeline_vs_ichimoku.compared}`
                : '—'}
            </div>
            <small>Paires où le pipeline complet a un meilleur Sharpe</small>
          </div>
          <div className="metric">
            <div className="metric-label">Échantillon minimum</div>
            <div className="metric-value">{runs?.min_trades_per_pair ?? '—'}</div>
            <small>Trades par paire en dessous desquels un chiffre est fragile</small>
          </div>
        </div>
      ) : (
        <div className="lab-controls">
          <label>
            Marché
            <select value={symbol} onChange={(e) => setSymbol(e.target.value)} disabled={busy}>
              {SYMBOLS.map((s) => (
                <option key={s} value={s}>
                  {s.replace(/USDT$/, '')}
                </option>
              ))}
            </select>
          </label>
          <label>
            Unité de temps
            <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} disabled={busy}>
              {TIMEFRAMES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <label>
            Historique
            <select value={depth} onChange={(e) => setDepth(Number(e.target.value))} disabled={busy}>
              {DEPTHS.map((d) => (
                <option key={d} value={d}>
                  {d} bougies
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="primary" disabled={busy} onClick={() => void runStudy()}>
            {busy ? 'Calcul en cours…' : 'Lancer le calcul'}
          </button>
        </div>
      )}

      {error && (
        <div className="notice lab-error" role="alert">
          {error}
        </div>
      )}

      {labTab === 'Backtests' && (
        <section className="card">
          <div className="card-head">
            <h2>Variantes comparées</h2>
            <small>Moyenne sur toutes les paires du dernier run</small>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>VARIANTE</th>
                  <th>PAIRES</th>
                  <th>TRADES</th>
                  <th>RÉUSSITE</th>
                  <th>ESPÉRANCE / TRADE</th>
                  <th>SHARPE</th>
                  <th>PROFIT FACTOR</th>
                  <th>FIABILITÉ</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {variants.length === 0 && (
                  <tr>
                    <td colSpan={9}>{loading ? 'Chargement…' : 'Aucun backtest enregistré pour le moment.'}</td>
                  </tr>
                )}
                {variants.map(([key, e]) => (
                  <Fragment key={key}>
                    <tr>
                      <td>
                        <b>{VARIANT_LABELS[key] ?? key}</b>
                      </td>
                      <td>{e.n_pairs}</td>
                      <td>{e.trades_total}</td>
                      <td>{pct(e.win_rate_mean)}</td>
                      <td className={e.expectancy_mean != null ? (e.expectancy_mean > 0 ? 'lab-up' : 'lab-down') : ''}>
                        {pct(e.expectancy_mean, 2, true)}
                      </td>
                      <td>{num(e.sharpe_mean)}</td>
                      <td>{num(e.profit_factor_median)}</td>
                      <td>{e.small_sample ? badge('ÉCHANTILLON FAIBLE', 'amber') : badge('OK', 'green')}</td>
                      <td>
                        <button type="button" className="subtle" onClick={() => toggle(key)}>
                          {open === key ? 'Fermer' : 'Examiner ↗'}
                        </button>
                      </td>
                    </tr>
                    {open === key && (
                      <tr className="lab-detail">
                        <td colSpan={9}>
                          <p>Évolution sur les {runs?.runs.length ?? 0} derniers runs :</p>
                          <table>
                            <thead>
                              <tr>
                                <th>RUN</th>
                                <th>TRADES</th>
                                <th>RÉUSSITE</th>
                                <th>ESPÉRANCE</th>
                                <th>PROFIT FACTOR</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(runs?.runs ?? []).map((r) => {
                                const x = r.experiments[key]
                                return (
                                  <tr key={r.started_at}>
                                    <td>{fmtDate(r.ended_at)}</td>
                                    <td>{x?.trades_total ?? '—'}</td>
                                    <td>{pct(x?.win_rate_mean)}</td>
                                    <td>{pct(x?.expectancy_mean, 2, true)}</td>
                                    <td>{num(x?.profit_factor_median)}</td>
                                  </tr>
                                )
                              })}
                            </tbody>
                          </table>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {labTab === 'Ablations' && (
        <section className="card">
          <div className="card-head">
            <h2>Échelle A → E</h2>
            <small>{ablation ? `${ablation.symbol} · ${ablation.timeframe} · ${ablation.n_bars} bougies` : 'Lancez le calcul'}</small>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ÉTAPE</th>
                  <th>SIGNAUX</th>
                  <th>TRADES</th>
                  <th>RÉUSSITE</th>
                  <th>ESPÉRANCE / TRADE</th>
                  <th>PROFIT FACTOR</th>
                  <th>DRAWDOWN MAX</th>
                  <th>APPORT DU FILTRE</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {!ablation && (
                  <tr>
                    <td colSpan={9}>{busy ? 'Calcul en cours…' : 'Choisissez un marché puis « Lancer le calcul ».'}</td>
                  </tr>
                )}
                {ablation?.steps.map((s, i) => {
                  const delta = i > 0 ? ablation.deltas[i - 1] : null
                  const key = `abl-${s.label}`
                  return (
                    <Fragment key={key}>
                      <tr>
                        <td>
                          <b>{layerLabel(s.label)}</b>
                        </td>
                        <td>{s.n_signals}</td>
                        <MetricCells m={metricsOf(s.study)} />
                        <td>
                          {delta
                            ? verdictBadge(ablationVerdict(delta.improves_expectancy, delta.improves_profit_factor))
                            : badge('RÉFÉRENCE')}
                        </td>
                        <td>
                          {delta && (
                            <button type="button" className="subtle" onClick={() => toggle(key)}>
                              {open === key ? 'Fermer' : 'Examiner ↗'}
                            </button>
                          )}
                        </td>
                      </tr>
                      {open === key && delta && (
                        <tr className="lab-detail">
                          <td colSpan={9}>
                            <p>
                              Conditions ajoutées : <b>{delta.added_conditions.join(', ') || '—'}</b>
                            </p>
                            <p>
                              Par rapport à l’étape précédente : signaux {delta.n_signals_delta >= 0 ? '+' : ''}
                              {delta.n_signals_delta}, trades {delta.n_trades_delta >= 0 ? '+' : ''}
                              {delta.n_trades_delta}, réussite {pct(delta.win_rate_delta, 1, true)}, espérance{' '}
                              {pct(delta.expectancy_delta, 2, true)}, profit factor{' '}
                              {delta.profit_factor_delta != null ? `${delta.profit_factor_delta > 0 ? '+' : ''}${num(delta.profit_factor_delta)}` : '—'}.
                            </p>
                            {delta.note && <p className="muted">{delta.note}</p>}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
          {ablation && <p className="lab-footnote">Un filtre doit améliorer l’espérance ou le profit factor pour mériter sa place.</p>}
        </section>
      )}

      {labTab === 'Régimes' && (
        <section className="card">
          <div className="card-head">
            <h2>Résultats par régime de marché</h2>
            <small>{regimes ? `${regimes.symbol} · ${regimes.timeframe} · ${regimes.n_bars} bougies` : 'Lancez le calcul'}</small>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>RÉGIME</th>
                  <th>BOUGIES</th>
                  <th>SIGNAUX</th>
                  <th>TRADES</th>
                  <th>RÉUSSITE</th>
                  <th>ESPÉRANCE / TRADE</th>
                  <th>PROFIT FACTOR</th>
                  <th>DRAWDOWN MAX</th>
                </tr>
              </thead>
              <tbody>
                {!regimes && (
                  <tr>
                    <td colSpan={8}>{busy ? 'Calcul en cours…' : 'Choisissez un marché puis « Lancer le calcul ».'}</td>
                  </tr>
                )}
                {regimes?.slices.map((s) => (
                  <tr key={s.regime}>
                    <td>
                      <b>{regimeLabel(s.regime)}</b>
                    </td>
                    <td>{s.n_bars_in_regime}</td>
                    <td>{s.n_signals}</td>
                    <MetricCells m={metricsOf(s.study)} />
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {regimes && (
            <p className="lab-footnote">
              Règle testée : {regimes.ruleset?.id ?? '—'}. Un profit factor faible sur « Tous les
              signaux » mais fort en tendance veut dire que la stratégie ne marche que dans ce régime.
            </p>
          )}
        </section>
      )}

      {labTab === 'Walk-forward' && (
        <section className="card">
          <div className="card-head">
            <h2>Hors échantillon, période par période</h2>
            <small>{walk ? `${walk.symbol} · ${walk.timeframe} · ${walk.folds.length} périodes` : 'Lancez le calcul'}</small>
          </div>
          {walk && (
            <div className="metrics lab-metrics-inline">
              <div className="metric">
                <div className="metric-label">Périodes rentables</div>
                <div className="metric-value">{pct(walk.oos_summary.pct_folds_pf_gt_1, 0)}</div>
                <small>Profit factor &gt; 1 hors échantillon</small>
              </div>
              <div className="metric">
                <div className="metric-label">Espérance moyenne</div>
                <div className="metric-value">{pct(walk.oos_summary.mean_oos_expectancy, 2, true)}</div>
                <small>Par trade, hors échantillon</small>
              </div>
              <div className="metric">
                <div className="metric-label">Profit factor moyen</div>
                <div className="metric-value">{num(walk.oos_summary.mean_oos_profit_factor)}</div>
                <small>Hors échantillon</small>
              </div>
              <div className="metric">
                <div className="metric-label">Trades testés</div>
                <div className="metric-value">{walk.oos_summary.total_oos_trades}</div>
                <small>
                  {walk.oos_summary.folds_with_trades} / {walk.oos_summary.n_folds} périodes avec trades
                </small>
              </div>
            </div>
          )}
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>PÉRIODE</th>
                  <th>TRADES (APPRIS → TESTÉ)</th>
                  <th>ESPÉRANCE APPRISE</th>
                  <th>ESPÉRANCE TESTÉE</th>
                  <th>PF TESTÉ</th>
                  <th>VERDICT</th>
                </tr>
              </thead>
              <tbody>
                {!walk && (
                  <tr>
                    <td colSpan={6}>{busy ? 'Calcul en cours…' : 'Choisissez un marché puis « Lancer le calcul ».'}</td>
                  </tr>
                )}
                {walk?.folds.map((f) => {
                  const is = metricsOf(f.is)
                  const oos = metricsOf(f.oos)
                  const pf = oos?.profit_factor
                  const v: Verdict =
                    !oos || oos.num_trades === 0
                      ? { text: 'AUCUN TRADE', tone: 'gray' }
                      : pf != null && pf > 1
                        ? { text: 'TIENT', tone: 'green' }
                        : { text: 'NE TIENT PAS', tone: 'red' }
                  return (
                    <tr key={f.fold_index}>
                      <td>
                        <b>#{f.fold_index + 1}</b>
                      </td>
                      <td>
                        {is?.num_trades ?? '—'} → {oos?.num_trades ?? '—'}
                      </td>
                      <td>{pct(is?.expectancy, 2, true)}</td>
                      <td className={oos?.expectancy != null ? (oos.expectancy > 0 ? 'lab-up' : 'lab-down') : ''}>
                        {pct(oos?.expectancy, 2, true)}
                      </td>
                      <td>{num(pf)}</td>
                      <td>{verdictBadge(v)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <div style={{ height: 20 }} />

      <section className="card">
        <div className="card-head">
          <h2>De l’idée à la preuve</h2>
        </div>
        <div className="card-body lab-steps">
          {STEPS.map(([n, title, text, tab]) => (
            <div className="step" key={n}>
              <b>
                {n} ·{' '}
                {tab ? (
                  <button type="button" className="lab-link" onClick={() => setLabTab(tab)}>
                    {title}
                  </button>
                ) : (
                  title
                )}
              </b>
              <p>{text}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
