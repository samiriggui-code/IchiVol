/**
 * Agents — port littéral de design-reference/ichivol-workspace `agents()` + page-head.
 * Classes HTML = maquette. Données = GET /api/agents (Eve runtime + 5 rôles code).
 * FicheHost absent sur main → deep-link ?fiche=agent:id ouvre le dialog permissions (stub).
 */

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  createAgentMission,
  fetchAgents,
  fmtDue,
  statusBadgeTone,
  type AgentRoleCard,
  type AgentsListResponse,
  type AuthorityChain,
} from '../lib/agentsRuntime'
import './AgentsPage.css'

type BadgeTone = 'green' | 'amber' | 'red' | 'gray' | ''

/** Fallback static cards when API unreachable — still shows structure, statuses as — . */
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

const CHAIN_DEFAULT = ['Observation', 'Opportunité', 'Risk Kernel', 'Position', 'Exécution']

function badge(text: string, tone: BadgeTone = ''): ReactNode {
  let inferred = tone
  if (!inferred) {
    inferred = /PASSE|ACCEPTÉ|OUVERTE|VALIDÉ|ACTIF/i.test(text)
      ? 'green'
      : /REFUS|BLOQU|ERREUR/i.test(text)
        ? 'red'
        : /PRUDENCE|ARMED|WATCH|VEILLE/i.test(text)
          ? 'amber'
          : ''
  }
  return <span className={`tag ${inferred}`.trim()}>{text}</span>
}

function dash(value: string | null | undefined, reason?: string): string {
  if (value && value.trim()) return value
  return reason ? `— (${reason})` : '—'
}

function runtimeNotice(data: AgentsListResponse | null, loadError: string | null): string {
  if (loadError) {
    return `Supervision des agents · runtime inaccessible (${loadError}) · —`
  }
  if (!data) {
    return 'Supervision des agents · chargement du runtime Eve…'
  }
  const r = data.runtime
  const parts: string[] = ['Supervision des agents · paper only']
  if (r.workerStarted) {
    parts.push('worker minute démarré')
    if (r.lastDrainAt) parts.push(`dernier drain ${fmtDue(r.lastDrainAt)}`)
    else parts.push('aucun drain encore (boot ≤15s)')
  } else {
    parts.push('worker minute non détecté dans ce process')
  }
  if (r.lastDrainError) parts.push(`erreur drain: ${r.lastDrainError}`)
  const leased = data.agents.find((a) => a.id === 'opportunities')
  if (leased?.status === 'ACTIF') {
    parts.push('Eve en exécution')
  } else if ((data.eve?.openTasks ?? 0) > 0) {
    parts.push(`${data.eve.openTasks} tâche(s) ouverte(s)`)
  } else {
    parts.push('aucun agent LLM en exécution')
  }
  parts.push(r.llmBudget.dailyBudgetReason)
  return parts.join(' · ')
}

export function AgentsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [data, setData] = useState<AgentsListResponse | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [detail, setDetail] = useState<AgentRoleCard | null>(null)
  const [ficheStub, setFicheStub] = useState<string | null>(null)
  const [missionSymbol, setMissionSymbol] = useState('BTCUSDT')
  const [missionBusy, setMissionBusy] = useState(false)
  const [missionMsg, setMissionMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const dialogRef = useRef<HTMLDialogElement>(null)
  const ficheHandled = useRef<string | null>(null)

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

  const cards = data?.agents?.length ? data.agents : FALLBACK_CARDS
  const chain: AuthorityChain | null = data?.authorityChain ?? null
  const chainSteps = chain?.steps?.length ? [...chain.steps] : CHAIN_DEFAULT

  const openDetail = useCallback((card: AgentRoleCard) => {
    setDetail(card)
    dialogRef.current?.showModal()
  }, [])

  const closeDetail = useCallback(() => {
    dialogRef.current?.close()
    setDetail(null)
    setFicheStub(null)
  }, [])

  // Deep-link stub: ?fiche=agent:<id> — FicheHost not on main tip.
  useEffect(() => {
    const raw = searchParams.get('fiche')
    if (!raw || !raw.startsWith('agent:')) return
    if (ficheHandled.current === raw) return
    ficheHandled.current = raw
    const id = raw.slice('agent:'.length).trim()
    const card = cards.find((c) => c.id === id || c.runtimeAgentId === id) ?? null
    setFicheStub(
      `FicheAgent non branchée (FicheHost absent sur main) · deep-link ${raw} · dialog permissions ci-dessous.`,
    )
    if (card) openDetail(card)
    const next = new URLSearchParams(searchParams)
    next.delete('fiche')
    setSearchParams(next, { replace: true })
  }, [searchParams, setSearchParams, cards, openDetail])

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

  const eveCard = cards.find((c) => c.id === 'opportunities')

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

      {ficheStub ? (
        <div className="notice">
          ⬡ <span>{ficheStub}</span>
        </div>
      ) : null}

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
            <button type="button" onClick={() => openDetail(a)}>
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
              ? `Étape courante : ${chain.currentStep} · ${chain.reason}`
              : `Chaque étape dispose d’un périmètre explicite. Étape courante : — (${chain?.reason ?? 'aucune décision récente'}). Le contrôle du risque reste nécessaire avant l’exécution.`}
          </p>
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Surveiller avec Eve</h2>
          <small>mission 1 symbole · paper · confirm humaine</small>
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
                ? `${eveCard.nextTaskKind ?? 'task'}${eveCard.nextTaskSymbol ? ` · ${eveCard.nextTaskSymbol}` : ''} · ${fmtDue(eveCard.nextTaskDue)}`
                : '— (aucune tâche ouverte · annulation API non exposée)'}
            </b>
          </div>
          {missionMsg ? (
            <p style={{ fontSize: 12, color: missionMsg.ok ? 'var(--green)' : 'var(--red)' }}>
              {missionMsg.text}
            </p>
          ) : (
            <p style={{ fontSize: 12, color: 'var(--muted)' }}>
              POST /api/agents/missions · cancel mission = follow-up (pas d’endpoint E1).
            </p>
          )}
        </div>
      </section>

      <dialog
        id="detail"
        ref={dialogRef}
        onClose={() => {
          setDetail(null)
        }}
      >
        {detail ? (
          <div className="dialog-body">
            <div className="dialog-head">
              <h2>{detail.name}</h2>
              <button type="button" onClick={closeDetail} aria-label="Fermer">
                ×
              </button>
            </div>
            {badge(detail.status, statusBadgeTone(detail.status))}
            <p>
              {detail.kind === 'llm'
                ? 'Eve (LLM) · permissions runtime · paper only.'
                : 'Rôle code déterministe · permissions runtime · paper only.'}{' '}
              {detail.statusReason}
            </p>
            <div className="statline">
              <span>Lecture du marché</span>
              <b>
                {badge(
                  /market_read|signals_read|risk_read|paper_orders|orders_execute/.test(
                    detail.permission,
                  )
                    ? 'AUTORISÉE'
                    : '—',
                  'gray',
                )}
              </b>
            </div>
            <div className="statline">
              <span>Modification du risque</span>
              <b>{badge(detail.id === 'risk' ? 'CODE ONLY' : 'BLOQUÉE', 'gray')}</b>
            </div>
            <div className="statline">
              <span>Ordres réels</span>
              <b>{badge('BLOQUÉS')}</b>
            </div>
            <div className="statline">
              <span>Paper / confirm humaine</span>
              <b>
                {badge('OUI', 'green')} · humanConfirmDefault=
                {String(detail.humanConfirmDefault)}
              </b>
            </div>
            <p style={{ fontSize: 12, color: 'var(--muted)' }}>
              FicheAgent (?fiche=agent:{detail.id}) : shell fiches non mergé — dialog maquette
              réutilisé. Activation et permissions effectives vérifiées via le runtime server /
              engine Python.
            </p>
            <div className="dialog-actions">
              {detail.kind === 'llm' ? (
                <Link to="/app/agent" className="link" onClick={closeDetail}>
                  Copilot Eve →
                </Link>
              ) : null}
              <button type="button" onClick={closeDetail}>
                Fermer
              </button>
            </div>
          </div>
        ) : null}
      </dialog>
    </div>
  )
}
