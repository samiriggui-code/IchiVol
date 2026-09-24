import { useState } from 'react'
import { Tag, WorkspacePageHead, StatLine, Card } from '../components/maquette'

const AGENTS = [
  {
    name: 'Observateur de marché',
    icon: '◎',
    blurb: 'Observe les régimes et la structure du marché.',
    mode: 'Règles',
    permission: 'market_read',
  },
  {
    name: 'Opportunités',
    icon: '◇',
    blurb: 'Repère les setups et rassemble les preuves.',
    mode: 'LLM / règles',
    permission: 'signals_read',
  },
  {
    name: 'Risque',
    icon: '◈',
    blurb: 'Applique les limites du Risk Kernel.',
    mode: 'Règles',
    permission: 'risk_read',
  },
  {
    name: 'Exécution',
    icon: '↗',
    blurb: 'Transmet uniquement les décisions validées.',
    mode: 'Règles',
    permission: 'orders_execute',
  },
  {
    name: 'Gestion de position',
    icon: '◫',
    blurb: 'Surveille le stop et les conditions de sortie.',
    mode: 'Règles',
    permission: 'paper_orders',
  },
  {
    name: 'Session',
    icon: '◷',
    blurb: 'Suit les horaires et contraintes de session.',
    mode: 'Règles',
    permission: 'market_read',
  },
] as const

const CHAIN = ['Observation', 'Opportunité', 'Risk Kernel', 'Position', 'Exécution'] as const

/**
 * Agents — maquette `agents()` : grille agent-card + chaîne d’autorité.
 * Permissions / états illustratifs ; le moteur Python reste source de vérité.
 */
export function AgentsPage() {
  const [selected, setSelected] = useState<number | null>(null)
  const detail = selected != null ? AGENTS[selected] : null

  return (
    <div>
      <WorkspacePageHead
        path="/app/agents"
        actions={<Tag tone="gray">DONNÉES D’EXEMPLE</Tag>}
      />

      <div className="notice blue">
        <span aria-hidden>⬡</span>
        <span>
          Supervision des agents · permissions et états illustratifs · aucun agent en exécution
          autonome sans le moteur.
        </span>
      </div>

      <div className="grid three">
        {AGENTS.map((a, i) => (
          <section key={a.name} className="card agent-card">
            <Tag tone="gray">APERÇU</Tag>
            <div className="agent-icon" aria-hidden>
              {a.icon}
            </div>
            <h2>{a.name}</h2>
            <p>{a.blurb}</p>
            <StatLine label="Mode" value={a.mode} />
            <StatLine label="Permission" value={<span className="mono">{a.permission}</span>} />
            <button type="button" onClick={() => setSelected(i)}>
              Voir les permissions →
            </button>
          </section>
        ))}
      </div>

      <Card title="Chaîne d’autorité" bodyClassName="card-body">
        <div className="toolbar" style={{ marginBottom: 12 }}>
          {CHAIN.map((s, i) => (
            <span key={s} style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              {i > 0 ? <span aria-hidden>→</span> : null}
              <Tag tone="gray">{s}</Tag>
            </span>
          ))}
        </div>
        <p style={{ fontSize: 12, color: 'var(--muted)', margin: 0 }}>
          Chaque étape dispose d’un périmètre explicite. Le contrôle du risque reste nécessaire avant
          l’exécution.
        </p>
      </Card>

      {detail && (
        <dialog open className="card" style={{ marginTop: 20, padding: 0, maxWidth: 550 }}>
          <div className="dialog-body">
            <div className="dialog-head">
              <h2>{detail.name}</h2>
              <button type="button" aria-label="Fermer" onClick={() => setSelected(null)}>
                ×
              </button>
            </div>
            <p>Permissions illustratives · agent non connecté au runtime.</p>
            <StatLine label="Lecture du marché" value={<Tag tone="gray">AUTORISÉE</Tag>} />
            <StatLine label="Modification du risque" value={<Tag tone="red">BLOQUÉE</Tag>} />
            <StatLine label="Ordres réels" value={<Tag tone="red">BLOQUÉS</Tag>} />
            <p>
              L’activation et les permissions effectives doivent être vérifiées par le moteur
              Python.
            </p>
            <div className="dialog-actions">
              <button type="button" onClick={() => setSelected(null)}>
                Fermer
              </button>
            </div>
          </div>
        </dialog>
      )}
    </div>
  )
}
