/**
 * Strategy Lab — port littéral de design-reference/ichivol-workspace `lab()` + page-head.
 * Classes HTML = maquette. Données = engine (manquant → « — »).
 */

import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  getBacktestCoverage,
  getBacktestRuns,
  type BacktestCoverage,
  type BacktestRuns,
} from '../lib/activity'
import { getWalkForwardOpt } from '../lib/backtest'
import {
  buildAuditReport,
  proposeExperimentPlan,
  runMonteCarlo,
} from '../lib/labResearch'
import './BacktestsPage.css'

type LabTab = 'Backtests' | 'Ablations' | 'Walk-forward' | 'Régimes' | 'Matrice A–F'
type BadgeTone = 'green' | 'amber' | 'red' | 'gray' | ''

const LAB_TABS: LabTab[] = [
  'Backtests',
  'Ablations',
  'Walk-forward',
  'Régimes',
  'Matrice A–F',
]

/** Taxonomie A–F maquette (structure produit, pas des chiffres inventés). */
const EXPERIMENTS: [string, string, string][] = [
  ['A · Ichimoku seul', '40 paires', 'Direction'],
  ['B · Ichimoku × RVOL', '40 paires', 'Volume relatif'],
  ['C · + Structure', '40 paires', 'Swings / pivots'],
  ['D · + Emplacement', '40 paires', 'Distance au nuage'],
  ['E · + Régime', '40 paires', 'ADX / Donchian'],
  ['F · Multi-timeframe', '40 paires', 'Confluence'],
]

const STEPS: [string, string, string][] = [
  ['01', 'Hypothèse', 'Définir ce que l’on cherche à améliorer.'],
  ['02', 'Backtest', 'Mesurer rendement, risque et coûts.'],
  ['03', 'Walk-forward', 'Vérifier hors échantillon.'],
  ['04', 'Paper', 'Observer avant toute exécution réelle.'],
]

function badge(text: string, tone: BadgeTone = ''): ReactNode {
  let inferred = tone
  if (!inferred) {
    inferred = /PASSE|ACCEPTÉ|OUVERTE|VALIDÉ/i.test(text)
      ? 'green'
      : /REFUS|BLOQU|ERREUR/i.test(text)
        ? 'red'
        : /PRUDENCE|ARMED|WATCH|TRIGGERED/i.test(text)
          ? 'amber'
          : ''
  }
  return <span className={`tag ${inferred}`.trim()}>{text}</span>
}

/** SVG structurel (classe `.chart`) — pas de courbe de perf inventée. */
function LabChart() {
  return (
    <svg className="chart" viewBox="0 0 720 230" role="img" aria-label="Courbe de performance">
      <defs>
        <linearGradient id="lab-fade" x1="0" y1="0" x2="0" y2="1">
          <stop stopColor="#b5d6cc" stopOpacity=".2" />
          <stop offset="1" stopColor="#b5d6cc" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[45, 95, 145, 195].map((y) => (
        <line
          key={y}
          x1="25"
          y1={y}
          x2="680"
          y2={y}
          stroke="#eeeae5"
          strokeDasharray="3 5"
        />
      ))}
      <text x="350" y="120" fontSize="14" fill="#939a9d" textAnchor="middle">
        —
      </text>
    </svg>
  )
}

export function BacktestsPage() {
  const [labTab, setLabTab] = useState<LabTab>('Backtests')
  const [coverage, setCoverage] = useState<BacktestCoverage | null>(null)
  const [runs, setRuns] = useState<BacktestRuns | null>(null)
  const [loading, setLoading] = useState(true)
  const [researchBusy, setResearchBusy] = useState(false)
  const [researchMsg, setResearchMsg] = useState<string | null>(null)

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

  const univers =
    coverage?.crypto_symbols != null ? String(coverage.crypto_symbols) : loading ? '—' : '—'
  const fenetre = runs?.runs?.[0]
    ? `${runs.runs[0].n_pairs} paires`
    : '—'
  const fenetreSub = runs?.runs?.[0]
    ? `${runs.runs[0].n_rows} lignes`
    : '—'

  const cardTitle = labTab === 'Backtests' ? 'Expériences comparées' : labTab

  const perimeter = useMemo(() => {
    if (coverage?.crypto_symbols != null) return `${coverage.crypto_symbols} paires`
    return EXPERIMENTS[0][1]
  }, [coverage])

  async function runResearch(kind: 'plan' | 'audit' | 'mc' | 'wf') {
    setResearchBusy(true)
    setResearchMsg(null)
    const rulesetId = 'IV_ICHIMOKU_RVOL_LONG_001'
    try {
      if (kind === 'plan') {
        const audit = await buildAuditReport({
          symbol: 'BTCUSDT',
          timeframe: '1h',
          limit: 800,
          rulesetId,
        })
        const plan = await proposeExperimentPlan(audit)
        const first = plan.steps?.[0]?.purpose ?? plan.notes?.[0] ?? plan.status
        setResearchMsg(`Plan · ${String(first).slice(0, 140)}`)
      } else if (kind === 'audit') {
        const audit = await buildAuditReport({
          symbol: 'BTCUSDT',
          timeframe: '1h',
          limit: 800,
          rulesetId,
        })
        const tip = audit.what_worked?.[0] ?? audit.disclaimer ?? 'ok'
        setResearchMsg(`Audit · ${String(tip).slice(0, 140)}`)
      } else if (kind === 'mc') {
        const mc = await runMonteCarlo({
          symbol: 'BTCUSDT',
          timeframe: '1h',
          limit: 800,
          rulesetId,
          nPaths: 200,
        })
        setResearchMsg(`Monte Carlo · ${mc.n_paths} chemins · ruin ${mc.risk_of_ruin ?? '—'}`)
      } else {
        await getWalkForwardOpt('BTCUSDT', '1h', 800, rulesetId, {
          persist: false,
        })
        setResearchMsg('Walk-forward opt reçu (aperçu moteur).')
      }
    } catch (err: unknown) {
      setResearchMsg(err instanceof Error ? err.message : 'Échec research')
    } finally {
      setResearchBusy(false)
    }
  }

  return (
    <div className="lab-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">05 / ICHIVOL WORKSPACE</div>
          <h1>Strategy Lab</h1>
          <p className="subtitle">Comparer, comprendre, améliorer.</p>
        </div>
        <div className="actions">{badge('DONNÉES LIVE', 'gray')}</div>
      </div>

      <div className="tabs">
        {LAB_TABS.map((t) => (
          <button
            key={t}
            type="button"
            className={labTab === t ? 'active' : ''}
            onClick={() => setLabTab(t)}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="notice blue">
        ◈{' '}
        <span>
          Résultats engine · couverture backtest / runs persistés · research lab branché
          (plan / audit / MC / walk-forward opt).
        </span>
      </div>
      {researchMsg && (
        <p style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 16 }} role="status">
          {researchMsg}
        </p>
      )}

      <div className="metrics">
        <div className="metric">
          <div className="metric-label">
            Univers<span>↗</span>
          </div>
          <div className="metric-value">{univers}</div>
          <small>Crypto spot · Binance</small>
        </div>
        <div className="metric">
          <div className="metric-label">
            Fenêtre<span>↗</span>
          </div>
          <div className="metric-value">{fenetre}</div>
          <small>{fenetreSub === '—' ? 'snapshots de référence' : fenetreSub}</small>
        </div>
        <div className="metric">
          <div className="metric-label">
            Validation<span>↗</span>
          </div>
          <div className="metric-value">Causale</div>
          <small>Bougies clôturées uniquement</small>
        </div>
        <div className="metric">
          <div className="metric-label">
            Hypothèse<span>↗</span>
          </div>
          <div className="metric-value">Ichi × RVOL</div>
          <small>Seuil volume ≥ 1,5</small>
        </div>
      </div>

      <section className="card">
        <div className="card-head">
          <h2>{cardTitle}</h2>
          <button
            type="button"
            className="primary"
            disabled={researchBusy}
            onClick={() => void runResearch('plan')}
          >
            {researchBusy ? 'Calcul…' : 'Configurer une expérience'}
          </button>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>EXPÉRIENCE</th>
                <th>PÉRIMÈTRE</th>
                <th>VARIABLE TESTÉE</th>
                <th>STATUT</th>
                <th>ACTION</th>
              </tr>
            </thead>
            <tbody>
              {EXPERIMENTS.map((r, i) => {
                const variable = labTab === 'Ablations' ? `Retrait : ${r[2]}` : r[2]
                const status =
                  runs?.runs?.length
                    ? badge('MESURÉ', 'gray')
                    : badge(loading ? '—' : 'À ÉVALUER', 'gray')
                return (
                  <tr key={r[0]}>
                    <td>
                      <b>{r[0]}</b>
                    </td>
                    <td>{coverage?.crypto_symbols != null ? perimeter : '—'}</td>
                    <td>{variable}</td>
                    <td>{status}</td>
                    <td>
                      <button
                        type="button"
                        className="subtle"
                        data-experiment={i}
                        disabled={researchBusy}
                        onClick={() =>
                          void runResearch(
                            labTab === 'Walk-forward'
                              ? 'wf'
                              : labTab === 'Ablations'
                                ? 'audit'
                                : labTab === 'Régimes'
                                  ? 'mc'
                                  : 'audit',
                          )
                        }
                      >
                        Examiner ↗
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>

      <div style={{ height: 20 }} />

      <div className="grid">
        <section className="card">
          <div className="card-head">
            <h2>Comparer les trajectoires</h2>
            {badge('ILLUSTRATION', 'gray')}
          </div>
          <div className="chart-summary">
            <span style={{ color: '#478f83' }}>— Ichimoku × RVOL</span>
            <span>— Ichimoku seul</span>
            <span>┄ Buy & hold</span>
          </div>
          <LabChart />
        </section>

        <section className="card">
          <div className="card-head">
            <h2>De l’idée à la preuve</h2>
          </div>
          <div className="card-body">
            {STEPS.map((s) => (
              <div className="step" key={s[0]}>
                <b>
                  {s[0]} · {s[1]}
                </b>
                <p>{s[2]}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
