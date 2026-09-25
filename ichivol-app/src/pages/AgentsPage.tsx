/**
 * Agents — port littéral de design-reference/ichivol-workspace `agents()` + page-head.
 * Classes HTML = maquette. États = lecture seule (aucun agent en exécution).
 */

import { type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import './AgentsPage.css'

type BadgeTone = 'green' | 'amber' | 'red' | 'gray' | ''

const AGENTS: {
  name: string
  icon: string
  blurb: string
  mode: string
  permission: string
  to: string
}[] = [
  {
    name: 'Observateur de marché',
    icon: '◎',
    blurb: 'Observe les régimes et la structure du marché.',
    mode: 'Règles',
    permission: 'market_read',
    to: '/app/context',
  },
  {
    name: 'Opportunités',
    icon: '◇',
    blurb: 'Repère les setups et rassemble les preuves.',
    mode: 'LLM / règles',
    permission: 'signals_read',
    to: '/app/opportunites',
  },
  {
    name: 'Risque',
    icon: '◈',
    blurb: 'Applique les limites du Risk Kernel.',
    mode: 'Règles',
    permission: 'risk_read',
    to: '/app/portefeuille',
  },
  {
    name: 'Exécution',
    icon: '↗',
    blurb: 'Transmet uniquement les décisions validées.',
    mode: 'Règles',
    permission: 'orders_execute',
    to: '/app/operations',
  },
  {
    name: 'Gestion de position',
    icon: '◫',
    blurb: 'Surveille le stop et les conditions de sortie.',
    mode: 'Règles',
    permission: 'paper_orders',
    to: '/app/portefeuille',
  },
  {
    name: 'Session',
    icon: '◷',
    blurb: 'Suit les horaires et contraintes de session.',
    mode: 'Règles',
    permission: 'market_read',
    to: '/app/journal',
  },
]

const CHAIN = ['Observation', 'Opportunité', 'Risk Kernel', 'Position', 'Exécution']

function badge(text: string, tone: BadgeTone = ''): ReactNode {
  let inferred = tone
  if (!inferred) {
    inferred = /PASSE|ACCEPTÉ|OUVERTE|VALIDÉ/i.test(text)
      ? 'green'
      : /REFUS|BLOQU|ERREUR/i.test(text)
        ? 'red'
        : /PRUDENCE|ARMED|WATCH/i.test(text)
          ? 'amber'
          : ''
  }
  return <span className={`tag ${inferred}`.trim()}>{text}</span>
}

export function AgentsPage() {
  const navigate = useNavigate()

  return (
    <div className="agents-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">09 / ICHIVOL WORKSPACE</div>
          <h1>Agents</h1>
          <p className="subtitle">Une chaîne de décision sous contrôle.</p>
        </div>
        <div className="actions">{badge('DONNÉES LIVE', 'gray')}</div>
      </div>

      <div className="notice blue">
        ⬡{' '}
        <span>
          Supervision des agents · permissions et états illustratifs · aucun agent en
          exécution.
        </span>
      </div>

      <div className="grid three">
        {AGENTS.map((a) => (
          <section className="card agent-card" key={a.name}>
            {badge('APERÇU', 'gray')}
            <div className="agent-icon">{a.icon}</div>
            <h2>{a.name}</h2>
            <p>{a.blurb}</p>
            <div className="statline">
              <span>Mode</span>
              <b>{a.mode}</b>
            </div>
            <div className="statline">
              <span>Permission</span>
              <b>{a.permission}</b>
            </div>
            <button type="button" onClick={() => navigate(a.to)}>
              Voir les permissions →
            </button>
          </section>
        ))}
      </div>

      <section className="card">
        <div className="card-head">
          <h2>Chaîne d’autorité</h2>
        </div>
        <div className="card-body">
          <div className="toolbar">
            {CHAIN.map((s, i) => (
              <span key={s} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                {i ? <span aria-hidden="true">→</span> : null}
                {badge(s, 'gray')}
              </span>
            ))}
          </div>
          <p style={{ fontSize: 12, color: 'var(--muted)' }}>
            Chaque étape dispose d’un périmètre explicite. Le contrôle du risque reste
            nécessaire avant l’exécution.
          </p>
        </div>
      </section>
    </div>
  )
}
