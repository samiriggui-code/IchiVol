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
    {
      label: 'combiner',
      value: typeof d.decision === 'string' ? d.decision : '—',
    },
    {
      label: 'portes',
      value: typeof pipeline.decision === 'string' ? String(pipeline.decision) : '—',
    },
    {
      label: 'direction',
      value: typeof d.direction === 'string' ? d.direction : '—',
    },
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
 * Découverte des tools engine + brief déterministe (sans LLM).
 * Le moteur calcule ; cette bande affiche le résultat brut.
 */
export function AgentEngineStrip({ symbol, timeframe }: Props) {
  const [tools, setTools] = useState<AgentToolSpec[] | null>(null)
  const [toolsError, setToolsError] = useState<string | null>(null)
  const [briefBusy, setBriefBusy] = useState(false)
  const [briefError, setBriefError] = useState<string | null>(null)
  const [briefLines, setBriefLines] = useState<BriefLine[] | null>(null)
  const [showTools, setShowTools] = useState(false)

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
      setBriefError('Choisis un symbole (Décisions / Marché).')
      return
    }
    setBriefBusy(true)
    setBriefError(null)
    setBriefLines(null)
    try {
      const batch = await symbolBriefPlaybook(sym, ['15m', '1h', '4h'])
      if (!batch.ok) {
        setBriefError(batch.error)
        return
      }
      const lines: BriefLine[] = [{ label: 'symbole', value: sym }]
      for (const row of batch.results) {
        if (!row.ok) {
          lines.push({ label: row.cmd, value: `erreur: ${row.error}` })
          continue
        }
        if (row.cmd === 'get_symbol_context') {
          lines.push(...summarizeContext(row.data))
        } else if (row.cmd === 'compare_timeframes') {
          lines.push(...summarizeCompare(row.data))
        }
      }
      setBriefLines(lines)
    } catch (e) {
      setBriefError(e instanceof Error ? e.message : 'brief impossible')
    } finally {
      setBriefBusy(false)
    }
  }

  async function onDetect() {
    const sym = (symbol ?? '').trim().toUpperCase()
    if (!sym) {
      setBriefError('Choisis un symbole (Décisions / Marché).')
      return
    }
    setBriefBusy(true)
    setBriefError(null)
    try {
      const res = await runAgentCommand({
        cmd: 'detect_signal',
        args: { symbol: sym, timeframe: timeframe ?? '1h' },
      })
      if (!res.ok) {
        setBriefError(res.error)
        return
      }
      const d = res.data as Record<string, unknown>
      setBriefLines([
        { label: 'symbole', value: sym },
        { label: 'portes', value: typeof d.decision === 'string' ? d.decision : '—' },
        { label: 'direction', value: typeof d.direction === 'string' ? d.direction : '—' },
        {
          label: 'source',
          value: 'detect_signal (engine, pas LLM)',
        },
      ])
    } catch (e) {
      setBriefError(e instanceof Error ? e.message : 'detect impossible')
    } finally {
      setBriefBusy(false)
    }
  }

  const toolCount = tools?.length ?? 0

  return (
    <div className="agent-engine-strip">
      <div className="agent-engine-strip-bar">
        <button
          type="button"
          className="ghost agent-engine-chip"
          disabled={!tools && !toolsError}
          onClick={() => setShowTools((v) => !v)}
          title={toolsError ?? 'Tools du moteur Python'}
        >
          Engine {toolsError ? 'offline' : `${toolCount} tools`}
        </button>
        <button
          type="button"
          className="ghost agent-engine-chip"
          disabled={briefBusy || !symbol}
          onClick={() => void onBrief()}
          title="get_symbol_context + compare_timeframes (batch)"
        >
          {briefBusy ? '…' : 'Brief symbole'}
        </button>
        <button
          type="button"
          className="ghost agent-engine-chip"
          disabled={briefBusy || !symbol}
          onClick={() => void onDetect()}
          title="detect_signal — verdict portes condensé"
        >
          Portes
        </button>
      </div>

      {showTools && tools && (
        <ul className="agent-engine-tools">
          {tools.map((t) => (
            <li key={t.name} title={t.description}>
              {t.name}
            </li>
          ))}
        </ul>
      )}
      {showTools && toolsError && (
        <p className="muted agent-engine-hint">Canal engine : {toolsError}</p>
      )}

      {briefError && <div className="banner error agent-engine-brief-err">{briefError}</div>}
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
      <p className="muted agent-engine-hint">
        Chiffres = moteur Python. Le chat LLM explique, ne recalcule pas.
      </p>
    </div>
  )
}
