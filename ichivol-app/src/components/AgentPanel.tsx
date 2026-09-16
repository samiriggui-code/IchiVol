import { useEffect, useRef, useState } from 'react'
import {
  askAgent,
  confirmAgentAction,
  type AgentCitation,
  type AgentChatResponse,
  type AgentDecisionPayload,
  type AgentMode,
} from '../lib/agent'
import { useAgentSession } from '../lib/agentSession'
import type { MarketSnapshot } from '../lib/marketSnapshot'
import { signalLabel } from '../lib/signals'

interface Props {
  snapshot: MarketSnapshot | null
  decisionPayload: AgentDecisionPayload | null
  /** Change à chaque openWithDecision → déclenche un envoi auto. */
  decisionRequestId: number
}

interface ChatEntry {
  role: 'user' | 'assistant'
  content: string
  citations?: AgentCitation[]
  disclaimer?: string
  pendingAction?: AgentChatResponse['pendingAction']
}

const MODES: {
  id: AgentMode
  label: string
  needsSnapshot?: boolean
  needsDecision?: boolean
}[] = [
  { id: 'explain_decision', label: 'Décision', needsDecision: true },
  { id: 'explain_signal', label: 'Signal', needsSnapshot: true },
  { id: 'research', label: 'Recherche' },
  { id: 'trade_idea', label: 'Idée', needsSnapshot: true },
]

export function AgentPanel({ snapshot, decisionPayload, decisionRequestId }: Props) {
  const { threadId, setThreadId, setAssumedSlots } = useAgentSession()
  const [mode, setMode] = useState<AgentMode>(() => {
    if (decisionPayload) return 'explain_decision'
    if (snapshot) return 'explain_signal'
    return 'research'
  })
  const [input, setInput] = useState('')
  const [history, setHistory] = useState<ChatEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [actionBusy, setActionBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const lastAutoId = useRef(0)

  const lastSignal = snapshot?.signals.length ? snapshot.signals[snapshot.signals.length - 1] : null

  async function onConfirmAction(
    pending: NonNullable<AgentChatResponse['pendingAction']>,
    confirm: boolean,
    entryIndex: number,
  ) {
    setActionBusy(true)
    setError(null)
    try {
      const res = await confirmAgentAction({
        intent: pending.intent,
        confirm,
        symbol: pending.symbol,
        timeframe: pending.timeframe,
        threadId: threadId ?? undefined,
        actionId: pending.actionId,
      })
      setHistory((h) => {
        const next = h.map((e, i) =>
          i === entryIndex ? { ...e, pendingAction: undefined } : e,
        )
        return [
          ...next,
          {
            role: 'assistant' as const,
            content: res.message ?? (confirm ? 'Action confirmée.' : 'Action annulée.'),
          },
        ]
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur action')
    } finally {
      setActionBusy(false)
    }
  }

  async function send(opts?: {
    forceMode?: AgentMode
    forceQuestion?: string
    forceDecision?: AgentDecisionPayload | null
  }) {
    const activeMode = opts?.forceMode ?? mode
    const question = (opts?.forceQuestion ?? input).trim()
    const decision = opts?.forceDecision !== undefined ? opts.forceDecision : decisionPayload

    if (activeMode === 'research' && !question) return
    if (activeMode === 'explain_decision' && !decision && !threadId) return
    if (activeMode === 'explain_signal' && !snapshot) return
    if (activeMode === 'trade_idea' && !snapshot) return

    setLoading(true)
    setError(null)
    if (!opts?.forceQuestion) setInput('')

    const defaultQ =
      activeMode === 'explain_decision'
        ? `Explique la décision sur ${decision?.symbol ?? ''}`
        : `Explique le signal sur ${snapshot?.symbol ?? ''}`

    const userEntry: ChatEntry = {
      role: 'user',
      content: question || defaultQ,
    }
    setHistory((h) => [...h, userEntry])

    try {
      const res = await askAgent({
        mode: activeMode,
        question,
        threadId: threadId ?? undefined,
        symbol: decision?.symbol ?? snapshot?.symbol,
        timeframe: decision?.timeframe ?? snapshot?.interval,
        history: undefined,
        decision: activeMode === 'explain_decision' && decision ? decision : undefined,
        live:
          activeMode === 'explain_signal' && snapshot
            ? {
                symbol: snapshot.symbol,
                interval: snapshot.interval,
                price: snapshot.live.price,
                bias: snapshot.live.bias,
                rvol: snapshot.live.rvol,
                lastSignal: lastSignal
                  ? {
                      kind: lastSignal.kind,
                      price: lastSignal.price,
                      rvol: lastSignal.rvol,
                      time: lastSignal.time,
                    }
                  : null,
              }
            : undefined,
        screenerRows:
          activeMode === 'trade_idea' && snapshot
            ? snapshot.rows.map((r) => ({
                symbol: r.symbol,
                bias: r.bias,
                rvol: r.rvol,
                lastSignal: r.lastSignal ? signalLabel(r.lastSignal.kind) : null,
                change24h: r.change24h,
              }))
            : undefined,
      })
      if (res.threadId) setThreadId(res.threadId)
      setAssumedSlots(res.assumedSymbol ?? null, res.assumedTimeframe ?? null)
      setHistory((h) => [
        ...h,
        {
          role: 'assistant',
          content: res.answer,
          citations: res.citations,
          disclaimer: res.disclaimer,
          pendingAction: res.pendingAction,
        },
      ])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur agent')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!decisionPayload || decisionRequestId === 0) return
    if (decisionRequestId === lastAutoId.current) return
    lastAutoId.current = decisionRequestId
    setMode('explain_decision')
    setHistory([])
    void send({
      forceMode: 'explain_decision',
      forceQuestion: '',
      forceDecision: decisionPayload,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only on new decision request
  }, [decisionPayload, decisionRequestId])

  return (
    <div className="agent-panel-body">
      <div className="agent-modes" role="group" aria-label="Mode agent">
        {MODES.map((m) => {
          const disabled =
            (m.needsSnapshot && !snapshot) || (m.needsDecision && !decisionPayload)
          return (
            <button
              key={m.id}
              type="button"
              className={m.id === mode ? 'is-active' : undefined}
              disabled={disabled}
              title={
                disabled
                  ? m.needsDecision
                    ? 'Ouvre via Expliquer sur Décisions / Journal'
                    : 'Disponible sur la page Marché'
                  : undefined
              }
              onClick={() => setMode(m.id)}
            >
              {m.label}
            </button>
          )
        })}
      </div>

      <div className="agent-history">
        {history.length === 0 && !loading && (
          <p className="muted">Aucune conversation pour l&apos;instant.</p>
        )}
        {history.map((entry, i) => (
          <div key={i} className={`agent-msg agent-msg-${entry.role}`}>
            <p>{entry.content}</p>
            {entry.disclaimer && <p className="agent-disclaimer">{entry.disclaimer}</p>}
            {entry.pendingAction && (
              <div className="agent-action-bar" style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <button
                  type="button"
                  className="ghost"
                  disabled={actionBusy}
                  onClick={() => void onConfirmAction(entry.pendingAction!, true, i)}
                >
                  Confirmer
                </button>
                <button
                  type="button"
                  className="ghost"
                  disabled={actionBusy}
                  onClick={() => void onConfirmAction(entry.pendingAction!, false, i)}
                >
                  Annuler
                </button>
              </div>
            )}
            {entry.citations && entry.citations.length > 0 && (
              <ul className="agent-citations">
                {entry.citations.map((c) => (
                  <li key={c.id}>
                    <a href={c.url} target="_blank" rel="noreferrer">
                      {c.title}
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
        {loading && <p className="muted">L&apos;agent réfléchit…</p>}
        {error && <div className="banner error">{error}</div>}
      </div>

      <div className="agent-input">
        <input
          type="text"
          value={input}
          placeholder={
            mode === 'research'
              ? 'Pose une question sur Ichimoku, RVOL…'
              : 'Question (optionnel)…'
          }
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && void send()}
        />
        <button type="button" className="ghost" disabled={loading} onClick={() => void send()}>
          {loading ? '…' : 'Envoyer'}
        </button>
      </div>
    </div>
  )
}
