import { Link } from 'react-router-dom'
import { AgentPanel } from '../components/AgentPanel'
import { StatLine, Tag, WorkspacePageHead } from '../components/maquette'
import { useAgentSession } from '../lib/agentSession'
import { useMarketSnapshot } from '../lib/marketSnapshot'

const PROMPTS = [
  'Pourquoi ce symbole attend-il ?',
  'Quel est le risque du portefeuille ?',
  'Explique le setup sélectionné',
] as const

/**
 * Copilot — maquette `copilot()` : card.chat + explorer.
 * AgentPanel conserve le streaming / outils LLM.
 */
export function AgentPage() {
  const { snapshot } = useMarketSnapshot()
  const { decisionPayload, assumedSymbol, assumedTimeframe, launch, setInput } = useAgentSession()

  const symbol =
    launch?.decision?.symbol ??
    launch?.live?.symbol ??
    assumedSymbol ??
    decisionPayload?.symbol ??
    snapshot?.symbol ??
    null
  const timeframe =
    launch?.decision?.timeframe ??
    launch?.live?.interval ??
    assumedTimeframe ??
    decisionPayload?.timeframe ??
    snapshot?.interval ??
    '1h'

  const hasSession = Boolean(symbol)
  const llmConnected = Boolean(snapshot) // session live implies engine path; LLM key is in settings

  return (
    <div>
      <WorkspacePageHead
        path="/app/agent"
        actions={<Tag tone="gray">{llmConnected ? 'SESSION LIVE' : 'APERÇU DU COPILOT'}</Tag>}
      />

      <div className="grid">
        <section className="card chat">
          <div className="card-head">
            <h2>Une seconde lecture</h2>
            <Tag tone="gray">{hasSession ? `${symbol} · ${timeframe}` : 'APERÇU DU COPILOT'}</Tag>
          </div>
          <AgentPanel snapshot={snapshot} />
        </section>

        <section className="card">
          <div className="card-head">
            <h2>Explorer une décision</h2>
          </div>
          <div className="card-body">
            {PROMPTS.map((q) => (
              <button
                key={q}
                type="button"
                className="suggestion"
                onClick={() => setInput(q)}
              >
                {q}
              </button>
            ))}
            <div style={{ marginTop: 30 }}>
              <StatLine label="Lire le contexte" value={<Tag tone="gray">DISPONIBLE</Tag>} />
              <StatLine label="Expliquer un refus" value={<Tag tone="gray">DISPONIBLE</Tag>} />
              <StatLine label="Passer un ordre" value={<Tag tone="red">BLOQUÉ</Tag>} />
            </div>
            <p style={{ fontSize: 11, color: 'var(--muted)' }}>
              Claude interroge le moteur en lecture seule. La validation reste au Risk Kernel.{' '}
              <Link to="/app/opportunites" className="link">
                Opportunités
              </Link>
              {' · '}
              <Link to="/app/journal" className="link">
                Journal
              </Link>
              {' · '}
              <Link to="/app/settings" className="link">
                Paramètres LLM
              </Link>
            </p>
          </div>
        </section>
      </div>
    </div>
  )
}
