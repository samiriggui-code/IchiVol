/**
 * Chantier 2b — 6 role cards for Agents page (1 LLM Eve + 5 code).
 * Statuses are derived honestly from engine/runtime signals — never invented.
 */
import { DEFAULT_AGENT_ID } from './taskConfig.js'

export type AgentRoleStatus = 'ACTIF' | 'EN VEILLE' | 'EN PAUSE' | 'ERREUR'

export type AgentRoleKind = 'llm' | 'code'

export type AgentRoleId =
  | 'observer'
  | 'opportunities'
  | 'risk'
  | 'execution'
  | 'position'
  | 'session'

export type AgentRoleCard = {
  id: AgentRoleId
  name: string
  kind: AgentRoleKind
  /** Eve lane id when kind=llm — tasks/logs keyed here. */
  runtimeAgentId: string | null
  status: AgentRoleStatus
  statusReason: string
  mode: string
  permission: string
  blurb: string
  icon: string
  lastAction: string | null
  lastActionAt: string | null
  nextTaskDue: string | null
  nextTaskKind: string | null
  nextTaskSymbol: string | null
  counts24h: number
  openTasks: number
  paperOnly: true
  humanConfirmDefault: true
  autoOpen: false
  chat: 'copilot_threads' | null
}

export type RoleSignals = {
  engineOk: boolean
  databaseOk: boolean
  workerStarted: boolean
  killSwitchArmed: boolean | null
  openPaperPositions: number | null
  /** FX venues currently open (Tokyo/London/NY) — null if calendar unavailable. */
  openSessions: number | null
  eveOpenTasks: number
  eveLeasedTasks: number
  eveRecheckOpen: number
  eveLastLogMessage: string | null
  eveLastLogAt: string | null
  eveNextDueAt: string | null
  eveNextKind: string | null
  eveNextSymbol: string | null
  eveLogs24h: number
  llmKeyPresent: boolean | null
}

const ROLE_META: Record<
  AgentRoleId,
  {
    name: string
    kind: AgentRoleKind
    mode: string
    permission: string
    blurb: string
    icon: string
    chat: 'copilot_threads' | null
  }
> = {
  observer: {
    name: 'Observateur de marché',
    kind: 'code',
    mode: 'Règles',
    permission: 'market_read',
    blurb: 'Observe les régimes et la structure du marché.',
    icon: '◎',
    chat: null,
  },
  opportunities: {
    name: 'Opportunités',
    kind: 'llm',
    mode: 'LLM / règles',
    permission: 'signals_read',
    blurb: 'Repère les setups et rassemble les preuves.',
    icon: '◇',
    chat: 'copilot_threads',
  },
  risk: {
    name: 'Risque',
    kind: 'code',
    mode: 'Règles',
    permission: 'risk_read',
    blurb: 'Applique les limites du Risk Kernel.',
    icon: '◈',
    chat: null,
  },
  execution: {
    name: 'Exécution',
    kind: 'code',
    mode: 'Règles',
    permission: 'orders_execute',
    blurb: 'Transmet uniquement les décisions validées.',
    icon: '↗',
    chat: null,
  },
  position: {
    name: 'Gestion de position',
    kind: 'code',
    mode: 'Règles',
    permission: 'paper_orders',
    blurb: 'Surveille le stop et les conditions de sortie.',
    icon: '◫',
    chat: null,
  },
  session: {
    name: 'Session',
    kind: 'code',
    mode: 'Règles',
    permission: 'market_read',
    blurb: 'Suit les horaires et contraintes de session.',
    icon: '◷',
    chat: null,
  },
}

export const AGENT_ROLE_ORDER: AgentRoleId[] = [
  'observer',
  'opportunities',
  'risk',
  'execution',
  'position',
  'session',
]

function baseCard(
  id: AgentRoleId,
  status: AgentRoleStatus,
  statusReason: string,
  extras: Partial<
    Pick<
      AgentRoleCard,
      | 'lastAction'
      | 'lastActionAt'
      | 'nextTaskDue'
      | 'nextTaskKind'
      | 'nextTaskSymbol'
      | 'counts24h'
      | 'openTasks'
    >
  > = {},
): AgentRoleCard {
  const meta = ROLE_META[id]
  return {
    id,
    name: meta.name,
    kind: meta.kind,
    runtimeAgentId: id === 'opportunities' ? DEFAULT_AGENT_ID : null,
    status,
    statusReason,
    mode: meta.mode,
    permission: meta.permission,
    blurb: meta.blurb,
    icon: meta.icon,
    lastAction: extras.lastAction ?? null,
    lastActionAt: extras.lastActionAt ?? null,
    nextTaskDue: extras.nextTaskDue ?? null,
    nextTaskKind: extras.nextTaskKind ?? null,
    nextTaskSymbol: extras.nextTaskSymbol ?? null,
    counts24h: extras.counts24h ?? 0,
    openTasks: extras.openTasks ?? 0,
    paperOnly: true,
    humanConfirmDefault: true,
    autoOpen: false,
    chat: meta.chat,
  }
}

export function deriveRoleCards(signals: RoleSignals): AgentRoleCard[] {
  const observer = !signals.engineOk
    ? baseCard('observer', 'ERREUR', 'moteur Python injoignable')
    : baseCard('observer', 'ACTIF', 'screener / market via engine')

  let opportunities: AgentRoleCard
  if (!signals.databaseOk) {
    opportunities = baseCard('opportunities', 'ERREUR', 'base Postgres injoignable')
  } else if (signals.llmKeyPresent === false) {
    opportunities = baseCard('opportunities', 'EN PAUSE', 'aucune clé LLM configurée', {
      lastAction: signals.eveLastLogMessage,
      lastActionAt: signals.eveLastLogAt,
      nextTaskDue: signals.eveNextDueAt,
      nextTaskKind: signals.eveNextKind,
      nextTaskSymbol: signals.eveNextSymbol,
      counts24h: signals.eveLogs24h,
      openTasks: signals.eveOpenTasks,
    })
  } else if (signals.eveLeasedTasks > 0) {
    opportunities = baseCard('opportunities', 'ACTIF', 'tâche Eve en cours (leased)', {
      lastAction: signals.eveLastLogMessage,
      lastActionAt: signals.eveLastLogAt,
      nextTaskDue: signals.eveNextDueAt,
      nextTaskKind: signals.eveNextKind,
      nextTaskSymbol: signals.eveNextSymbol,
      counts24h: signals.eveLogs24h,
      openTasks: signals.eveOpenTasks,
    })
  } else if (signals.eveOpenTasks > 0) {
    opportunities = baseCard(
      'opportunities',
      'EN VEILLE',
      `${signals.eveOpenTasks} tâche(s) ouverte(s) — worker ${signals.workerStarted ? 'démarré' : 'non détecté'}`,
      {
        lastAction: signals.eveLastLogMessage,
        lastActionAt: signals.eveLastLogAt,
        nextTaskDue: signals.eveNextDueAt,
        nextTaskKind: signals.eveNextKind,
        nextTaskSymbol: signals.eveNextSymbol,
        counts24h: signals.eveLogs24h,
        openTasks: signals.eveOpenTasks,
      },
    )
  } else if (signals.workerStarted) {
    opportunities = baseCard(
      'opportunities',
      'EN VEILLE',
      'worker minute démarré · aucune tâche ouverte',
      {
        lastAction: signals.eveLastLogMessage,
        lastActionAt: signals.eveLastLogAt,
        counts24h: signals.eveLogs24h,
        openTasks: 0,
      },
    )
  } else {
    opportunities = baseCard(
      'opportunities',
      'EN PAUSE',
      'worker minute non démarré dans ce process',
      {
        lastAction: signals.eveLastLogMessage,
        lastActionAt: signals.eveLastLogAt,
        counts24h: signals.eveLogs24h,
      },
    )
  }

  const risk = !signals.engineOk
    ? baseCard('risk', 'ERREUR', 'risk_kernel indisponible (engine down)')
    : baseCard('risk', 'ACTIF', 'risk_kernel code — évalué avant paper')

  let execution: AgentRoleCard
  if (!signals.engineOk) {
    execution = baseCard('execution', 'ERREUR', 'paper gateway injoignable')
  } else if (signals.killSwitchArmed === true) {
    execution = baseCard('execution', 'EN PAUSE', 'kill switch armé — entrées bloquées')
  } else if (signals.killSwitchArmed === null) {
    execution = baseCard(
      'execution',
      'ACTIF',
      'paper gateway joignable · état kill-switch non lu',
    )
  } else {
    execution = baseCard('execution', 'ACTIF', 'paper gateway · human confirm default')
  }

  let position: AgentRoleCard
  if (!signals.engineOk) {
    position = baseCard('position', 'ERREUR', 'positions paper injoignables')
  } else if (signals.openPaperPositions != null && signals.openPaperPositions > 0) {
    position = baseCard(
      'position',
      'ACTIF',
      `${signals.openPaperPositions} position(s) paper ouverte(s)`,
      {
        nextTaskDue: signals.eveNextDueAt,
        nextTaskKind: signals.eveRecheckOpen > 0 ? 'recheck' : signals.eveNextKind,
        nextTaskSymbol: signals.eveNextSymbol,
        openTasks: signals.eveRecheckOpen,
      },
    )
  } else if (signals.eveRecheckOpen > 0) {
    position = baseCard(
      'position',
      'EN VEILLE',
      `${signals.eveRecheckOpen} recheck Eve ouvert(s)`,
      {
        nextTaskDue: signals.eveNextDueAt,
        nextTaskKind: 'recheck',
        nextTaskSymbol: signals.eveNextSymbol,
        openTasks: signals.eveRecheckOpen,
      },
    )
  } else {
    position = baseCard(
      'position',
      'EN VEILLE',
      signals.openPaperPositions == null
        ? 'engine OK · compte positions non lu'
        : 'aucune position paper ouverte',
    )
  }

  let session: AgentRoleCard
  if (signals.openSessions == null) {
    session = baseCard(
      'session',
      'EN VEILLE',
      'calendrier sessions FX non exposé côté API — crypto 24/7',
    )
  } else if (signals.openSessions > 0) {
    session = baseCard(
      'session',
      'ACTIF',
      `${signals.openSessions} session(s) FX ouverte(s) · crypto 24/7`,
    )
  } else {
    session = baseCard('session', 'EN VEILLE', 'sessions FX fermées · crypto 24/7')
  }

  return [observer, opportunities, risk, execution, position, session]
}

export type AuthorityStep =
  | 'Observation'
  | 'Opportunité'
  | 'Risk Kernel'
  | 'Position'
  | 'Exécution'

/** Map last AgentLog source → authority chain step when determinable. */
export function authorityStepFromLogSource(source: string | null | undefined): AuthorityStep | null {
  if (!source) return null
  const s = source.toLowerCase()
  if (s.includes('mission') || s.includes('recheck') || s.includes('claude') || s.includes('llm')) {
    return 'Opportunité'
  }
  if (s.includes('risk') || s.includes('kill')) return 'Risk Kernel'
  if (s.includes('position') || s.includes('paper') || s.includes('proximity')) return 'Position'
  if (s.includes('order') || s.includes('exec') || s.includes('gateway')) return 'Exécution'
  if (s.includes('screener') || s.includes('market') || s.includes('observer')) return 'Observation'
  if (s.includes('runtime.dispatcher') || s.includes('runtime.missionrunner')) return 'Opportunité'
  return null
}
