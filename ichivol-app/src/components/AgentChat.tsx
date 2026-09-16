import { useNavigate } from 'react-router-dom'
import { IconChat } from './NavIcons'
import { useAgentSession } from '../lib/agentSession'

/** Bulle = raccourci vers l’atelier Copilot (conversation persistée dans la session). */
export function AgentChat() {
  const navigate = useNavigate()
  const { loading, history } = useAgentSession()
  const pending = loading || history.length > 0

  return (
    <div className="agent-chat">
      <button
        type="button"
        className={`agent-chat-bubble${loading ? ' is-busy' : pending ? ' has-thread' : ''}`}
        aria-label={loading ? 'Copilot en cours — rouvrir' : 'Ouvrir le Copilot'}
        title={loading ? 'L’agent réfléchit…' : 'Copilot'}
        onClick={() => navigate('/app/agent')}
      >
        <IconChat />
        {loading && <span className="agent-chat-pulse" aria-hidden />}
      </button>
    </div>
  )
}
