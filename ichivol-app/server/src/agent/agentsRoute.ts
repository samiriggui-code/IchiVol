/**
 * Chantier 2 E1/2b — front-facing agent control API.
 * GET /api/agents (6 role cards + runtime), GET /api/agents/:id/tasks,
 * GET /api/agents/logs, POST /api/agents/missions
 */
import type { Request, Response } from 'express'
import { config } from '../config.js'
import { db } from '../db.js'
import { checkSystemHealth } from '../health/check.js'
import { resolveLlmForUser } from '../settings/resolve.js'
import {
  AGENT_ROLE_ORDER,
  authorityStepFromLogSource,
  deriveRoleCards,
  type RoleSignals,
} from './agentRoles.js'
import { createMission } from './missions.js'
import { getAgentRuntimeSnapshot } from './runtime/dispatcher.js'
import { DEFAULT_AGENT_ID } from './taskConfig.js'
import { MISSION_MAX_ITERATIONS, MISSION_MAX_TOKENS } from './runtime/missionRunner.js'

const DEFAULT_LIMIT = 50
const MAX_LIMIT = 200
const PORTFOLIO_CODE = 'ICHIVOL_BASELINE_V1'
const ENGINE_TIMEOUT_MS = 4_000

function parseLimit(raw: unknown): number {
  const n = Number(raw)
  if (!Number.isFinite(n) || n < 1) return DEFAULT_LIMIT
  return Math.min(Math.floor(n), MAX_LIMIT)
}

async function fetchEngineJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${config.engineUrl}${path}`, {
      signal: AbortSignal.timeout(ENGINE_TIMEOUT_MS),
    })
    if (!res.ok) return null
    return (await res.json()) as T
  } catch {
    return null
  }
}

/** FX session windows — same venues as front marketSessions (server-side copy). */
function countOpenFxSessions(now = new Date()): number {
  const defs: Array<{ tz: string; open: number; close: number }> = [
    { tz: 'Asia/Tokyo', open: 9, close: 18 },
    { tz: 'Europe/London', open: 8, close: 17 },
    { tz: 'America/New_York', open: 9.5, close: 16 },
  ]
  let open = 0
  for (const d of defs) {
    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: d.tz,
      weekday: 'short',
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    }).formatToParts(now)
    const wd = parts.find((p) => p.type === 'weekday')?.value ?? ''
    if (wd === 'Sat' || wd === 'Sun') continue
    const hour = Number(parts.find((p) => p.type === 'hour')?.value ?? 0)
    const minute = Number(parts.find((p) => p.type === 'minute')?.value ?? 0)
    const h = hour + minute / 60
    if (h >= d.open && h < d.close) open += 1
  }
  return open
}

async function llmKeyPresentForUser(userId: string | undefined): Promise<boolean | null> {
  const envPresent = Boolean(
    config.anthropicApiKey || config.openaiApiKey || config.openrouterApiKey,
  )
  if (envPresent) return true
  if (!userId) return false
  try {
    const resolved = await resolveLlmForUser(userId)
    return Boolean(resolved.apiKey)
  } catch {
    return null
  }
}

async function gatherRoleSignals(userId?: string): Promise<RoleSignals> {
  const health = await checkSystemHealth()
  const since = new Date(Date.now() - 24 * 60 * 60_000)
  const runtime = getAgentRuntimeSnapshot()

  const [
    openTasks,
    leasedTasks,
    recheckOpen,
    logs24h,
    lastLog,
    nextTask,
    riskLock,
    positions,
    llmKey,
  ] = await Promise.all([
    db.agentTask.count({
      where: {
        agentId: DEFAULT_AGENT_ID,
        status: { in: ['pending', 'leased'] },
      },
    }),
    db.agentTask.count({
      where: { agentId: DEFAULT_AGENT_ID, status: 'leased' },
    }),
    db.agentTask.count({
      where: {
        agentId: DEFAULT_AGENT_ID,
        kind: 'recheck',
        status: { in: ['pending', 'leased'] },
      },
    }),
    db.agentLog.count({
      where: { agentId: DEFAULT_AGENT_ID, createdAt: { gte: since } },
    }),
    db.agentLog.findFirst({
      where: { agentId: DEFAULT_AGENT_ID },
      orderBy: { createdAt: 'desc' },
      select: { message: true, createdAt: true, source: true },
    }),
    db.agentTask.findFirst({
      where: {
        agentId: DEFAULT_AGENT_ID,
        status: { in: ['pending', 'leased'] },
      },
      orderBy: { dueAt: 'asc' },
      select: { dueAt: true, kind: true, symbol: true },
    }),
    health.engine
      ? fetchEngineJson<{
          kill_switch_armed?: boolean
        }>(`/api/engine/paper/portfolios/${PORTFOLIO_CODE}/risk-lock`)
      : Promise.resolve(null),
    health.engine
      ? fetchEngineJson<{ positions?: unknown[]; count?: number }>(
          '/api/engine/paper/positions?status=OPEN',
        )
      : Promise.resolve(null),
    llmKeyPresentForUser(userId),
  ])

  let openPaper: number | null = null
  if (positions) {
    if (typeof positions.count === 'number') openPaper = positions.count
    else if (Array.isArray(positions.positions)) openPaper = positions.positions.length
  }

  return {
    engineOk: health.engine,
    databaseOk: health.database,
    workerStarted: runtime.workerStarted,
    killSwitchArmed:
      riskLock && typeof riskLock.kill_switch_armed === 'boolean'
        ? riskLock.kill_switch_armed
        : null,
    openPaperPositions: openPaper,
    openSessions: countOpenFxSessions(),
    eveOpenTasks: openTasks,
    eveLeasedTasks: leasedTasks,
    eveRecheckOpen: recheckOpen,
    eveLastLogMessage: lastLog?.message ?? null,
    eveLastLogAt: lastLog?.createdAt?.toISOString() ?? null,
    eveNextDueAt: nextTask?.dueAt?.toISOString() ?? null,
    eveNextKind: nextTask?.kind ?? null,
    eveNextSymbol: nextTask?.symbol ?? null,
    eveLogs24h: logs24h,
    llmKeyPresent: llmKey,
  }
}

/** 6 role cards + Eve runtime notice payload. */
export async function handleListAgents(req: Request, res: Response): Promise<void> {
  const [signals, lastLog] = await Promise.all([
    gatherRoleSignals(req.user?.id),
    db.agentLog.findFirst({
      where: { agentId: DEFAULT_AGENT_ID },
      orderBy: { createdAt: 'desc' },
      select: { source: true, message: true, createdAt: true, level: true },
    }),
  ])

  const agents = deriveRoleCards(signals)
  const runtime = getAgentRuntimeSnapshot()
  const authorityStep = authorityStepFromLogSource(lastLog?.source)

  res.json({
    agents,
    roleOrder: AGENT_ROLE_ORDER,
    paperOnly: true,
    humanConfirmDefault: true,
    /** Backward-compatible mono Eve summary (E1 clients). */
    eve: {
      id: DEFAULT_AGENT_ID,
      name: 'Eve',
      role: 'mono-agent',
      paperOnly: true,
      humanConfirmDefault: true,
      autoOpen: false,
      openTasks: signals.eveOpenTasks,
      logs24h: signals.eveLogs24h,
      chat: 'copilot_threads',
    },
    runtime: {
      workerStarted: runtime.workerStarted,
      workerStartedAt: runtime.workerStartedAt,
      lastDrainAt: runtime.lastDrainAt,
      lastDrain: runtime.lastDrain,
      lastDrainError: runtime.lastDrainError,
      intervalMs: runtime.intervalMs,
      draining: runtime.draining,
      llmBudget: {
        perWakeMaxIterations: MISSION_MAX_ITERATIONS,
        perWakeMaxTokens: MISSION_MAX_TOKENS,
        dailyBudget: null,
        dailyBudgetReason: 'budget LLM journalier non exposé — caps E1 par wake uniquement',
      },
      lastLog: lastLog
        ? {
            source: lastLog.source,
            message: lastLog.message,
            level: lastLog.level,
            at: lastLog.createdAt.toISOString(),
          }
        : null,
    },
    authorityChain: {
      steps: ['Observation', 'Opportunité', 'Risk Kernel', 'Position', 'Exécution'] as const,
      currentStep: authorityStep,
      reason: authorityStep
        ? `dérivé du dernier AgentLog (${lastLog?.source ?? '—'})`
        : 'aucune décision récente exposée — étape courante inconnue',
      lastLogAt: lastLog?.createdAt?.toISOString() ?? null,
    },
  })
}

export async function handleListAgentTasks(req: Request, res: Response): Promise<void> {
  const rawId = String(req.params.id || DEFAULT_AGENT_ID)
  // Role alias → Eve lane (opportunities card).
  const agentId = rawId === 'opportunities' ? DEFAULT_AGENT_ID : rawId
  const limit = parseLimit(req.query.limit)
  const status = typeof req.query.status === 'string' ? req.query.status : undefined

  const tasks = await db.agentTask.findMany({
    where: {
      agentId,
      ...(status ? { status } : {}),
    },
    orderBy: { dueAt: 'asc' },
    take: limit,
    select: {
      id: true,
      agentId: true,
      kind: true,
      symbol: true,
      status: true,
      dueAt: true,
      attempts: true,
      leaseUntil: true,
      idempotencyKey: true,
      error: true,
      createdAt: true,
      updatedAt: true,
    },
  })

  res.json({ agentId, tasks })
}

export async function handleListAgentLogs(req: Request, res: Response): Promise<void> {
  const limit = parseLimit(req.query.limit)
  const rawAgentId =
    typeof req.query.agentId === 'string' && req.query.agentId.trim()
      ? req.query.agentId.trim()
      : undefined
  const agentId =
    rawAgentId === 'opportunities' ? DEFAULT_AGENT_ID : rawAgentId

  const logs = await db.agentLog.findMany({
    where: agentId ? { agentId } : undefined,
    orderBy: { createdAt: 'desc' },
    take: limit,
    select: {
      id: true,
      agentId: true,
      level: true,
      source: true,
      message: true,
      taskId: true,
      decisionId: true,
      positionId: true,
      meta: true,
      createdAt: true,
    },
  })

  res.json({ logs })
}

export async function handleCreateAgentMission(req: Request, res: Response): Promise<void> {
  if (!req.user) {
    res.status(401).json({ error: 'Non authentifié' })
    return
  }

  const body = req.body as {
    symbol?: string
    timeframe?: string
    threadId?: string
    reason?: string
    skills?: string[]
    dueAt?: string
  }

  if (!body.symbol || typeof body.symbol !== 'string') {
    res.status(400).json({ error: 'symbol is required' })
    return
  }

  let dueAt: Date | undefined
  if (typeof body.dueAt === 'string' && body.dueAt.trim()) {
    dueAt = new Date(body.dueAt)
    if (Number.isNaN(dueAt.getTime())) {
      res.status(400).json({ error: 'dueAt must be ISO datetime' })
      return
    }
  }

  try {
    const mission = await createMission({
      userId: req.user.id,
      symbol: body.symbol,
      timeframe: body.timeframe,
      threadId: body.threadId,
      reason: body.reason,
      skills: body.skills,
      dueAt,
    })
    res.status(201).json({ ok: true, mission })
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    const status = /thread not found|exactly one symbol|required/i.test(message) ? 400 : 500
    res.status(status).json({ error: message })
  }
}
