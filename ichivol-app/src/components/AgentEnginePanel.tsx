import { useEffect, useState } from 'react'
import {
  fetchAgentTools,
  runAgentCommand,
  symbolBriefPlaybook,
  type AgentToolSpec,
} from '../lib/agentChannel'

type BriefLine = { label: string; value: string }

function summarizeContext(data: unknown): BriefLine[] {
  if (!data || typeof data !== 'object') return [{ label: 'contexte', value: '—' }]
  const d = data as Record<string, unknown>
  const pipeline = (d.pipeline ?? {}) as Record<string, unknown>
  const lines: BriefLine[] = [
    { label: 'combiner', value: typeof d.decision === 'string' ? d.decision : '—' },
    {
      label: 'portes',
      value: typeof pipeline.decision === 'string' ? String(pipeline.decision) : '—',
    },
    { label: 'direction', value: typeof d.direction === 'string' ? d.direction : '—' },
  ]
  if (typeof d.rvol === 'number') {
    lines.push({ label: 'RVOL', value: d.rvol.toFixed(2) })
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
    if (typeof r.error === 'string') return { label: tf, value: `err: ${r.error}` }
    const decision = typeof r.decision === 'string' ? r.decision : '—'
    const pipe = (r.pipeline ?? {}) as Record<string, unknown>
    const gate = typeof pipe.decision === 'string' ? String(pipe.decision) : null
    return {
      label: tf,
      value: gate ? `${decision} · portes ${gate}` : decision,
    }
  })
}

interface Props {
  symbol: string | null | undefined
  timeframe?: string | null
}

/**
 * Panneau moteur pour la page /app/agent — pas pour la bulle chat.
 * Lecture seule : batch / commandes déterministes.
 */
export function AgentEnginePanel({ symbol, timeframe }: Props) {
  const [tools, setTools] = useState<AgentToolSpec[] | null>(null)
  const [toolsError, setToolsError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
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

  async function onBrief() {
    const sym = (symbol ?? '').trim().toUpperCase()
    if (!sym) {
      setError('Ouvre une décision ou la page Marché pour un symbole.')
      return
    }
    setBusy(true)
    setError(null)
    setBriefLines(null)
    try {
      const batch = await symbolBriefPlaybook(sym, ['15m', '1h', '4h'])
      if (!batch.ok) {
        setError(batch.error)
        return
      }
      const lines: BriefLine[] = [{ label: 'symbole', value: sym }]
      for (const row of batch.results) {
        if (!row.ok) {
          lines.push({ label: row.cmd, value: `erreur: ${row.error}` })
          continue
        }
        if (row.cmd === 'get_symbol_context') lines.push(...summarizeContext(row.data))
        else if (row.cmd === 'compare_timeframes') lines.push(...summarizeCompare(row.data))
      }
      setBriefLines(lines)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'brief impossible')
    } finally {
      setBusy(false)
    }
  }

  async function onDetect() {
    const sym = (symbol ?? '').trim().toUpperCase()
    if (!sym) {
      setError('Ouvre une décision ou la page Marché pour un symbole.')
      return
    }
    setBusy(true)
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
        { label: 'symbole', value: sym },
        { label: 'portes', value: typeof d.decision === 'string' ? d.decision : '—' },
        { label: 'direction', value: typeof d.direction === 'string' ? d.direction : '—' },
      ])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'detect impossible')
    } finally {
      setBusy(false)
    }
  }

  return (
    <aside className="agent-engine-panel panel">
      <header className="panel-head">
        <h2>Moteur</h2>
        <span className="muted agent-engine-panel-meta">
          {toolsError ? 'offline' : tools ? `${tools.length} tools` : '…'}
        </span>
      </header>

      <div className="agent-engine-panel-body">
        <p className="muted agent-engine-panel-lead">
          Chiffres déterministes. Le chat à gauche explique — il ne recalcule pas.
        </p>

        <div className="agent-engine-panel-actions">
          <button
            type="button"
            className="ghost"
            disabled={busy || !symbol}
            onClick={() => void onBrief()}
          >
            {busy ? '…' : 'Brief symbole'}
          </button>
          <button
            type="button"
            className="ghost"
            disabled={busy || !symbol}
            onClick={() => void onDetect()}
          >
            Verdict portes
          </button>
        </div>

        {symbol ? (
          <p className="agent-engine-panel-sym">
            {symbol}
            {timeframe ? ` · ${timeframe}` : ''}
          </p>
        ) : (
          <p className="muted">Aucun symbole en session.</p>
        )}

        {error && <div className="banner error">{error}</div>}

        {briefLines && briefLines.length > 0 && (
          <dl className="agent-engine-brief">
            {briefLines.map((line, i) => (
              <div key={`${line.label}-${i}`}>
                <dt>{line.label}</dt>
                <dd>{line.value}</dd>
              </div>
            ))}
          </dl>
        )}

        {tools && tools.length > 0 && (
          <div className="agent-engine-panel-tools">
            <h3>Allowlist engine</h3>
            <ul>
              {tools.map((t) => (
                <li key={t.name} title={t.description}>
                  <code>{t.name}</code>
                  <span>{t.description}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </aside>
  )
}
