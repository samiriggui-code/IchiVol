import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  fetchAgentTools,
  runAgentCommand,
  symbolBriefPlaybook,
  type AgentToolSpec,
} from '../lib/agentChannel'

type BriefLine = { label: string; value: string }

/** Libellés métier — on n’expose pas le jargon API en premier. */
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
    blurb: 'Comparer Ichimoku / RVOL / pipeline sur l’historique.',
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
  const [busy, setBusy] = useState<'brief' | 'gates' | null>(null)
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

  const featured = useMemo(() => {
    if (!tools) return []
    const order = [
        'get_symbol_context',
      'detect_signal',
      'compare_timeframes',
      'scan_market',
      'get_correlations',
      'get_news',
      'get_calendar',
      'run_backtest',
    ]
    const byName = new Map(tools.map((t) => [t.name, t]))
    return order
      .map((name) => byName.get(name))
      .filter((t): t is AgentToolSpec => Boolean(t))
      .slice(0, 6)
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

  const online = !toolsError && tools != null

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
                  <span>{t.description}</span>
                </li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </aside>
  )
}
