import { Link } from 'react-router-dom'
import { KeenIcon } from '../components/KeenIcon'
import { llmStatusLabel, useLlmStatus } from '../lib/llmStatus'
import './AgentsPage.css'

const roles = [
  { name: 'Observateur de marché', icon: 'compass', purpose: 'Observer les régimes, le volume et la structure du marché.', scope: 'Prix, indicateurs et contexte.', limit: 'Aucune modification de position.', to: '/app/context', label: 'Voir le contexte' },
  { name: 'Opportunités', icon: 'questionnaire-tablet', purpose: 'Rassembler les preuves autour des setups repérés par le moteur.', scope: 'Signaux et étapes du pipeline.', limit: 'Aucune décision de trading autonome.', to: '/app/opportunites', label: 'Voir les opportunités' },
  { name: 'Risque', icon: 'shield-tick', purpose: 'Présenter les limites et les refus du Risk Kernel.', scope: 'Exposition et contrôles du portefeuille.', limit: 'Aucun changement des limites de risque.', to: '/app/portefeuille?tab=risque', label: 'Voir le risque' },
  { name: 'Exécution', icon: 'arrow-right', purpose: 'Suivre la transmission et le résultat des décisions validées.', scope: 'Traçabilité des opérations.', limit: 'Aucun ordre envoyé depuis cette page.', to: '/app/operations', label: 'Voir les opérations' },
  { name: 'Gestion de position', icon: 'chart-simple', purpose: 'Suivre les positions paper et leurs conditions de sortie.', scope: 'Positions et protection.', limit: 'Aucun changement de stop ou clôture depuis cette page.', to: '/app/portefeuille?tab=positions', label: 'Voir les positions' },
  { name: 'Session', icon: 'timer', purpose: 'Regrouper les contraintes horaires de la chaîne de décision.', scope: 'Rôle prévu dans la maquette.', limit: 'Agent de session non connecté.', to: '/app/journal', label: 'Voir le journal' },
] as const

export function AgentsPage() {
  const llm = useLlmStatus()
  return (
    <div className="agents-page">
      <header className="iv-page-header page-head agents-page-head">
        <div>
          <p className="iv-page-eyebrow">Automatisation · Agents</p>
          <h1>Agents</h1>
          <p className="iv-page-question">Une chaîne de décision sous contrôle.</p>
        </div>
        <Link className="ghost" to="/app/agent">Ouvrir Copilot →</Link>
      </header>

      <section className="panel agents-connection" aria-label="Connexion du Copilot">
        <div>
          <h2>Copilot · connexion LLM</h2>
          <p role="status">{llmStatusLabel(llm.state)}{llm.provider ? ` · ${llm.provider}` : ''}{llm.model ? ` · ${llm.model}` : ''}</p>
          <p className="muted">L’état de connexion ne signifie pas qu’un agent est en cours d’exécution.</p>
        </div>
        <Link to="/app/settings">Paramètres du LLM →</Link>
      </section>

      <p className="agents-notice">Les six rôles ci-dessous décrivent l’organisation prévue. Leurs permissions sont indicatives ; leur exécution autonome n’est pas connectée à cette page.</p>

      <div className="agents-grid">
        {roles.map((role) => (
          <section className="panel agents-card" key={role.name}>
            <div className="agents-card-top"><KeenIcon icon={role.icon} /><span className="iv-badge">NON CONNECTÉ</span></div>
            <h2>{role.name}</h2>
            <p>{role.purpose}</p>
            <details>
              <summary>Périmètre prévu</summary>
              <dl><dt>Lecture</dt><dd>{role.scope}</dd><dt>Limite</dt><dd>{role.limit}</dd></dl>
            </details>
            <Link to={role.to}>{role.label} →</Link>
          </section>
        ))}
      </div>

      <section className="panel agents-authority">
        <h2>Chaîne d’autorité</h2>
        <ol>{['Observation', 'Opportunité', 'Risk Kernel', 'Validation', 'Exécution'].map((step) => <li key={step}>{step}</li>)}</ol>
        <p className="muted">Le moteur calcule et contrôle le risque. Copilot explique les résultats. Cette page ne déclenche aucune opération.</p>
      </section>
    </div>
  )
}
