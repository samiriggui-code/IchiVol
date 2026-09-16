import { Link } from 'react-router-dom'
import { AgentEnginePanel } from '../components/AgentEnginePanel'
import { AgentPanel } from '../components/AgentPanel'
import { useAgentSession } from '../lib/agentSession'
import { useMarketSnapshot } from '../lib/marketSnapshot'

/**
 * Atelier Copilot plein écran — chat + panneau moteur ventilé.
 * La bulle flottante reste pour les explications rapides (Décisions / Journal).
 */
export function AgentPage() {
  const { snapshot } = useMarketSnapshot()
  const { decisionPayload, decisionRequestId, assumedSymbol, assumedTimeframe } =
    useAgentSession()

  const symbol =
    assumedSymbol ?? decisionPayload?.symbol ?? snapshot?.symbol ?? null
  const timeframe =
    assumedTimeframe ?? decisionPayload?.timeframe ?? snapshot?.interval ?? '1h'

  return (
    <div className="page agent-atelier">
      <header className="page-head">
        <div>
          <h1>Copilot</h1>
          <p className="muted">
            Chat à gauche · outils moteur à droite. Les chiffres viennent du
            Python, pas du LLM.
          </p>
        </div>
        <Link to="/app/decisions" className="ghost">
          ← Décisions
        </Link>
      </header>

      <div className="agent-atelier-grid">
        <section className="agent-atelier-chat panel">
          <header className="panel-head">
            <h2>
              Conversation
              {symbol ? ` · ${symbol}` : ''}
              {timeframe ? ` · ${timeframe}` : ''}
            </h2>
          </header>
          <AgentPanel
            snapshot={snapshot}
            decisionPayload={decisionPayload}
            decisionRequestId={decisionRequestId}
          />
        </section>

        <AgentEnginePanel symbol={symbol} timeframe={timeframe} />
      </div>
    </div>
  )
}
