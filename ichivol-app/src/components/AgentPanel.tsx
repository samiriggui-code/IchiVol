import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { PaperConfirmSheet } from './PaperConfirmSheet'
import {
  askAgentStream,
  confirmAgentAction,
  type AgentChatResponse,
  type AgentDecisionPayload,
  type AgentLivePayload,
  type AgentMode,
} from '../lib/agent'
import { useAgentSession } from '../lib/agentSession'
import type { MarketSnapshot } from '../lib/marketSnapshot'
import { proposePaperTrade, type OrderIntent } from '../lib/paper'
import { getSettings, type LlmConnection, type LlmProvider } from '../lib/settings'
import { signalLabel } from '../lib/signals'

interface Props {
  snapshot: MarketSnapshot | null
}

const PROVIDER_LABEL: Record<LlmProvider, string> = {
  openrouter: 'OpenRouter',
  anthropic: 'Claude (Anthropic) · agent à outils',
  openai: 'OpenAI',
}
const PROVIDER_STORAGE_KEY = 'ichivol.agent.provider'

function readStoredProvider(): LlmProvider | null {
  try {
    const v = localStorage.getItem(PROVIDER_STORAGE_KEY)
    return v === 'anthropic' || v === 'openai' || v === 'openrouter' ? v : null
  } catch {
    return null
  }
}

export function AgentPanel({ snapshot }: Props) {
  const {
    threadId,
    setThreadId,
    setAssumedSlots,
    decisionPayload,
    launch,
    clearLaunch,
    takeLaunch,
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

  // Bulle en direct pendant que Claude écrit / interroge le moteur.
  const [liveText, setLiveText] = useState('')
  const [liveTool, setLiveTool] = useState<string | null>(null)

  /** open_paper_position → même récap qty/stop/cash que Décisions. */
  const [paperSheet, setPaperSheet] = useState<{
    pending: NonNullable<AgentChatResponse['pendingAction']>
    intent: OrderIntent
    entryIndex: number
  } | null>(null)
  const [paperConfirming, setPaperConfirming] = useState(false)
  const [paperConfirmError, setPaperConfirmError] = useState<string | null>(null)

  // Fournisseurs ayant une clé (personnelle et/ou serveur) : on choisit par message, sans toucher aux réglages.
  const [connections, setConnections] = useState<LlmConnection[]>([])
  const [providerChoice, setProviderChoice] = useState<LlmProvider | null>(readStoredProvider)
  useEffect(() => {
    let cancelled = false
    getSettings()
      .then((s) => {
        if (!cancelled) setConnections((s.llmConnections ?? []).filter((c) => c.connected))
      })
      .catch(() => {
        // Sans réglages lisibles, le sélecteur reste masqué et le serveur garde le fournisseur actif.
      })
    return () => {
      cancelled = true
    }
  }, [])
  const activeProvider = connections.find((c) => c.active)?.provider ?? null
  const chosenProvider =
    providerChoice && connections.some((c) => c.provider === providerChoice)
      ? providerChoice
      : activeProvider
  function onProviderChange(next: LlmProvider) {
    setProviderChoice(next)
    try {
      localStorage.setItem(PROVIDER_STORAGE_KEY, next)
    } catch {
      // Stockage indisponible (navigation privée) : le choix vaut pour la session.
    }
  }

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

  function clearPendingFromHistory(entryIndex: number) {
    setHistory((h) =>
      h.map((e, i) => (i === entryIndex ? { ...e, pendingAction: undefined } : e)),
    )
  }

  async function onConfirmAction(
    pending: NonNullable<AgentChatResponse['pendingAction']>,
    confirm: boolean,
    entryIndex: number,
  ) {
    // Paper : d’abord le sheet récap (qty/stop/liquidités), puis confirm API.
    if (confirm && pending.intent === 'open_paper_position') {
      if (!pending.symbol) {
        setError('Symbole manquant pour ouvrir en paper')
        return
      }
      setActionBusy(true)
      setError(null)
      setPaperConfirmError(null)
      try {
        const intent = await proposePaperTrade(pending.symbol, pending.timeframe ?? '1h')
        setPaperSheet({ pending, intent, entryIndex })
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Proposition paper impossible')
      } finally {
        setActionBusy(false)
      }
      return
    }

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
      clearPendingFromHistory(entryIndex)
      setHistory((h) => [
        ...h,
        {
          role: 'assistant' as const,
          content: res.message ?? (confirm ? 'Action confirmée.' : 'Action annulée.'),
        },
      ])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur action')
    } finally {
      setActionBusy(false)
    }
  }

  async function executePaperSheetConfirm() {
    if (!paperSheet) return
    const { pending, entryIndex } = paperSheet
    setPaperConfirming(true)
    setPaperConfirmError(null)
    setError(null)
    try {
      const res = await confirmAgentAction({
        intent: pending.intent,
        confirm: true,
        symbol: pending.symbol,
        timeframe: pending.timeframe,
        threadId: threadId ?? undefined,
        actionId: pending.actionId,
      })
      clearPendingFromHistory(entryIndex)
      setPaperSheet(null)
      setHistory((h) => [
        ...h,
        {
          role: 'assistant' as const,
          content: res.message ?? 'Position paper ouverte.',
        },
      ])
    } catch (e) {
      setPaperConfirmError(e instanceof Error ? e.message : 'Ouverture paper impossible')
    } finally {
      setPaperConfirming(false)
    }
  }

  async function cancelPaperSheet() {
    if (!paperSheet || paperConfirming) return
    const { pending, entryIndex } = paperSheet
    setPaperSheet(null)
    setPaperConfirmError(null)
    setActionBusy(true)
    try {
      await confirmAgentAction({
        intent: pending.intent,
        confirm: false,
        symbol: pending.symbol,
        timeframe: pending.timeframe,
        threadId: threadId ?? undefined,
        actionId: pending.actionId,
      })
      clearPendingFromHistory(entryIndex)
      setHistory((h) => [
        ...h,
        { role: 'assistant' as const, content: 'Ouverture paper annulée.' },
      ])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Annulation impossible')
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
    // Claude choisit ses outils : sans « Expliquer » forcé, c'est une question libre.
    const activeMode = opts?.forceMode ?? 'research'
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
      const res = await askAgentStream(
        {
        mode: activeMode,
        provider: chosenProvider ?? undefined,
        question: question || defaultQ,
        threadId: threadId ?? undefined,
        symbol: decision?.symbol ?? live?.symbol ?? snapshot?.symbol,
        timeframe: decision?.timeframe ?? live?.interval ?? snapshot?.interval,
        history: undefined,
        decision: decision ?? undefined,
        live: live ?? undefined,
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
        },
        {
          onText: (d) => {
            if (gen === getChatGeneration()) setLiveText((t) => t + d)
          },
          // Le texte avant un appel d'outil est du « je regarde… » : on l'efface.
          onToolStart: (name) => {
            setLiveText('')
            setLiveTool(name)
          },
          onToolEnd: () => setLiveTool(null),
        },
      )
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
          toolCalls: res.toolCalls,
          pendingAction: res.pendingAction,
        },
      ])
    } catch (e) {
      if (gen !== getChatGeneration()) return
      setError(e instanceof Error ? e.message : 'Erreur agent')
    } finally {
      setLiveText('')
      setLiveTool(null)
      if (gen === getChatGeneration()) setLoading(false)
    }
  }

  useEffect(() => {
    if (!launch || !takeLaunch(launch.requestId)) return
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

  return (
    <div className="agent-panel-body">
      <div className="agent-history">
        {history.length === 0 && !loading && (
          <div className="agent-empty">
            <p className="agent-empty-title">Pose ta question au moteur</p>
            <p className="muted">
              Claude interroge le moteur IchiVol (scan, décision, multi-timeframe,
              backtest, walk-forward) en lecture seule, puis explique. Tu peux aussi
              lancer « Expliquer » depuis une page métier.
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
            {entry.toolCalls && entry.toolCalls.length > 0 && (
              <p className="muted" style={{ fontSize: '0.78rem' }}>
                Moteur interrogé :{' '}
                {entry.toolCalls
                  .map((t) => `${t.name}${t.ok ? '' : ' ✗'} (${(t.ms / 1000).toFixed(1)}s)`)
                  .join(' · ')}
              </p>
            )}
            {entry.disclaimer && <p className="agent-disclaimer">{entry.disclaimer}</p>}
            {entry.pendingAction && (
              <div className="agent-action-bar" style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <button
                  type="button"
                  className="ghost"
                  disabled={actionBusy || !!paperSheet}
                  onClick={() => void onConfirmAction(entry.pendingAction!, true, i)}
                >
                  {entry.pendingAction.intent === 'open_paper_position'
                    ? 'Vérifier…'
                    : 'Confirmer'}
                </button>
                <button
                  type="button"
                  className="ghost"
                  disabled={actionBusy || !!paperSheet}
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
        {loading && liveText && (
          <div className="agent-msg agent-msg-assistant">
            <p>{liveText}</p>
          </div>
        )}
        {loading && liveTool && (
          <p className="muted">Interrogation du moteur : {liveTool}…</p>
        )}
        {loading && !liveText && !liveTool && (
          <p className="muted">L&apos;agent réfléchit…</p>
        )}
        {error && <div className="banner error">{error}</div>}
      </div>

      {connections.length > 1 && (
        <div className="agent-provider" style={{ padding: '0 0.65rem 0.35rem' }}>
          <label className="muted" style={{ fontSize: '0.78rem' }}>
            Modèle :{' '}
            <select
              value={chosenProvider ?? ''}
              onChange={(e) => onProviderChange(e.target.value as LlmProvider)}
              disabled={loading}
            >
              {connections.map((c) => (
                <option key={c.provider} value={c.provider}>
                  {PROVIDER_LABEL[c.provider]}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      <div className="agent-input">
        <textarea
          value={input}
          rows={input.length > 80 ? 3 : 2}
          placeholder="Ex. : BTCUSDT en 1h, qu'en dit le moteur ? Compare 15m/1h/4h."
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

      {paperSheet && (
        <PaperConfirmSheet
          symbolLabel={paperSheet.pending.symbol?.replace(/USDT$/i, '') ?? '—'}
          intent={paperSheet.intent}
          confirming={paperConfirming}
          error={paperConfirmError}
          onConfirm={() => void executePaperSheetConfirm()}
          onCancel={() => void cancelPaperSheet()}
        />
      )}
    </div>
  )
}
