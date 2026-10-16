/**
 * Fiche agent — même chrome que Opportunités / FicheDecision (`fiche-dialog`).
 * ids : eve | eve:analyst|challenger|guardian|shadow | observer|opportunities|…
 */

import { useEffect, useRef, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useFicheNav } from '../../lib/useFicheNav'
import { EveIntelligencePanel } from '../../pages/EveIntelligencePanel'
import { EveShadowPanel } from '../../pages/EveShadowPanel'
import './ficheDialog.css'

type BadgeTone = 'green' | 'amber' | 'red' | 'gray' | ''

type EveModeId = 'analyst' | 'challenger' | 'guardian' | 'shadow'

type RoleId =
  | 'observer'
  | 'opportunities'
  | 'risk'
  | 'execution'
  | 'position'
  | 'session'

type ModeDef = {
  id: EveModeId
  name: string
  blurb: string
  mission: string
  primitives: string
  permission: string
}

type RoleDef = {
  id: RoleId
  name: string
  blurb: string
  mode: string
  permission: string
  kind: 'llm' | 'code'
  to: string
  linkLabel: string
}

const EVE_MODES: Record<EveModeId, ModeDef> = {
  analyst: {
    id: 'analyst',
    name: 'Ève Analyst',
    blurb: 'Interprète calculs, structure et scénarios.',
    mission: 'Lire le FactSheet et proposer un scénario cohérent.',
    primitives: 'SCORE',
    permission: 'market_read',
  },
  challenger: {
    id: 'challenger',
    name: 'Ève Challenger',
    blurb: 'Cherche contradictions et alternatives.',
    mission: 'Contester le scénario Analyst avant tout verdict.',
    primitives: 'NOUL + CHOICE',
    permission: 'signals_read',
  },
  guardian: {
    id: 'guardian',
    name: 'Ève Guardian',
    blurb: 'Risques et anomalies — advisory seulement.',
    mission: 'Signaler veto / prudence. Risk Kernel reste autorité.',
    primitives: 'NOUL + SCORE',
    permission: 'risk_read',
  },
  shadow: {
    id: 'shadow',
    name: 'Ève Shadow',
    blurb: 'Contre-évaluation indépendante (≠ ShadowBroker).',
    mission: 'Audit parallèle NOUL / CHOICE / SCORE — observation only.',
    primitives: 'NOUL + CHOICE + SCORE',
    permission: 'market_read',
  },
}

const ROLES: Record<RoleId, RoleDef> = {
  observer: {
    id: 'observer',
    name: 'Observateur de marché',
    blurb: 'Observe les régimes et la structure du marché.',
    mode: 'Règles',
    permission: 'market_read',
    kind: 'code',
    to: '/app/context',
    linkLabel: 'Voir le contexte →',
  },
  opportunities: {
    id: 'opportunities',
    name: 'Opportunités',
    blurb: 'Repère les setups et rassemble les preuves.',
    mode: 'LLM / règles',
    permission: 'signals_read',
    kind: 'llm',
    to: '/app/opportunites',
    linkLabel: 'Voir les opportunités →',
  },
  risk: {
    id: 'risk',
    name: 'Risque',
    blurb: 'Applique les limites du Risk Kernel.',
    mode: 'Règles',
    permission: 'risk_read',
    kind: 'code',
    to: '/app/portefeuille?tab=risque',
    linkLabel: 'Voir le risque →',
  },
  execution: {
    id: 'execution',
    name: 'Exécution',
    blurb: 'Transmet uniquement les décisions validées.',
    mode: 'Règles',
    permission: 'orders_execute',
    kind: 'code',
    to: '/app/operations',
    linkLabel: 'Voir les opérations →',
  },
  position: {
    id: 'position',
    name: 'Gestion de position',
    blurb: 'Surveille le stop et les conditions de sortie.',
    mode: 'Règles',
    permission: 'paper_orders',
    kind: 'code',
    to: '/app/portefeuille?tab=positions',
    linkLabel: 'Voir les positions →',
  },
  session: {
    id: 'session',
    name: 'Session',
    blurb: 'Suit les horaires et contraintes de session.',
    mode: 'Règles',
    permission: 'market_read',
    kind: 'code',
    to: '/app/journal',
    linkLabel: 'Voir le journal →',
  },
}

function badge(text: string, tone: BadgeTone = ''): ReactNode {
  let inferred = tone
  if (!inferred) {
    inferred = /PASSE|ACCEPTÉ|OUVERTE|VALIDÉ|ACTIF|CENTRALE/i.test(text)
      ? 'green'
      : /REFUS|BLOQU|ERREUR/i.test(text)
        ? 'red'
        : /PRUDENCE|ADVISORY|MODE|VEILLE/i.test(text)
          ? 'amber'
          : ''
  }
  return <span className={`tag ${inferred}`.trim()}>{text}</span>
}

function parseAgentId(id: string): {
  kind: 'hub' | 'mode' | 'role' | 'unknown'
  mode?: ModeDef
  role?: RoleDef
  title: string
} {
  const raw = id.trim().toLowerCase()
  if (raw === 'eve' || raw === 'eve-hub' || raw === 'hub') {
    return { kind: 'hub', title: 'Ève Intelligence' }
  }
  const modeKey = raw.replace(/^eve[:\-]/, '') as EveModeId
  if (modeKey in EVE_MODES) {
    return { kind: 'mode', mode: EVE_MODES[modeKey], title: EVE_MODES[modeKey].name }
  }
  if (raw in ROLES) {
    const role = ROLES[raw as RoleId]
    return { kind: 'role', role, title: role.name }
  }
  return { kind: 'unknown', title: `Agent · ${id}` }
}

export function FicheAgent({
  agentId,
  onClose,
}: {
  agentId: string
  onClose: () => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  const { openFiche } = useFicheNav()
  const parsed = parseAgentId(agentId)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (!el.open) el.showModal()
    const onDialogClose = () => onClose()
    el.addEventListener('close', onDialogClose)
    return () => el.removeEventListener('close', onDialogClose)
  }, [onClose])

  return (
    <dialog
      ref={ref}
      className="fiche-dialog"
      aria-label={`Fiche ${parsed.title}`}
      onCancel={(e) => {
        e.preventDefault()
        ref.current?.close()
      }}
    >
      <div className="dialog-body">
        <div className="dialog-head">
          <h2>{parsed.title}</h2>
          <button type="button" onClick={() => ref.current?.close()} aria-label="Fermer">
            ×
          </button>
        </div>

        {parsed.kind === 'hub' ? (
          <>
            {badge('IA CENTRALE', 'green')}
            <p>
              Une seule intelligence Ève · modes Analyst / Challenger / Guardian / Shadow ·
              trade paper sur tous les livres virtuels (jamais live).
            </p>
            <div className="statline">
              <span>Exécution</span>
              <b>paper si autonomie on</b>
            </div>
            <div className="statline">
              <span>Portefeuille</span>
              <b>tous les virtuels actifs</b>
            </div>
            <div className="statline">
              <span>Risk Kernel</span>
              <b>autorité — autonomie = Eve peut trader paper</b>
            </div>
            <div className="fiche-tab-panel">
              <EveIntelligencePanel />
            </div>
          </>
        ) : null}

        {parsed.kind === 'mode' && parsed.mode ? (
          <>
            {badge(parsed.mode.id === 'guardian' ? 'ADVISORY' : 'MODE')}
            <p>{parsed.mode.blurb}</p>
            <div className="statline">
              <span>Mission</span>
              <b>{parsed.mode.mission}</b>
            </div>
            <div className="statline">
              <span>Primitives JEV</span>
              <b>
                <code>{parsed.mode.primitives}</code>
              </b>
            </div>
            <div className="statline">
              <span>Permission</span>
              <b>{parsed.mode.permission}</b>
            </div>
            <div className="statline">
              <span>Exécution</span>
              <b>paper si autonomie on</b>
            </div>
            <div className="statline">
              <span>Autorité risque</span>
              <b>
                {parsed.mode.id === 'guardian'
                  ? 'Advisory — Risk Kernel décide'
                  : 'Risk Kernel (impératif)'}
              </b>
            </div>
            <div className="statline">
              <span>Paper / live</span>
              <b>paper only · pas de broker live</b>
            </div>
            {parsed.mode.id === 'shadow' ? (
              <div className="fiche-tab-panel">
                <EveShadowPanel />
              </div>
            ) : (
              <div className="notice blue" style={{ marginTop: 16 }}>
                Mode de l’intelligence unique Ève — pas un LLM séparé. Dossiers dans la fiche hub.
              </div>
            )}
            <div className="dialog-actions">
              <button
                type="button"
                className="suggestion"
                onClick={() => openFiche({ kind: 'agent', id: 'eve' }, { replace: true })}
              >
                Ouvrir hub Ève →
              </button>
              <button type="button" className="primary" onClick={() => ref.current?.close()}>
                Fermer
              </button>
            </div>
          </>
        ) : null}

        {parsed.kind === 'role' && parsed.role ? (
          <>
            {badge(parsed.role.kind === 'llm' ? 'LLM' : 'CODE', 'gray')}
            <p>
              {parsed.role.blurb}{' '}
              {parsed.role.kind === 'llm'
                ? '· Eve (LLM) · paper only · confirm humaine.'
                : '· rôle code déterministe · paper only.'}
            </p>
            <div className="statline">
              <span>Mode</span>
              <b>{parsed.role.mode}</b>
            </div>
            <div className="statline">
              <span>Permission</span>
              <b>{parsed.role.permission}</b>
            </div>
            <div className="statline">
              <span>Lecture marché</span>
              <b>{badge('AUTORISÉE', 'gray')}</b>
            </div>
            <div className="statline">
              <span>Modification risque</span>
              <b>{badge(parsed.role.id === 'risk' ? 'CODE ONLY' : 'BLOQUÉE', 'gray')}</b>
            </div>
            <div className="statline">
              <span>Ordres réels</span>
              <b>{badge('BLOQUÉS')}</b>
            </div>
            <div className="statline">
              <span>Paper / confirm</span>
              <b>{badge('OUI', 'green')}</b>
            </div>
            <div className="dialog-actions">
              <Link className="link" to={parsed.role.to} onClick={() => ref.current?.close()}>
                {parsed.role.linkLabel}
              </Link>
              {parsed.role.kind === 'llm' ? (
                <Link className="link" to="/app/agent" onClick={() => ref.current?.close()}>
                  Copilot Eve →
                </Link>
              ) : null}
              <button type="button" className="primary" onClick={() => ref.current?.close()}>
                Fermer
              </button>
            </div>
          </>
        ) : null}

        {parsed.kind === 'unknown' ? (
          <>
            <div className="notice blue">
              Agent inconnu : <code>{agentId}</code>. IDs attendus : eve, eve:analyst, observer,
              opportunities, risk, execution, position, session.
            </div>
            <div className="dialog-actions">
              <button type="button" className="primary" onClick={() => ref.current?.close()}>
                Fermer
              </button>
            </div>
          </>
        ) : null}
      </div>
    </dialog>
  )
}
