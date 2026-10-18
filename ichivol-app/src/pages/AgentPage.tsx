/**
 * Copilot — le chat d'Ève : il explique les signaux, les décisions et le risque avec un modèle de langage
 * (choisi dans Paramètres › Modèles d'IA). Il ne passe jamais d'ordre.
 */

import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { askAgentStream, type AgentMode } from '../lib/agent'
import { FactsheetAnswer } from '../components/FactsheetAnswer'
import { useAgentSession } from '../lib/agentSession'
import { getSettings } from '../lib/settings'
import './AgentPage.css'

type ToolActivity = {
  name: string
  status: 'running' | 'ok' | 'error'
  ms?: number
}

const SUGGESTIONS = [
  'Pourquoi BTC attend-il ?',
  'Quel est le risque du portefeuille ?',
  'Explique le setup BNB',
]

export function AgentPage() {
  const { history, setHistory, input, setInput, loading, setLoading, threadId, setThreadId, launch, takeLaunch } =
    useAgentSession()
  const [llmReady, setLlmReady] = useState<boolean | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [toolActivity, setToolActivity] = useState<ToolActivity[]>([])

  useEffect(() => {
    getSettings()
      .then((s) => setLlmReady(Boolean(s.llmReady)))
      .catch(() => setLlmReady(false))
  }, [])

  const send = useCallback(
    async (text: string, mode: AgentMode = 'research') => {
      const q = text.trim()
      if (!q || loading) return
      setError(null)
      setInput('')
      setToolActivity([])
      setHistory((h) => [...h, { role: 'user', content: q }])
      setLoading(true)
      try {
        let acc = ''
        const res = await askAgentStream(
          {
            question: q,
            threadId: threadId ?? undefined,
            mode,
          },
          {
            onText: (t) => {
              acc += t
              setHistory((h) => {
                const copy = [...h]
                const last = copy[copy.length - 1]
                if (last?.role === 'assistant') {
                  copy[copy.length - 1] = { ...last, content: acc }
                } else {
                  copy.push({ role: 'assistant', content: acc })
                }
                return copy
              })
            },
            onToolStart: (name) => {
              setToolActivity((prev) => [...prev, { name, status: 'running' }])
            },
            onToolEnd: (name, ok, ms) => {
              setToolActivity((prev) => {
                const copy = [...prev]
                for (let i = copy.length - 1; i >= 0; i--) {
                  if (copy[i].name === name && copy[i].status === 'running') {
                    copy[i] = { name, status: ok ? 'ok' : 'error', ms }
                    break
                  }
                }
                return copy
              })
            },
          },
        )
        if (res.threadId) setThreadId(res.threadId)
        const finalText = res.answer || acc || '—'
        setHistory((h) => {
          const copy = [...h]
          const last = copy[copy.length - 1]
          if (last?.role === 'assistant') {
            copy[copy.length - 1] = {
              ...last,
              content: finalText,
              toolCalls: res.toolCalls,
              factsheet: res.factsheet,
            }
          } else {
            copy.push({ role: 'assistant', content: finalText, toolCalls: res.toolCalls, factsheet: res.factsheet })
          }
          return copy
        })
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Copilot indisponible')
        setHistory((h) => [...h, { role: 'assistant', content: '—' }])
      } finally {
        setLoading(false)
      }
    },
    [loading, setHistory, setInput, setLoading, setThreadId, threadId],
  )

  // Une autre page a demandé une explication (« Demander à Ève d'expliquer ») : on l'envoie, ou on la prépare.
  useEffect(() => {
    if (!launch || !takeLaunch(launch.requestId)) return
    if (launch.autoSend) void send(launch.prompt, launch.mode)
    else setInput(launch.prompt)
  }, [launch, takeLaunch, send, setInput])

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    void send(input)
  }

  const modelState =
    llmReady === null ? (
      <span className="iv-chip is-muted">
        <i className="iv-dot is-off" aria-hidden="true" />—
      </span>
    ) : llmReady ? (
      <span className="iv-chip is-mint">
        <i className="iv-dot" aria-hidden="true" />
        Modèle connecté
      </span>
    ) : (
      <span className="iv-chip is-amber">
        <i className="iv-dot is-amber" aria-hidden="true" />
        Modèle non connecté
      </span>
    )

  return (
    <div className="copilot-page">
      <header className="iv-ph">
        <div>
          <div className="iv-meta">Copilot · le chat d’Ève</div>
          <h1>Copilot</h1>
          <p>Le chat d’Ève : explorer et expliquer chaque décision.</p>
        </div>
        <div className="iv-ph-act">{modelState}</div>
      </header>

      <div className="iv-grid">
        <section className="iv-card iv-s8 iv-m-s12 cp-chat">
          <div className="iv-card-head">
            <div className="iv-card-tabs">
              <span className="iv-card-tab is-on">Chat d’Ève</span>
            </div>
            <div className="iv-card-tools">Il explique, il ne passe jamais d’ordre</div>
          </div>
          <div className="cp-log" id="chat-log" aria-live="polite">
            {history.length === 0 ? (
              <div className="cp-msg is-eve">
                <span className="cp-who">Ève</span>
                <div className="cp-bb">
                  <b>Votre décision, rendue lisible.</b>
                  <p>
                    Choisissez une question pour explorer les données. Le Copilot explique les signaux et le risque ;
                    les décisions de trade restent à Ève et au Risk Kernel.
                  </p>
                </div>
              </div>
            ) : null}
            {history.map((m, i) => (
              <div className={`cp-msg ${m.role === 'user' ? 'is-me' : 'is-eve'}`} key={`${m.role}-${i}`}>
                <span className="cp-who">{m.role === 'user' ? 'Vous' : 'Ève'}</span>
                <div className="cp-bb">
                  {m.role === 'assistant' && m.factsheet && !m.factsheet.fallback ? (
                    <FactsheetAnswer view={m.factsheet} />
                  ) : (
                    <p>{m.content || '—'}</p>
                  )}
                </div>
                {m.role === 'assistant' && m.toolCalls && m.toolCalls.length > 0 && (
                  <ul className="cp-tools">
                    {m.toolCalls.map((t, j) => (
                      <li key={`${t.name}-${j}`} className={`iv-chip ${t.ok ? '' : 'is-sell'}`.trim()}>
                        <code>{t.name}</code>
                        <span className={t.ok ? 'ok' : 'neg'}>{t.ok ? 'OK' : 'ERREUR'}</span>
                        <span className="dim">{t.ms} ms</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
            {(loading || toolActivity.length > 0) && toolActivity.length > 0 && (
              <div className="cp-msg is-eve is-live">
                <span className="cp-who">Outils</span>
                <ul className="cp-tools">
                  {toolActivity.map((t, j) => (
                    <li
                      key={`${t.name}-${j}-${t.status}`}
                      className={`iv-chip ${t.status === 'running' ? 'is-amber' : t.status === 'ok' ? '' : 'is-sell'}`.trim()}
                    >
                      <code>{t.name}</code>
                      <span className={t.status === 'running' ? 'warn' : t.status === 'ok' ? 'ok' : 'neg'}>
                        {t.status === 'running' ? '…' : t.status === 'ok' ? 'OK' : 'ERREUR'}
                      </span>
                      {t.ms != null && <span className="dim">{t.ms} ms</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {error && (
              <p className="iv-empty is-error cp-error" role="alert">
                {error}
              </p>
            )}
          </div>
          <form id="chat-form" className="cp-composer" onSubmit={onSubmit}>
            <input
              id="chat-input"
              className="iv-input"
              placeholder="Pourquoi BTC n’est-il pas encore déclenché ?"
              aria-label="Votre question"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              required
              disabled={loading}
            />
            <button className="iv-btn iv-btn--primary" type="submit" disabled={loading}>
              {loading ? '…' : 'Envoyer ↗'}
            </button>
          </form>
        </section>

        <div className="iv-s4 iv-m-s12 cp-side">
          <section className="iv-card">
            <div className="iv-card-head">
              <div className="iv-card-tabs">
                <span className="iv-card-tab is-on">Explorer une décision</span>
              </div>
            </div>
            <div className="iv-card-body cp-quick">
              {SUGGESTIONS.map((q, i) => (
                <button
                  key={q}
                  type="button"
                  className="iv-btn cp-q"
                  onClick={() => void send(q)}
                  disabled={loading}
                  data-prompt={i}
                >
                  {q}
                </button>
              ))}
            </div>
          </section>

          <section className="iv-card">
            <div className="iv-card-head">
              <div className="iv-card-tabs">
                <span className="iv-card-tab is-on">Outils</span>
              </div>
            </div>
            <div className="iv-card-body">
              <div className="iv-row">
                <span>Lire le contexte</span>
                <span className="iv-row-v ok">disponible</span>
              </div>
              <div className="iv-row">
                <span>Expliquer un refus</span>
                <span className="iv-row-v ok">disponible</span>
              </div>
              <div className="iv-row">
                <span>Passer un ordre</span>
                <span className="iv-row-v">
                  <span className="iv-tag is-sell">Bloqué</span>
                </span>
              </div>
            </div>
          </section>

          <aside className="apex-card cp-apex">
            <div className="iv-label">Une seconde lecture</div>
            <p className="iv-note cp-apex-note">
              Le Copilot utilise le modèle de langage choisi dans Paramètres › Modèles d’IA. Sans clé, il ne répond pas.
            </p>
            <div className="apex-card-foot">
              <span className="apex-card-sig">ichivol</span>
              {modelState}
            </div>
          </aside>
        </div>
      </div>
    </div>
  )
}
