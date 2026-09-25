/**
 * Thin client for Chantier 2b — Agents page ↔ Eve runtime API.
 * Paper only · no invented fallbacks (missing → null + reason on server).
 */

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

export type AgentsRuntimeSnapshot = {
  workerStarted: boolean
  workerStartedAt: string | null
  lastDrainAt: string | null
  lastDrain: {
    released: number
    retired: number
    claimed: number
    completed: number
    deferred: number
    failed: number
    wokeLlm: number
  } | null
  lastDrainError: string | null
  intervalMs: number
  draining: boolean
  llmBudget: {
    perWakeMaxIterations: number
    perWakeMaxTokens: number
    dailyBudget: null
    dailyBudgetReason: string
  }
  lastLog: {
    source: string
    message: string
    level: string
    at: string
  } | null
}

export type AuthorityChain = {
  steps: readonly string[]
  currentStep: string | null
  reason: string
  lastLogAt: string | null
}

export type AgentsListResponse = {
  agents: AgentRoleCard[]
  roleOrder: AgentRoleId[]
  paperOnly: boolean
  humanConfirmDefault: boolean
  eve: {
    id: string
    name: string
    openTasks: number
    logs24h: number
  }
  runtime: AgentsRuntimeSnapshot
  authorityChain: AuthorityChain
}

export type CreateMissionInput = {
  symbol: string
  timeframe?: string
  threadId?: string
  reason?: string
  skills?: string[]
  dueAt?: string
}

export type CreateMissionResult = {
  ok: true
  mission: {
    taskId: string
    threadId: string
    created: boolean
    symbol: string
    timeframe: string
    dueAt: string
  }
}

async function parseError(res: Response): Promise<string> {
  const body = (await res.json().catch(() => null)) as
    | { error?: string; detail?: string; message?: string }
    | null
  return body?.error ?? body?.detail ?? body?.message ?? `Erreur ${res.status}`
}

export async function fetchAgents(): Promise<AgentsListResponse> {
  const res = await fetch('/api/agents', { credentials: 'include' })
  if (!res.ok) throw new Error(await parseError(res))
  return (await res.json()) as AgentsListResponse
}

export async function createAgentMission(
  input: CreateMissionInput,
): Promise<CreateMissionResult> {
  const res = await fetch('/api/agents/missions', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  if (!res.ok) throw new Error(await parseError(res))
  return (await res.json()) as CreateMissionResult
}

export function statusBadgeTone(
  status: AgentRoleStatus | string,
): 'green' | 'amber' | 'red' | 'gray' {
  switch (status) {
    case 'ACTIF':
      return 'green'
    case 'EN VEILLE':
      return 'amber'
    case 'EN PAUSE':
      return 'gray'
    case 'ERREUR':
      return 'red'
    default:
      return 'gray'
  }
}

export function fmtDue(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(+d)) return '—'
  return d.toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}
