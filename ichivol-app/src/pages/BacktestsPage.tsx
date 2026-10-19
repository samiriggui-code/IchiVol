/**
 * Strategy Lab — vérifier sur l'historique ce que chaque brique de la stratégie apporte, avant le paper.
 * Toutes les valeurs viennent du moteur : backtest quotidien (/backtest/runs), ablation A→E,
 * résultats par régime et walk-forward (/strategy-lab/*). Rien n'est inventé : absent → « — ».
 */

import { Fragment, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
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
import {
  explainAblationStep,
  explainFold,
  explainRegime,
  explainVariant,
  foldVerdict,
  type Explanation,
} from '../lib/labExplain'
import { LabExplainSheet } from '../components/LabExplainSheet'
import { TablePager } from '../components/table/TablePager'
import { usePaged } from '../components/table/usePaged'
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
  ['05', 'Régimes', 'Où la stratégie gagne-t-elle ?', 'Régimes'],
  ['06', 'Paper', 'La stratégie tourne avec de l’argent fictif, sous le regard d’Ève.', null],
]

const TONE_CLASS: Record<BadgeTone, string> = {
  green: 'is-mint',
  amber: 'is-amber',
  red: 'is-sell',
  gray: 'is-muted',
  '': 'is-cyan',
}

function badge(text: string, tone: BadgeTone = 'gray'): ReactNode {
  return <span className={`iv-tag ${TONE_CLASS[tone]}`}>{text}</span>
}

function signClass(v: number | null | undefined): string {
  return v != null ? (v > 0 ? 'pos' : 'neg') : ''
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
      <td className="n">{m ? m.num_trades : '—'}</td>
      <td className="n">{pct(m?.win_rate)}</td>
      <td className={`n ${signClass(m?.expectancy)}`}>{pct(m?.expectancy, 2, true)}</td>
      <td className="n">{num(m?.profit_factor)}</td>
      <td className="n">{pct(m?.max_drawdown)}</td>
    </>
  )
}

export function BacktestsPage() {
  const [labTab, setLabTab] = useState<LabTab>('Backtests')
  const [coverage, setCoverage] = useState<BacktestCoverage | null>(null)
  const [runs, setRuns] = useState<BacktestRuns | null>(null)
  const [loading, setLoading] = useState(true)
  const [sheet, setSheet] = useState<Explanation | null>(null)

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
  const variants = useMemo(() => (latest ? Object.entries(latest.experiments) : []), [latest])
  // Pagination après le calcul : toutes les lignes restent accessibles page par page.
  const variantsPaged = usePaged(variants, 'lab-backtests-variantes')
  const ablationRows = useMemo(() => (ablation ? ablation.steps.map((s, i) => ({ s, i })) : []), [ablation])
  const ablationPaged = usePaged(ablationRows, 'lab-ablations')
  const regimeRows = useMemo(() => regimes?.slices ?? [], [regimes])
  const regimesPaged = usePaged(regimeRows, 'lab-regimes')
  const foldRows = useMemo(() => walk?.folds ?? [], [walk])
  const foldsPaged = usePaged(foldRows, 'lab-walk-forward')
  const hint = LAB_TABS.find((t) => t.id === labTab)?.hint
  const examineBtn = (build: () => Explanation) => (
    <button type="button" className="iv-btn iv-btn--ghost iv-btn--sm lab-examine" onClick={() => setSheet(build())}>
      Examiner ↗
    </button>
  )
  const pickTab = (t: LabTab) => {
    setLabTab(t)
    setError(null)
  }
  const tabMeta =
    labTab === 'Ablations'
      ? ablation
        ? `${ablation.symbol} · ${ablation.timeframe} · ${ablation.n_bars} bougies`
        : 'Lancez le calcul'
      : labTab === 'Régimes'
        ? regimes
          ? `${regimes.symbol} · ${regimes.timeframe} · ${regimes.n_bars} bougies`
          : 'Lancez le calcul'
        : labTab === 'Walk-forward'
          ? walk
            ? `${walk.symbol} · ${walk.timeframe} · ${walk.folds.length} périodes`
            : 'Lancez le calcul'
          : 'Moyenne sur toutes les paires du dernier run'
  const emptyRow = (cols: number) => (
    <tr>
      <td colSpan={cols} className="lab-empty">
        {busy ? 'Calcul en cours…' : 'Choisissez un marché puis « Lancer le calcul ».'}
      </td>
    </tr>
  )

  return (
    <div className="lab-page">
      <div className="iv-ph">
        <div>
          <div className="iv-meta">Strategy Lab · données moteur · backtest quotidien</div>
          <h1>Strategy Lab</h1>
          <p>Vérifier sur l’historique ce que chaque brique de la stratégie apporte.</p>
        </div>
        <div className="iv-ph-act lab-controls">
          {labTab === 'Backtests' ? (
            <span className="iv-chip is-mint">
              <i className="iv-dot" />
              Données moteur
            </span>
          ) : (
            <>
              <select
                className="iv-input"
                aria-label="Marché"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                disabled={busy}
              >
                {SYMBOLS.map((s) => (
                  <option key={s} value={s}>
                    {s.replace(/USDT$/, '')}
                  </option>
                ))}
              </select>
              <select
                className="iv-input"
                aria-label="Unité de temps"
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value)}
                disabled={busy}
              >
                {TIMEFRAMES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <select
                className="iv-input"
                aria-label="Historique"
                value={depth}
                onChange={(e) => setDepth(Number(e.target.value))}
                disabled={busy}
              >
                {DEPTHS.map((d) => (
                  <option key={d} value={d}>
                    {d} bougies
                  </option>
                ))}
              </select>
              <button type="button" className="iv-btn iv-btn--primary" disabled={busy} onClick={() => void runStudy()}>
                {busy ? 'Calcul en cours…' : 'Lancer le calcul'}
              </button>
            </>
          )}
        </div>
      </div>

      <ol className="lab-steps" aria-label="De l’idée à la preuve">
        {STEPS.map(([n, title, text, tab]) => {
          const cur = tab != null && tab === labTab
          return (
            <li className={`lab-step${cur ? ' is-cur' : ''}`} key={n}>
              <div className="lab-step-n">
                {n}
                {cur ? ' · en cours' : ''}
              </div>
              <div className="lab-step-h">
                {tab ? (
                  <button type="button" className="lab-link" onClick={() => pickTab(tab)}>
                    {title}
                  </button>
                ) : (
                  title
                )}
              </div>
              <div className="lab-step-d">{text}</div>
            </li>
          )
        })}
      </ol>

      <div className="iv-kpis lab-kpis">
        <div className="iv-kpi">
          <div className="iv-kpi-k">Univers</div>
          <div className="iv-kpi-v">{coverage?.crypto_symbols ?? '—'}</div>
          <div className="iv-kpi-s">Cryptos du backtest quotidien</div>
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">Dernier calcul</div>
          <div className="iv-kpi-v">{fmtDate(latest?.ended_at)}</div>
          <div className="iv-kpi-s">
            {latest ? `${latest.n_pairs} paires × unités de temps` : loading ? 'chargement…' : 'aucun run'}
          </div>
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">Pipeline vs Ichimoku seul</div>
          <div className="iv-kpi-v">
            {latest && latest.pipeline_vs_ichimoku.compared > 0 ? (
              <>
                {latest.pipeline_vs_ichimoku.beats}
                <small> / {latest.pipeline_vs_ichimoku.compared}</small>
              </>
            ) : (
              '—'
            )}
          </div>
          <div className="iv-kpi-s">Paires au meilleur Sharpe</div>
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">Échantillon minimum</div>
          <div className="iv-kpi-v">{runs?.min_trades_per_pair ?? '—'}</div>
          <div className="iv-kpi-s">Trades par paire, en dessous c’est fragile</div>
        </div>
      </div>

      <section className="iv-card lab-main">
        <div className="iv-card-head">
          <div className="iv-card-tabs" role="tablist">
            {LAB_TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={labTab === t.id}
                className={`iv-card-tab${labTab === t.id ? ' is-on' : ''}`}
                onClick={() => pickTab(t.id)}
              >
                {t.id === 'Ablations' ? 'Ablations · A → E' : t.id}
              </button>
            ))}
          </div>
          <div className="iv-card-tools">{tabMeta}</div>
        </div>
        <div className="lab-hint">
          <span className="iv-kw">◆</span> {hint} Résultats nets de frais, sur bougies clôturées uniquement.
        </div>
        {error && (
          <div className="lab-error" role="alert">
            {error}
          </div>
        )}

        {labTab === 'Backtests' && (
          <div className="iv-card-body is-flush iv-table-wrap">
            <table className="iv-table">
              <thead>
                <tr>
                  <th>Variante</th>
                  <th className="n">Paires</th>
                  <th className="n">Trades</th>
                  <th className="n">Réussite</th>
                  <th className="n">Espérance / trade</th>
                  <th className="n">Sharpe</th>
                  <th className="n">Profit factor</th>
                  <th>Fiabilité</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {variants.length === 0 && (
                  <tr>
                    <td colSpan={9} className="lab-empty">
                      {loading ? 'Chargement…' : 'Aucun backtest enregistré pour le moment.'}
                    </td>
                  </tr>
                )}
                {variantsPaged.rows.map(([key, e]) => (
                  <Fragment key={key}>
                    <tr>
                      <td className="sym">{VARIANT_LABELS[key] ?? key}</td>
                      <td className="n">{e.n_pairs}</td>
                      <td className="n">{e.trades_total}</td>
                      <td className="n">{pct(e.win_rate_mean)}</td>
                      <td className={`n ${signClass(e.expectancy_mean)}`}>{pct(e.expectancy_mean, 2, true)}</td>
                      <td className="n">{num(e.sharpe_mean)}</td>
                      <td className="n">{num(e.profit_factor_median)}</td>
                      <td>{e.small_sample ? badge('ÉCHANTILLON FAIBLE', 'amber') : badge('OK', 'green')}</td>
                      <td className="lab-act">
                        {examineBtn(() =>
                          explainVariant(
                            key,
                            e,
                            runs?.runs ?? [],
                            latest?.experiments.ICHIMOKU_ONLY ?? null,
                            runs?.min_trades_per_pair ?? 30,
                          ),
                        )}
                      </td>
                    </tr>
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {labTab === 'Backtests' && <TablePager paged={variantsPaged} label="variantes" />}

        {labTab === 'Ablations' && (
          <>
            <div className="iv-card-body is-flush iv-table-wrap">
              <table className="iv-table">
                <thead>
                  <tr>
                    <th>Étape</th>
                    <th className="n">Signaux</th>
                    <th className="n">Trades</th>
                    <th className="n">Réussite</th>
                    <th className="n">Espérance / trade</th>
                    <th className="n">Profit factor</th>
                    <th className="n">Drawdown max</th>
                    <th>Apport du filtre</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {!ablation && emptyRow(9)}
                  {ablation &&
                    ablationPaged.rows.map(({ s, i }) => {
                    const delta = i > 0 ? ablation.deltas[i - 1] : null
                    const key = `abl-${s.label}`
                    return (
                      <Fragment key={key}>
                        <tr>
                          <td className="sym">{layerLabel(s.label)}</td>
                          <td className="n">{s.n_signals}</td>
                          <MetricCells m={metricsOf(s.study)} />
                          <td>
                            {delta
                              ? verdictBadge(ablationVerdict(delta.improves_expectancy, delta.improves_profit_factor))
                              : badge('RÉFÉRENCE', '')}
                          </td>
                          <td className="lab-act">
                            {examineBtn(() =>
                              explainAblationStep(s, i > 0 ? ablation.steps[i - 1] : null, delta, {
                                symbol: ablation.symbol,
                                timeframe: ablation.timeframe,
                                nBars: ablation.n_bars,
                              }),
                            )}
                          </td>
                        </tr>
                      </Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <TablePager paged={ablationPaged} label="étapes" />
            <div className="iv-card-foot">Un filtre doit améliorer l’espérance ou le profit factor pour mériter sa place</div>
          </>
        )}

        {labTab === 'Régimes' && (
          <>
            <div className="iv-card-body is-flush iv-table-wrap">
              <table className="iv-table">
                <thead>
                  <tr>
                    <th>Régime</th>
                    <th className="n">Bougies</th>
                    <th className="n">Signaux</th>
                    <th className="n">Trades</th>
                    <th className="n">Réussite</th>
                    <th className="n">Espérance / trade</th>
                    <th className="n">Profit factor</th>
                    <th className="n">Drawdown max</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {!regimes && emptyRow(9)}
                  {regimes &&
                    regimesPaged.rows.map((s) => (
                    <tr key={s.regime}>
                      <td className="sym">{regimeLabel(s.regime)}</td>
                      <td className="n">{s.n_bars_in_regime}</td>
                      <td className="n">{s.n_signals}</td>
                      <MetricCells m={metricsOf(s.study)} />
                      <td className="lab-act">
                        {examineBtn(() =>
                          explainRegime(s, regimes.slices.find((x) => x.regime === 'GLOBAL') ?? null, {
                            symbol: regimes.symbol,
                            timeframe: regimes.timeframe,
                            nBars: regimes.n_bars,
                          }),
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <TablePager paged={regimesPaged} label="régimes" />
            {regimes && (
              <p className="iv-note lab-footnote">
                Règle testée : <span className="iv-kw">{regimes.ruleset?.id ?? '—'}</span>. Un profit factor faible
                sur « Tous les signaux » mais fort en tendance veut dire que la stratégie ne marche que dans ce régime.
              </p>
            )}
          </>
        )}

        {labTab === 'Walk-forward' && (
          <>
            {walk && (
              <div className="iv-kpis lab-kpis-inline">
                <div className="iv-kpi">
                  <div className="iv-kpi-k">Périodes rentables</div>
                  <div className="iv-kpi-v">{pct(walk.oos_summary.pct_folds_pf_gt_1, 0)}</div>
                  <div className="iv-kpi-s">Profit factor &gt; 1 hors échantillon</div>
                </div>
                <div className="iv-kpi">
                  <div className="iv-kpi-k">Espérance moyenne</div>
                  <div className={`iv-kpi-v ${signClass(walk.oos_summary.mean_oos_expectancy)}`}>
                    {pct(walk.oos_summary.mean_oos_expectancy, 2, true)}
                  </div>
                  <div className="iv-kpi-s">Par trade, hors échantillon</div>
                </div>
                <div className="iv-kpi">
                  <div className="iv-kpi-k">Profit factor moyen</div>
                  <div className="iv-kpi-v">{num(walk.oos_summary.mean_oos_profit_factor)}</div>
                  <div className="iv-kpi-s">Hors échantillon</div>
                </div>
                <div className="iv-kpi">
                  <div className="iv-kpi-k">Trades testés</div>
                  <div className="iv-kpi-v">{walk.oos_summary.total_oos_trades}</div>
                  <div className="iv-kpi-s">
                    {walk.oos_summary.folds_with_trades} / {walk.oos_summary.n_folds} périodes avec trades
                  </div>
                </div>
              </div>
            )}
            <div className="iv-card-body is-flush iv-table-wrap">
              <table className="iv-table">
                <thead>
                  <tr>
                    <th>Période</th>
                    <th className="n">Trades (appris → testé)</th>
                    <th className="n">Espérance apprise</th>
                    <th className="n">Espérance testée</th>
                    <th className="n">PF testé</th>
                    <th>Verdict</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {!walk && emptyRow(7)}
                  {walk &&
                    foldsPaged.rows.map((f) => {
                    const is = metricsOf(f.is)
                    const oos = metricsOf(f.oos)
                    const pf = oos?.profit_factor
                    const v = foldVerdict(oos)
                    return (
                      <tr key={f.fold_index}>
                        <td className="sym">#{f.fold_index + 1}</td>
                        <td className="n">
                          {is?.num_trades ?? '—'} → {oos?.num_trades ?? '—'}
                        </td>
                        <td className="n">{pct(is?.expectancy, 2, true)}</td>
                        <td className={`n ${signClass(oos?.expectancy)}`}>{pct(oos?.expectancy, 2, true)}</td>
                        <td className="n">{num(pf)}</td>
                        <td>{verdictBadge(v)}</td>
                        <td className="lab-act">
                          {examineBtn(() =>
                            explainFold(
                              f,
                              { symbol: walk.symbol, timeframe: walk.timeframe, nBars: walk.n_bars },
                              walk.folds.length,
                            ),
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <TablePager paged={foldsPaged} label="périodes" />
          </>
        )}
      </section>

      {sheet && <LabExplainSheet explanation={sheet} onClose={() => setSheet(null)} />}
    </div>
  )
}
