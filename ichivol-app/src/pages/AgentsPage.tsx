/**
 * Agents — cartes Ève (hub + 4 modes) + chaîne opérationnelle (6 rôles).
 * Fiches = FicheHost / `?fiche=agent:…` (même chrome que Opportunités), pas ModalSheetHost.
 */

import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import {
  createAgentMission,
  fetchAgents,
  fmtDue,
  statusBadgeTone,
  type AgentRoleCard,
  type AgentsListResponse,
  type AuthorityChain,
} from '../lib/agentsRuntime'
import { labelEngineCode } from '../lib/engineTerminology'
import { useFicheNav } from '../lib/useFicheNav'
import './AgentsPage.css'

type BadgeTone = 'green' | 'amber' | 'red' | 'gray' | ''

type EveModeId = 'analyst' | 'challenger' | 'guardian' | 'shadow'

type EveModeDef = {
  id: EveModeId
  name: string
  tag: string
  icon: string
  blurb: string
  primitives: string
  advisoryOnly: boolean
}

const EVE_MODES: EveModeDef[] = [
  {
    id: 'analyst',
    name: 'Ève Analyste',
    tag: 'MODE',
    icon: '◇',
    blurb: 'Lit les calculs du moteur et la structure du marché, puis construit les scénarios.',
    primitives: 'NOUL + CHOICE + SCORE',
    advisoryOnly: true,
  },
  {
    id: 'challenger',
    name: 'Ève Contradictrice',
    tag: 'MODE',
    icon: '↺',
    blurb: 'Cherche ce qui contredit le scénario retenu et les autres possibilités.',
    primitives: 'NOUL + CHOICE + SCORE',
    advisoryOnly: true,
  },
  {
    id: 'guardian',
    name: 'Ève Gardienne',
    tag: 'MODE',
    icon: '◈',
    blurb: 'Signale les risques et les anomalies. Le Risk Kernel garde le dernier mot.',
    primitives: 'NOUL + CHOICE + SCORE',
    advisoryOnly: true,
  },
  {
    id: 'shadow',
    name: 'Ève Contre-avis',
    tag: 'MODE',
    icon: '◉',
    blurb: 'Refait l’évaluation de son côté avec JEV (API hébergée, puis jevos si les crédits sont épuisés).',
    primitives: 'NOUL + CHOICE + SCORE',
    advisoryOnly: true,
  },
]

const FALLBACK_CARDS: AgentRoleCard[] = [
  {
    id: 'observer',
    name: 'Observateur de marché',
    kind: 'code',
    runtimeAgentId: null,
    status: 'EN VEILLE',
    statusReason: 'API agents injoignable',
    mode: 'Règles',
    permission: 'market_read',
    blurb: 'Observe les régimes et la structure du marché.',
    icon: '◎',
    lastAction: null,
    lastActionAt: null,
    nextTaskDue: null,
    nextTaskKind: null,
    nextTaskSymbol: null,
    counts24h: 0,
    openTasks: 0,
    paperOnly: true,
    humanConfirmDefault: true,
    autoOpen: false,
    chat: null,
  },
  {
    id: 'opportunities',
    name: 'Opportunités',
    kind: 'llm',
    runtimeAgentId: 'eve',
    status: 'EN VEILLE',
    statusReason: 'API agents injoignable',
    mode: 'LLM / règles',
    permission: 'signals_read',
    blurb: 'Repère les setups et rassemble les preuves.',
    icon: '◇',
    lastAction: null,
    lastActionAt: null,
    nextTaskDue: null,
    nextTaskKind: null,
    nextTaskSymbol: null,
    counts24h: 0,
    openTasks: 0,
    paperOnly: true,
    humanConfirmDefault: true,
    autoOpen: false,
    chat: 'copilot_threads',
  },
  {
    id: 'risk',
    name: 'Risque',
    kind: 'code',
    runtimeAgentId: null,
    status: 'EN VEILLE',
    statusReason: 'API agents injoignable',
    mode: 'Règles',
    permission: 'risk_read',
    blurb: 'Applique les limites du Risk Kernel.',
    icon: '◈',
    lastAction: null,
    lastActionAt: null,
    nextTaskDue: null,
    nextTaskKind: null,
    nextTaskSymbol: null,
    counts24h: 0,
    openTasks: 0,
    paperOnly: true,
    humanConfirmDefault: true,
    autoOpen: false,
    chat: null,
  },
  {
    id: 'execution',
    name: 'Exécution',
    kind: 'code',
    runtimeAgentId: null,
    status: 'EN VEILLE',
    statusReason: 'API agents injoignable',
    mode: 'Règles',
    permission: 'orders_execute',
    blurb: 'Transmet uniquement les décisions validées.',
    icon: '↗',
    lastAction: null,
    lastActionAt: null,
    nextTaskDue: null,
    nextTaskKind: null,
    nextTaskSymbol: null,
    counts24h: 0,
    openTasks: 0,
    paperOnly: true,
    humanConfirmDefault: true,
    autoOpen: false,
    chat: null,
  },
  {
    id: 'position',
    name: 'Gestion de position',
    kind: 'code',
    runtimeAgentId: null,
    status: 'EN VEILLE',
    statusReason: 'API agents injoignable',
    mode: 'Règles',
    permission: 'paper_orders',
    blurb: 'Surveille le stop et les conditions de sortie.',
    icon: '◫',
    lastAction: null,
    lastActionAt: null,
    nextTaskDue: null,
    nextTaskKind: null,
    nextTaskSymbol: null,
    counts24h: 0,
    openTasks: 0,
    paperOnly: true,
    humanConfirmDefault: true,
    autoOpen: false,
    chat: null,
  },
  {
    id: 'session',
    name: 'Session',
    kind: 'code',
    runtimeAgentId: null,
    status: 'EN VEILLE',
    statusReason: 'API agents injoignable',
    mode: 'Règles',
    permission: 'market_read',
    blurb: 'Suit les horaires et contraintes de session.',
    icon: '◷',
    lastAction: null,
    lastActionAt: null,
    nextTaskDue: null,
    nextTaskKind: null,
    nextTaskSymbol: null,
    counts24h: 0,
    openTasks: 0,
    paperOnly: true,
    humanConfirmDefault: true,
    autoOpen: false,
    chat: null,
  },
]

const ROLE_ORDER = [
  'observer',
  'opportunities',
  'risk',
  'execution',
  'position',
  'session',
] as const

const CHAIN_DEFAULT = ['Observation', 'Opportunité', 'Risk Kernel', 'Position', 'Exécution']

function badge(text: string, tone: BadgeTone = ''): ReactNode {
  let inferred = tone
  if (!inferred) {
    inferred = /PASSE|ACCEPTÉ|OUVERTE|VALIDÉ|ACTIF/i.test(text)
      ? 'green'
      : /REFUS|BLOQU|ERREUR/i.test(text)
        ? 'red'
        : /PRUDENCE|ARMED|WATCH|VEILLE|ADVISORY|MODE/i.test(text)
          ? 'amber'
          : ''
  }
  return <span className={`tag ${inferred}`.trim()}>{text}</span>
}

function dash(value: string | null | undefined, reason?: string, max = 72): string {
  if (value && value.trim()) {
    const t = labelEngineCode(value.trim())
    return t.length > max ? `${t.slice(0, max - 1)}…` : t
  }
  return reason ? `— (${labelEngineCode(reason)})` : '—'
}

function runtimeNotice(data: AgentsListResponse | null, loadError: string | null): string {
  if (loadError) return 'Supervision des agents · runtime inaccessible · —'
  if (!data) return 'Supervision des agents · chargement du runtime Eve…'
  const r = data.runtime
  const eve = data.agents.find((a) => a.id === 'opportunities')
  const worker = r.workerStarted ? 'worker minute démarré' : 'worker non détecté'
  const run =
    eve?.status === 'ACTIF'
      ? 'Eve en exécution'
      : (data.eve?.openTasks ?? 0) > 0
        ? `${data.eve.openTasks} tâche(s) ouverte(s)`
        : 'aucun agent LLM en exécution'
  return `Supervision des agents · ${worker} · ${run}.`
}

function orderRoleCards(cards: AgentRoleCard[]): AgentRoleCard[] {
  const byId = new Map(cards.map((c) => [c.id, c]))
  const ordered: AgentRoleCard[] = []
  for (const id of ROLE_ORDER) {
    const c = byId.get(id)
    if (c) ordered.push(c)
  }
  for (const c of cards) {
    if (!ROLE_ORDER.includes(c.id as (typeof ROLE_ORDER)[number])) ordered.push(c)
  }
  return ordered
}

export function AgentsPage() {
  const { openFiche } = useFicheNav()
  const [data, setData] = useState<AgentsListResponse | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [missionSymbol, setMissionSymbol] = useState('BTCUSDT')
  const [missionBusy, setMissionBusy] = useState(false)
  const [missionMsg, setMissionMsg] = useState<{ ok: boolean; text: string } | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetchAgents()
      setData(res)
      setLoadError(null)
    } catch (err) {
      setData(null)
      setLoadError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const cards = orderRoleCards(data?.agents?.length ? data.agents : FALLBACK_CARDS)
  const chain: AuthorityChain | null = data?.authorityChain ?? null
  const chainSteps = chain?.steps?.length ? [...chain.steps] : CHAIN_DEFAULT
  const eveCard = cards.find((c) => c.id === 'opportunities')

  async function onMission(e: FormEvent) {
    e.preventDefault()
    const symbol = missionSymbol.trim().toUpperCase()
    if (!symbol) return
    setMissionBusy(true)
    setMissionMsg(null)
    try {
      const res = await createAgentMission({
        symbol,
        timeframe: '1h',
        reason: `Surveiller avec Eve depuis Agents · ${symbol}`,
      })
      setMissionMsg({
        ok: true,
        text: `Mission ${res.mission.symbol} · prochain recheck ${fmtDue(res.mission.dueAt)} · thread Copilot ${res.mission.threadId.slice(0, 8)}…`,
      })
      void load()
    } catch (err) {
      setMissionMsg({
        ok: false,
        text: err instanceof Error ? err.message : String(err),
      })
    } finally {
      setMissionBusy(false)
    }
  }

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
        ⬡ <span>{runtimeNotice(data, loadError)}</span>
      </div>

      <div className="agents-section-head">
        <h2>Ève Intelligence</h2>
        <p>Une seule IA · quatre modes · test paper sur portefeuilles existants (pas de live).</p>
      </div>

      <div className="grid three">
        <section className="card agent-card">
          <span className="tag green">IA CENTRALE</span>
          <div className="agent-icon">◆</div>
          <h2>Hub dossiers</h2>
          <p>Dossiers, modes, Risk Kernel → trade paper sur tous les livres virtuels si autonomie on.</p>
          <div className="statline">
            <span>Exécution</span>
            <b>paper si autonomie on</b>
          </div>
          <div className="statline">
            <span>Portefeuille</span>
            <b>tous les virtuels actifs</b>
          </div>
          <div className="statline">
            <span>Permission</span>
            <b>market_read</b>
          </div>
          <button type="button" onClick={() => openFiche({ kind: 'agent', id: 'eve' })}>
            Ouvrir la fiche →
          </button>
        </section>

        {EVE_MODES.map((m) => (
          <section className="card agent-card" key={m.id}>
            {badge(m.tag, m.id === 'guardian' ? 'amber' : 'green')}
            <div className="agent-icon">{m.icon}</div>
            <h2>{m.name}</h2>
            <p>{m.blurb}</p>
            <div className="statline">
              <span>Questions JEV</span>
              <b>{m.primitives}</b>
            </div>
            <div className="statline">
              <span>Accès</span>
              <b>lecture des calculs du moteur</b>
            </div>
            <div className="statline">
              <span>Rôle</span>
              <b>{m.advisoryOnly ? 'donne son avis, la synthèse d’Ève tranche' : '—'}</b>
            </div>
            <button
              type="button"
              onClick={() => openFiche({ kind: 'agent', id: `eve:${m.id}` })}
            >
              Ouvrir la fiche →
            </button>
          </section>
        ))}
      </div>

      <div className="agents-section-head">
        <h2>Chaîne opérationnelle</h2>
        <p>Six rôles (code ou IA), chacun avec ses permissions. Tout reste en paper. Quand l’autonomie est activée, Ève décide sans confirmation humaine.</p>
      </div>

      <div className="grid three">
        {cards.map((a) => (
          <section className="card agent-card" key={a.id}>
            {badge(
              loading && !data ? '—' : a.status,
              loading && !data ? 'gray' : statusBadgeTone(a.status),
            )}
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
            <div className="statline">
              <span>Dernière action</span>
              <b>{dash(a.lastAction, a.lastAction ? undefined : a.statusReason)}</b>
            </div>
            <div className="statline">
              <span>Prochaine tâche</span>
              <b>
                {a.nextTaskDue
                  ? `${a.nextTaskKind ?? 'task'}${a.nextTaskSymbol ? ` · ${a.nextTaskSymbol}` : ''} · ${fmtDue(a.nextTaskDue)}`
                  : dash(null, a.statusReason)}
              </b>
            </div>
            <button type="button" onClick={() => openFiche({ kind: 'agent', id: a.id })}>
              Ouvrir la fiche →
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
            {chainSteps.map((s, i) => {
              const current = chain?.currentStep === s
              return (
                <span key={s} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  {i ? <span aria-hidden="true">→</span> : null}
                  {badge(s, current ? 'green' : 'gray')}
                </span>
              )
            })}
          </div>
          <p style={{ fontSize: 12, color: 'var(--muted)' }}>
            {chain?.currentStep
              ? `Étape courante : ${chain.currentStep} · ${labelEngineCode(chain.reason)}`
              : `Chaque étape dispose d’un périmètre explicite. Étape courante : — (${chain?.reason ? labelEngineCode(chain.reason) : 'aucune décision récente'}). Le contrôle du risque reste nécessaire avant l’exécution.`}
          </p>
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Surveiller avec Eve</h2>
          <small>surveillance d’un instrument · paper · confirmation humaine</small>
        </div>
        <div className="card-body">
          <form className="toolbar" onSubmit={onMission} style={{ flexWrap: 'wrap' }}>
            <input
              type="text"
              value={missionSymbol}
              onChange={(e) => setMissionSymbol(e.target.value)}
              placeholder="BTCUSDT"
              aria-label="Symbole à surveiller"
              style={{ minWidth: 140 }}
            />
            <button type="submit" className="primary" disabled={missionBusy || !!loadError}>
              {missionBusy ? 'Création…' : 'Surveiller avec Eve'}
            </button>
            <Link to="/app/agent" className="link">
              Ouvrir Copilot →
            </Link>
          </form>
          <div className="statline">
            <span>Prochain recheck Eve</span>
            <b>
              {eveCard?.nextTaskDue
                ? `${eveCard.nextTaskKind === 'recheck' ? 'Contrôle' : 'Tâche'}${eveCard.nextTaskSymbol ? ` · ${eveCard.nextTaskSymbol}` : ''} · ${fmtDue(eveCard.nextTaskDue)}`
                : 'Aucune surveillance en cours'}
            </b>
          </div>
          {missionMsg ? (
            <p style={{ fontSize: 12, color: missionMsg.ok ? 'var(--green)' : 'var(--red)' }}>
              {missionMsg.text}
            </p>
          ) : (
            <p style={{ fontSize: 12, color: 'var(--muted)' }}>
              Eve surveille un seul symbole en paper. Une ouverture attend votre confirmation.
            </p>
          )}
        </div>
      </section>
    </div>
  )
}
