import { Link } from 'react-router-dom'
import { AgentPanel } from '../components/AgentPanel'
import { useAgentSession } from '../lib/agentSession'
import { useMarketSnapshot } from '../lib/marketSnapshot'

/**
 * Agent Claude : il interroge le moteur en lecture seule (outils) puis explique.
 */
export function AgentPage() {
  const { snapshot } = useMarketSnapshot()
  const { decisionPayload, assumedSymbol, assumedTimeframe, launch } = useAgentSession()

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

  return (
    <div className="page agent-atelier">
      <header className="agent-atelier-hero">
        <div className="agent-atelier-hero-copy">
          <p className="agent-atelier-kicker">Atelier d’analyse</p>
          <h1>Copilot</h1>
          <p className="agent-atelier-lede">
            Le <strong>moteur Python</strong> calcule. Claude <strong>interroge le moteur</strong> avec ses outils, puis explique.
            Depuis Décisions ou Journal, un clic « Expliquer » t’amène ici avec la
            question déjà prête.
          </p>
          <div className="agent-atelier-roles" aria-label="Rôles">
            <span className="agent-role-pill is-engine">Moteur = chiffres</span>
            <span className="agent-role-pill is-llm">Claude = outils + explication</span>
            <span className="agent-role-pill is-you">Toi = confirmation</span>
          </div>
        </div>

        <div className="agent-atelier-hero-aside">
          <div className={`agent-session-chip ${hasSession ? 'is-live' : ''}`}>
            <span className="agent-session-label">Session</span>
            {hasSession ? (
              <span className="agent-session-value">
                {symbol}
                <span className="muted"> · {timeframe}</span>
              </span>
            ) : (
              <span className="agent-session-value muted">Aucun symbole — lance depuis Décisions</span>
            )}
          </div>
          <nav className="agent-atelier-jump" aria-label="Raccourcis">
            <Link to="/app/decisions">Décisions</Link>
            <Link to="/app/journal">Journal</Link>
            <Link to="/app/context">Contexte</Link>
            <Link to="/app/market">Marché</Link>
          </nav>
        </div>
      </header>

      <div className="agent-atelier-grid">
        <section className="agent-atelier-chat panel">
          <header className="agent-atelier-panel-head">
            <div>
              <h2>Conversation</h2>
              <p className="muted">
                Modes : expliquer une décision, un signal, rechercher, ou une idée —
                toujours ancré sur les données injectées.
              </p>
            </div>
          </header>
          <AgentPanel snapshot={snapshot} />
        </section>

      </div>
    </div>
  )
}
