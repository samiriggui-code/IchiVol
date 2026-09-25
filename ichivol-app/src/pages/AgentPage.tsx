/**
 * Copilot — port littéral de design-reference/ichivol-workspace `copilot()` + page-head.
 * Classes HTML = maquette. Données / chat = engine (manquant → « — »).
 */

import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { askAgentStream } from '../lib/agent'
import { useAgentSession } from '../lib/agentSession'
import { getSettings } from '../lib/settings'
import './AgentPage.css'

type BadgeTone = 'green' | 'amber' | 'red' | 'gray' | ''

const SUGGESTIONS = [
  'Pourquoi BTC attend-il ?',
  'Quel est le risque du portefeuille ?',
  'Explique le setup BNB',
]

function badge(text: string, tone: BadgeTone = ''): ReactNode {
  let inferred = tone
  if (!inferred) {
    inferred = /PASSE|ACCEPTÉ|OUVERTE|VALIDÉ|DISPONIBLE/i.test(text)
      ? 'green'
      : /REFUS|BLOQU|ERREUR/i.test(text)
        ? 'red'
        : /PRUDENCE|ARMED|WATCH/i.test(text)
          ? 'amber'
          : ''
  }
  return <span className={`tag ${inferred}`.trim()}>{text}</span>
}

export function AgentPage() {
  const { history, setHistory, input, setInput, loading, setLoading, threadId, setThreadId } =
    useAgentSession()
  const [llmReady, setLlmReady] = useState<boolean | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getSettings()
      .then((s) => setLlmReady(Boolean(s.llmReady)))
      .catch(() => setLlmReady(false))
  }, [])

  const send = useCallback(
    async (text: string) => {
      const q = text.trim()
      if (!q || loading) return
      setError(null)
      setInput('')
      setHistory((h) => [...h, { role: 'user', content: q }])
      setLoading(true)
      try {
        let acc = ''
        const res = await askAgentStream(
          {
            question: q,
            threadId: threadId ?? undefined,
            mode: 'research',
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
          },
        )
        if (res.threadId) setThreadId(res.threadId)
        const finalText = res.answer || acc || '—'
        setHistory((h) => {
          const copy = [...h]
          const last = copy[copy.length - 1]
          if (last?.role === 'assistant') {
            copy[copy.length - 1] = { ...last, content: finalText }
          } else {
            copy.push({ role: 'assistant', content: finalText })
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

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    void send(input)
  }

  return (
    <div className="copilot-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">08 / ICHIVOL WORKSPACE</div>
          <h1>Copilot</h1>
          <p className="subtitle">Explorer et expliquer chaque décision.</p>
        </div>
        <div className="actions">{badge('APERÇU DU COPILOT', 'gray')}</div>
      </div>

      <div className="grid">
        <section className="card chat">
          <div className="card-head">
            <h2>Une seconde lecture</h2>
            {badge('APERÇU DU COPILOT', 'gray')}
          </div>
          <div className="chat-log" id="chat-log">
            <div className="bubble">
              <b>Votre décision, rendue lisible.</b>
              <p>
                Choisissez une question pour explorer les données. Le Copilot explique les
                signaux et le risque ; la validation reste au moteur.
              </p>
              <span className="tag gray">
                {llmReady === null
                  ? '—'
                  : llmReady
                    ? 'LLM connecté'
                    : 'Claude non connecté'}
              </span>
            </div>
            {history.map((m, i) => (
              <div className="bubble" key={`${m.role}-${i}`}>
                <span className="eyebrow">{m.role === 'user' ? 'VOUS' : 'COPILOT'}</span>
                <p>{m.content || '—'}</p>
              </div>
            ))}
            {error && (
              <div className="bubble">
                <p style={{ color: 'var(--red)' }}>{error}</p>
              </div>
            )}
          </div>
          <form id="chat-form" onSubmit={onSubmit}>
            <input
              id="chat-input"
              placeholder="Pourquoi BTC n’est-il pas encore déclenché ?"
              aria-label="Votre question"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              required
              disabled={loading}
            />
            <button className="primary" type="submit" disabled={loading}>
              {loading ? '…' : 'Envoyer ↗'}
            </button>
          </form>
        </section>

        <section className="card">
          <div className="card-head">
            <h2>Explorer une décision</h2>
          </div>
          <div className="card-body">
            {SUGGESTIONS.map((q, i) => (
              <button
                key={q}
                type="button"
                className="suggestion"
                onClick={() => void send(q)}
                disabled={loading}
                data-prompt={i}
              >
                {q}
              </button>
            ))}
            <div style={{ marginTop: 30 }}>
              <div className="statline">
                <span>Lire le contexte</span>
                <b>{badge('DISPONIBLE', 'gray')}</b>
              </div>
              <div className="statline">
                <span>Expliquer un refus</span>
                <b>{badge('DISPONIBLE', 'gray')}</b>
              </div>
              <div className="statline">
                <span>Passer un ordre</span>
                <b>{badge('BLOQUÉ')}</b>
              </div>
            </div>
            <p style={{ fontSize: 11, color: 'var(--muted)' }}>
              Les réponses passent par le moteur / LLM configuré. Sans clé : « — ».
            </p>
          </div>
        </section>
      </div>
    </div>
  )
}
