import { Link, useLocation } from 'react-router-dom'
import { useMarketSnapshot } from '../lib/marketSnapshot'
import { useAgentSession } from '../lib/agentSession'
import { AgentPanel } from './AgentPanel'
import { IconChat } from './NavIcons'

export function AgentChat() {
  const location = useLocation()
  const onAtelier = location.pathname.startsWith('/app/agent')
  const { snapshot } = useMarketSnapshot()
  const {
    open,
    setOpen,
    decisionPayload,
    decisionRequestId,
    assumedSymbol,
    assumedTimeframe,
  } = useAgentSession()

  const titleSymbol = assumedSymbol ?? decisionPayload?.symbol ?? snapshot?.symbol
  const titleTf =
    assumedTimeframe ?? decisionPayload?.timeframe ?? snapshot?.interval

  // Sur /app/agent la page plein écran est le siège ; pas de double UI.
  if (onAtelier) return null

  return (
    <div className="agent-chat">
      {open && (
        <div className="agent-chat-panel panel">
          <header className="panel-head">
            <h2>
              Agent
              {titleSymbol ? ` · ${titleSymbol}` : ''}
              {titleTf ? ` · ${titleTf}` : ''}
            </h2>
            <div className="agent-chat-head-actions">
              <Link
                to="/app/agent"
                className="ghost agent-chat-atelier-link"
                onClick={() => setOpen(false)}
              >
                Atelier
              </Link>
              <button
                type="button"
                className="agent-chat-close"
                aria-label="Fermer"
                onClick={() => setOpen(false)}
              >
                <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
                  <path
                    d="M2 2l8 8M10 2L2 10"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
            </div>
          </header>
          <AgentPanel
            snapshot={snapshot}
            decisionPayload={decisionPayload}
            decisionRequestId={decisionRequestId}
          />
        </div>
      )}
      <button
        type="button"
        className="agent-chat-bubble"
        aria-expanded={open}
        aria-label={open ? "Fermer l'agent" : "Ouvrir l'agent"}
        onClick={() => setOpen(!open)}
      >
        <IconChat />
      </button>
    </div>
  )
}
