import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  fetchAgentTools,
  runAgentCommand,
  strategyLabBriefPlaybook,
  symbolBriefPlaybook,
  type AgentCommandName,
  type AgentToolSpec,
} from '../lib/agentChannel'

type BriefLine = { label: string; value: string }
type BusyKind = 'brief' | 'gates' | 'lab' | 'wf' | 'wfo' | null

/** Libellés métier — on n'expose pas le jargon API en premier. */
const TOOL_UX: Record<string, { title: string; blurb: string }> = {
  scan_market: {
    title: 'Scanner le marché',
    blurb: 'Screener multi-actifs (même lecture que Décisions).',
  },
  get_symbol_context: {
    title: 'Contexte symbole',
    blurb: 'Décision complète : portes, raisons, risques.',
  },
  detect_signal: {
    title: 'Verdict portes',
    blurb: 'Label condensé BUY / SELL / WATCH / NO_TRADE.',
  },
  compare_timeframes: {
    title: 'Comparer les TF',
    blurb: '15m · 1h · 4h · 1d côte à côte.',
  },
  run_backtest: {
    title: 'Backtest',
    blurb: 'Comparer Ichimoku / RVOL / pipeline sur l historique.',
  },
  run_event_study: {
    title: 'Event Study',
    blurb: 'Après chaque signal : +N bougies, MFE/MAE ATR — sans capital.',
  },
  list_rulesets: {
    title: 'Rulesets',
    blurb: 'Hypothèses IV_* déclaratives (Strategy Lab).',
  },
  run_ruleset_event_study: {
    title: 'Ruleset Study',
    blurb: 'Évalue un ruleset puis mesure le forward path + SL/TP.',
  },
  list_strategy_lab_experiments: {
    title: 'Perf DB',
    blurb: 'Expériences Strategy Lab déjà persistées.',
  },
  run_ablation: {
    title: 'Ablation',
    blurb: 'Escalier de filtres — mesure l apport marginal de chaque couche.',
  },
  run_regime_slices: {
    title: 'Régimes',
    blurb: 'Perf découpée TRENDING / RANGING / VOL / BULL…',
  },
  run_walk_forward: {
    title: 'Walk-forward',
    blurb: 'Même ruleset sur folds IS/OOS — anti-overfitting.',
  },
  run_optimize: {
    title: 'Optimize (IS)',
    blurb: 'Grid-search sur une fenêtre — diagnostic seulement.',
  },
  run_walk_forward_opt: {
    title: 'Walk-forward opt',
    blurb: 'Best params sur IS, mesure OOS — Phase 8.',
  },
  get_correlations: {
    title: 'Corrélations',
    blurb: 'Qui bouge avec qui (lecture seule).',
  },
  get_news: {
    title: 'News crypto',
    blurb: 'Titres RSS — contexte, pas un vote.',
  },
  get_calendar: {
    title: 'Calendrier macro',
    blurb: 'Événements de la semaine — contexte seul.',
  },
  calculate_ichimoku: {
    title: 'Ichimoku brut',
    blurb: 'Niveaux cloud — pas une décision.',
  },
  calculate_rvol: {
    title: 'RVOL brut',
    blurb: 'Participation volume — pas une décision.',
  },
  list_tools: {
    title: 'Liste des capacités',
    blurb: 'Introspection du canal agent.',
  },
}

const DEFAULT_RULESET = 'IV_ICHIMOKU_RVOL_LONG_001'

function fmtPct(v: unknown): string {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—'
  return `${(v * 100).toFixed(1)}%`
}

function fmtNum(v: unknown): string {
  if (typeof v !== 'number' || !Number.isFinite(v)) return '—'
  return v.toFixed(2)
}

function summarizeContext(data: unknown): BriefLine[] {
  if (!data || typeof data !== 'object') return [{ label: 'contexte', value: '—' }]
  const d = data as Record<string, unknown>
  const pipeline = (d.pipeline ?? {}) as Record<string, unknown>
  const lines: BriefLine[] = [
    { label: 'Badge', value: typeof d.decision === 'string' ? d.decision : '—' },
    {
      label: 'Portes',
      value: typeof pipeline.decision === 'string' ? String(pipeline.decision) : '—',
    },
    { label: 'Direction', value: typeof d.direction === 'string' ? d.direction : '—' },
  ]
  if (typeof d.rvol === 'number') {
    lines.push({ label: 'RVOL', value: `${d.rvol.toFixed(2)}×` })
  }
  return lines
}

function summarizeCompare(data: unknown): BriefLine[] {
  if (!data || typeof data !== 'object') return []
  const tfs = (data as { timeframes?: Record<string, unknown> }).timeframes
  if (!tfs || typeof tfs !== 'object') return []
  return Object.entries(tfs).map(([tf, row]) => {
    if (!row || typeof row !== 'object') return { label: tf, value: '—' }
    const r = row as Record<string, unknown>
    if (typeof r.error === 'string') return { label: tf, value: `indispo` }
    const decision = typeof r.decision === 'string' ? r.decision : '—'
    const pipe = (r.pipeline ?? {}) as Record<string, unknown>
    const gate = typeof pipe.decision === 'string' ? String(pipe.decision) : null
    return {
      label: tf,
      value: gate ? `${decision} → ${gate}` : decision,
    }
  })
}

function summarizeRulesetStudy(data: unknown): BriefLine[] {
  if (!data || typeof data !== 'object') return []
  const d = data as Record<string, unknown>
  const rs = (d.ruleset ?? {}) as Record<string, unknown>
  const bt = (d.backtest ?? {}) as Record<string, unknown>
  const m = (bt.metrics ?? {}) as Record<string, unknown>
  return [
    { label: 'Ruleset', value: typeof rs.id === 'string' ? rs.id : '—' },
    { label: 'Signaux', value: String(d.n_signals ?? '—') },
    { label: 'Trades', value: String(m.num_trades ?? '—') },
    { label: 'WR', value: fmtPct(m.win_rate) },
    { label: 'PF', value: fmtNum(m.profit_factor) },
    { label: 'Expect.', value: fmtPct(m.expectancy) },
    { label: 'Sharpe', value: fmtNum(m.sharpe) },
  ]
}

function summarizeAblation(data: unknown): BriefLine[] {
  if (!data || typeof data !== 'object') return []
  const d = data as Record<string, unknown>
  const steps = Array.isArray(d.steps) ? d.steps : []
  const lines: BriefLine[] = [
    { label: 'Ablation', value: typeof d.mode === 'string' ? d.mode : 'cumulative' },
    { label: 'Étapes', value: String(steps.length) },
  ]
  for (const step of steps.slice(0, 5)) {
    if (!step || typeof step !== 'object') continue
    const s = step as Record<string, unknown>
    const study = (s.study ?? {}) as Record<string, unknown>
    const bt = (study.backtest ?? {}) as Record<string, unknown>
    const m = (bt.metrics ?? {}) as Record<string, unknown>
    const label = typeof s.label === 'string' ? s.label : 'step'
    lines.push({
      label,
      value: `tr ${m.num_trades ?? '—'} · PF ${fmtNum(m.profit_factor)} · Exp ${fmtPct(m.expectancy)}`,
    })
  }
  return lines
}

function summarizeRegime(data: unknown): BriefLine[] {
  if (!data || typeof data !== 'object') return []
  const d = data as Record<string, unknown>
  const slices = Array.isArray(d.slices) ? d.slices : []
  const lines: BriefLine[] = [{ label: 'Régimes', value: String(slices.length) }]
  for (const slice of slices.slice(0, 8)) {
    if (!slice || typeof slice !== 'object') continue
    const s = slice as Record<string, unknown>
    const study = (s.study ?? {}) as Record<string, unknown>
    const bt = (study.backtest ?? {}) as Record<string, unknown>
    const m = (bt.metrics ?? {}) as Record<string, unknown>
    const regime = typeof s.regime === 'string' ? s.regime : '—'
    lines.push({
      label: regime,
      value: `sig ${s.n_signals ?? '—'} · PF ${fmtNum(m.profit_factor)} · Exp ${fmtPct(m.expectancy)}`,
    })
  }
  return lines
}

function summarizeWalkForward(data: unknown, title: string): BriefLine[] {
  if (!data || typeof data !== 'object') return []
  const d = data as Record<string, unknown>
  const oos = (d.oos_summary ?? {}) as Record<string, unknown>
  const lines: BriefLine[] = [
    { label: title, value: typeof d.mode === 'string' ? d.mode : 'rolling' },
    { label: 'Folds', value: String(oos.n_folds ?? (Array.isArray(d.folds) ? d.folds.length : '—')) },
    { label: 'OOS trades', value: String(oos.total_oos_trades ?? '—') },
    { label: 'mean OOS Exp', value: fmtPct(oos.mean_oos_expectancy) },
    { label: 'mean OOS PF', value: fmtNum(oos.mean_oos_profit_factor) },
    { label: 'folds PF>1', value: fmtPct(oos.pct_folds_pf_gt_1) },
  ]
  const stability = (d.param_stability ?? {}) as Record<string, unknown>
  const keys = (stability.keys ?? {}) as Record<string, unknown>
  for (const [k, v] of Object.entries(keys).slice(0, 4)) {
    if (!v || typeof v !== 'object') continue
    const row = v as Record<string, unknown>
    lines.push({ label: `stab ${k}`, value: String(row.mode ?? '—') })
  }
  return lines
}

interface Props {
  symbol: string | null | undefined
  timeframe?: string | null
}

/**
 * Panneau « Lecture moteur » — chiffres Python, pas le dump API.
 */
export function AgentEnginePanel({ symbol, timeframe }: Props) {
  const [tools, setTools] = useState<AgentToolSpec[] | null>(null)
  const [toolsError, setToolsError] = useState<string | null>(null)
  const [busy, setBusy] = useState<BusyKind>(null)
  const [error, setError] = useState<string | null>(null)
  const [briefLines, setBriefLines] = useState<BriefLine[] | null>(null)

  useEffect(() => {
    let cancelled = false
    void (async () => {
      const res = await fetchAgentTools()
      if (cancelled) return
      if (!res.ok) {
        setToolsError(res.error)
        setTools(null)
        return
      }
      setToolsError(null)
      setTools(res.tools)
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const hasTool = useMemo(() => {
    const names = new Set((tools ?? []).map((t) => t.name))
    return (name: string) => names.has(name)
  }, [tools])

  const featured = useMemo(() => {
    if (!tools) return []
    const order = [
      'get_symbol_context',
      'detect_signal',
      'compare_timeframes',
      'run_event_study',
      'run_ruleset_event_study',
      'run_ablation',
      'run_regime_slices',
      'run_walk_forward',
      'run_walk_forward_opt',
      'list_strategy_lab_experiments',
      'run_backtest',
      'scan_market',
    ]
    const byName = new Map(tools.map((t) => [t.name, t]))
    return order
      .map((name) => byName.get(name))
      .filter((t): t is AgentToolSpec => Boolean(t))
      .slice(0, 10)
  }, [tools])

  async function onBrief() {
    const sym = (symbol ?? '').trim().toUpperCase()
    if (!sym) {
      setError('Choisis un symbole via Décisions ou Marché.')
      return
    }
    setBusy('brief')
    setError(null)
    setBriefLines(null)
    try {
      const batch = await symbolBriefPlaybook(sym, ['15m', '1h', '4h'])
      if (!batch.ok) {
        setError(batch.error)
        return
      }
      const lines: BriefLine[] = [{ label: 'Symbole', value: sym }]
      for (const row of batch.results) {
        if (!row.ok) {
          lines.push({ label: row.cmd, value: `erreur` })
          continue
        }
        if (row.cmd === 'get_symbol_context') lines.push(...summarizeContext(row.data))
        else if (row.cmd === 'compare_timeframes') lines.push(...summarizeCompare(row.data))
      }
      setBriefLines(lines)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Brief impossible')
    } finally {
      setBusy(null)
    }
  }

  async function onDetect() {
    const sym = (symbol ?? '').trim().toUpperCase()
    if (!sym) {
      setError('Choisis un symbole via Décisions ou Marché.')
      return
    }
    setBusy('gates')
    setError(null)
    try {
      const res = await runAgentCommand({
        cmd: 'detect_signal',
        args: { symbol: sym, timeframe: timeframe ?? '1h' },
      })
      if (!res.ok) {
        setError(res.error)
        return
      }
      const d = res.data as Record<string, unknown>
      setBriefLines([
        { label: 'Symbole', value: sym },
        { label: 'Portes', value: typeof d.decision === 'string' ? d.decision : '—' },
        { label: 'Direction', value: typeof d.direction === 'string' ? d.direction : '—' },
        { label: 'TF', value: String(timeframe ?? '1h') },
      ])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Verdict impossible')
    } finally {
      setBusy(null)
    }
  }

  async function onLabBrief() {
    const sym = (symbol ?? '').trim().toUpperCase()
    if (!sym) {
      setError('Choisis un symbole via Décisions ou Marché.')
      return
    }
    setBusy('lab')
    setError(null)
    setBriefLines(null)
    try {
      const batch = await strategyLabBriefPlaybook(sym, {
        timeframe: timeframe ?? '1h',
        limit: 500,
        rulesetId: DEFAULT_RULESET,
      })
      if (!batch.ok) {
        setError(batch.error)
        return
      }
      const lines: BriefLine[] = [
        { label: 'Symbole', value: sym },
        { label: 'Lab', value: 'ruleset + ablation + régimes' },
      ]
      for (const row of batch.results) {
        if (!row.ok) {
          lines.push({ label: row.cmd, value: row.error || 'erreur' })
          continue
        }
        if (row.cmd === 'run_ruleset_event_study') lines.push(...summarizeRulesetStudy(row.data))
        else if (row.cmd === 'run_ablation') lines.push(...summarizeAblation(row.data))
        else if (row.cmd === 'run_regime_slices') lines.push(...summarizeRegime(row.data))
      }
      setBriefLines(lines)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Lab brief impossible')
    } finally {
      setBusy(null)
    }
  }

  async function onWalkForward(opt: boolean) {
    const sym = (symbol ?? '').trim().toUpperCase()
    if (!sym) {
      setError('Choisis un symbole via Décisions ou Marché.')
      return
    }
    const cmd: AgentCommandName = opt ? 'run_walk_forward_opt' : 'run_walk_forward'
    setBusy(opt ? 'wfo' : 'wf')
    setError(null)
    setBriefLines(null)
    try {
      const res = await runAgentCommand({
        cmd,
        args: {
          symbol: sym,
          timeframe: timeframe ?? '1h',
          limit: 800,
          ruleset_id: DEFAULT_RULESET,
          mode: 'rolling',
          train_bars: 400,
          test_bars: 100,
          persist: false,
          ...(opt
            ? {
                objective: 'expectancy',
                min_trades: 3,
                grid: {
                  rvol_min: [1.2, 1.5, 2.0],
                  stop_atr: [1.0, 1.5],
                  target_atr: [2.0, 3.0],
                },
              }
            : { include_train: true }),
        },
      })
      if (!res.ok) {
        setError(res.error)
        return
      }
      setBriefLines([
        { label: 'Symbole', value: sym },
        ...summarizeWalkForward(res.data, opt ? 'WF-opt' : 'Walk-forward'),
      ])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Walk-forward impossible')
    } finally {
      setBusy(null)
    }
  }

  const online = !toolsError && tools != null
  const labReady =
    hasTool('run_ruleset_event_study') &&
    hasTool('run_ablation') &&
    hasTool('run_regime_slices')

  return (
    <aside className="agent-engine-panel panel">
      <header className="agent-atelier-panel-head">
        <div>
          <h2>Lecture moteur</h2>
          <p className="muted">
            Chiffres déterministes — le chat à gauche ne les recalcule pas.
          </p>
        </div>
        <span className={`agent-engine-status ${online ? 'is-on' : 'is-off'}`}>
          {toolsError ? 'Hors ligne' : online ? 'Connecté' : '…'}
        </span>
      </header>

      <div className="agent-engine-panel-body">
        <div className={`agent-engine-symbol ${symbol ? 'has-sym' : ''}`}>
          {symbol ? (
            <>
              <span className="agent-engine-symbol-label">Symbole en session</span>
              <span className="agent-engine-symbol-value">
                {symbol}
                <span className="muted"> · {timeframe ?? '1h'}</span>
              </span>
            </>
          ) : (
            <>
              <span className="agent-engine-symbol-label">Pas de symbole</span>
              <p className="muted agent-engine-symbol-hint">
                Ouvre une ligne dans{' '}
                <Link to="/app/decisions">Décisions</Link> puis clique{' '}
                <strong>Expliquer</strong>.
              </p>
            </>
          )}
        </div>

        <div className="agent-engine-panel-actions">
          <button
            type="button"
            className="agent-engine-cta"
            disabled={Boolean(busy) || !symbol}
            onClick={() => void onBrief()}
          >
            {busy === 'brief' ? 'Calcul…' : 'Brief multi-TF'}
          </button>
          <button
            type="button"
            className="agent-engine-cta is-secondary"
            disabled={Boolean(busy) || !symbol}
            onClick={() => void onDetect()}
          >
            {busy === 'gates' ? 'Calcul…' : 'Verdict portes'}
          </button>
        </div>

        <div className="agent-engine-panel-actions">
          <button
            type="button"
            className="agent-engine-cta is-secondary"
            disabled={Boolean(busy) || !symbol || !labReady}
            onClick={() => void onLabBrief()}
            title={labReady ? DEFAULT_RULESET : 'Tools Lab indisponibles côté moteur'}
          >
            {busy === 'lab' ? 'Lab…' : 'Brief Strategy Lab'}
          </button>
          <button
            type="button"
            className="agent-engine-cta is-secondary"
            disabled={Boolean(busy) || !symbol || !hasTool('run_walk_forward')}
            onClick={() => void onWalkForward(false)}
          >
            {busy === 'wf' ? 'WF…' : 'Walk-forward'}
          </button>
          <button
            type="button"
            className="agent-engine-cta is-secondary"
            disabled={Boolean(busy) || !symbol || !hasTool('run_walk_forward_opt')}
            onClick={() => void onWalkForward(true)}
          >
            {busy === 'wfo' ? 'Opt…' : 'WF-opt'}
          </button>
        </div>

        {error && <div className="banner error">{error}</div>}

        {briefLines && briefLines.length > 0 && (
          <div className="agent-engine-result">
            <h3>Résultat</h3>
            <dl className="agent-engine-brief">
              {briefLines.map((line, i) => (
                <div key={`${line.label}-${i}`}>
                  <dt>{line.label}</dt>
                  <dd>{line.value}</dd>
                </div>
              ))}
            </dl>
            <p className="muted" style={{ marginTop: '0.75rem', fontSize: '0.85rem' }}>
              Détail complet aussi sur <Link to="/app/backtests">Backtests</Link>.
            </p>
          </div>
        )}

        {featured.length > 0 && (
          <div className="agent-engine-caps">
            <h3>Ce que le moteur peut répondre</h3>
            <ul>
              {featured.map((t) => {
                const ux = TOOL_UX[t.name] ?? {
                  title: t.name,
                  blurb: t.description,
                }
                return (
                  <li key={t.name}>
                    <strong>{ux.title}</strong>
                    <span>{ux.blurb}</span>
                  </li>
                )
              })}
            </ul>
          </div>
        )}

        {tools && tools.length > 0 && (
          <details className="agent-engine-raw">
            <summary>
              Détail technique ({tools.length} commandes)
            </summary>
            <ul>
              {tools.map((t) => (
                <li key={t.name}>
                  <code>{t.name}</code>
                  <span>{TOOL_UX[t.name]?.title ?? t.description}</span>
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </aside>
  )
}
