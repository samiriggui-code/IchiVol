import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  askAgent,
  confirmAgentAction,
  type AgentChatResponse,
  type AgentDecisionPayload,
  type AgentLivePayload,
  type AgentMode,
} from '../lib/agent'
import { useAgentSession } from '../lib/agentSession'
import type { MarketSnapshot } from '../lib/marketSnapshot'
import { signalLabel } from '../lib/signals'

interface Props {
  snapshot: MarketSnapshot | null
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

export function AgentPanel({ snapshot }: Props) {
  const {
    threadId,
    setThreadId,
    setAssumedSlots,
    decisionPayload,
    launch,
    clearLaunch,
    takeLaunch,
    mode,
    setMode,
    input,
    setInput,
    history,
    setHistory,
    loading,
    setLoading,
    bumpChatGeneration,
    getChatGeneration,
    actionBusy,
    setActionBusy,
    error,
    setError,
  } = useAgentSession()

  const lastSignal = snapshot?.signals.length ? snapshot.signals[snapshot.signals.length - 1] : null

  const liveFromSnapshot: AgentLivePayload | null = snapshot
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
    : null

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
    forceLive?: AgentLivePayload | null
  }) {
    const activeMode = opts?.forceMode ?? mode
    const question = (opts?.forceQuestion ?? input).trim()
    const decision = opts?.forceDecision !== undefined ? opts.forceDecision : decisionPayload
    const live = opts?.forceLive !== undefined ? opts.forceLive : liveFromSnapshot

    if (activeMode === 'research' && !question) return
    if (activeMode === 'explain_decision' && !decision && !threadId) return
    if (activeMode === 'explain_signal' && !live) return
    if (activeMode === 'trade_idea' && !snapshot) return

    setLoading(true)
    setError(null)
    if (!opts?.forceQuestion) setInput('')

    const gen = bumpChatGeneration()
    const defaultQ =
      activeMode === 'explain_decision'
        ? `Explique la décision sur ${decision?.symbol ?? ''}`
        : `Explique le signal sur ${live?.symbol ?? snapshot?.symbol ?? ''}`

    setHistory((h) => [
      ...h,
      {
        role: 'user',
        content: question || defaultQ,
      },
    ])

    try {
      const res = await askAgent({
        mode: activeMode,
        question: question || defaultQ,
        threadId: threadId ?? undefined,
        symbol: decision?.symbol ?? live?.symbol ?? snapshot?.symbol,
        timeframe: decision?.timeframe ?? live?.interval ?? snapshot?.interval,
        history: undefined,
        decision: activeMode === 'explain_decision' && decision ? decision : undefined,
        live: activeMode === 'explain_signal' && live ? live : undefined,
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
      if (gen !== getChatGeneration()) return
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
      if (gen !== getChatGeneration()) return
      setError(e instanceof Error ? e.message : 'Erreur agent')
    } finally {
      if (gen === getChatGeneration()) setLoading(false)
    }
  }

  useEffect(() => {
    if (!launch || !takeLaunch(launch.requestId)) return
    setMode(launch.mode)
    if (launch.autoSend) {
      setInput('')
      void send({
        forceMode: launch.mode,
        forceQuestion: launch.prompt,
        forceDecision: launch.decision,
        forceLive: launch.live,
      }).finally(() => clearLaunch())
    } else {
      setInput(launch.prompt)
      clearLaunch()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- launch.requestId only
  }, [launch])

  const hasDecision = Boolean(decisionPayload || launch?.decision)
  const hasLive = Boolean(snapshot || launch?.live)

  return (
    <div className="agent-panel-body">
      <div className="agent-modes" role="group" aria-label="Mode agent">
        {MODES.map((m) => {
          const disabled =
            (m.needsSnapshot && !hasLive && m.id === 'explain_signal') ||
            (m.needsSnapshot && !snapshot && m.id === 'trade_idea') ||
            (m.needsDecision && !hasDecision)
          return (
            <button
              key={m.id}
              type="button"
              className={m.id === mode ? 'is-active' : undefined}
              disabled={disabled}
              title={
                disabled
                  ? m.needsDecision
                    ? 'Lance depuis Décisions / Journal / Watchlist'
                    : 'Disponible depuis Marché'
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
          <div className="agent-empty">
            <p className="agent-empty-title">Prêt à expliquer une décision</p>
            <p className="muted">
              Tu n’es pas censé inventer la question. Lance depuis une page métier —
              le prompt arrive déjà rempli. Quitter la page ne perd plus la conversation.
            </p>
            <div className="agent-empty-actions">
              <Link to="/app/decisions" className="ghost">
                Ouvrir Décisions
              </Link>
              <Link to="/app/journal" className="ghost">
                Ouvrir Journal
              </Link>
              <Link to="/app/watchlist" className="ghost">
                Watchlist
              </Link>
            </div>
          </div>
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
        <textarea
          value={input}
          rows={mode === 'research' || input.length > 80 ? 3 : 2}
          placeholder={
            mode === 'research'
              ? 'Pose une question sur Ichimoku, RVOL…'
              : 'Affiner la question (optionnel)…'
          }
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              void send()
            }
          }}
        />
        <button type="button" className="ghost" disabled={loading} onClick={() => void send()}>
          {loading ? '…' : 'Envoyer'}
        </button>
      </div>
    </div>
  )
}
