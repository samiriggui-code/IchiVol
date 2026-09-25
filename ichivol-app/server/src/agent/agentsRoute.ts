/**
 * Chantier 2 E1 — front-facing agent control API stubs (no UI wiring yet).
 * GET /api/agents, GET /api/agents/:id/tasks, GET /api/agents/logs, POST /api/agents/missions
 */
import type { Request, Response } from 'express'
import { db } from '../db.js'
import { createMission } from './missions.js'
import { DEFAULT_AGENT_ID } from './taskConfig.js'

const DEFAULT_LIMIT = 50
const MAX_LIMIT = 200

function parseLimit(raw: unknown): number {
  const n = Number(raw)
  if (!Number.isFinite(n) || n < 1) return DEFAULT_LIMIT
  return Math.min(Math.floor(n), MAX_LIMIT)
}

/** Mono-agent until multi-agent proven — expose the eve lane. */
export async function handleListAgents(_req: Request, res: Response): Promise<void> {
  const [openTasks, recentLogs] = await Promise.all([
    db.agentTask.count({
      where: {
        agentId: DEFAULT_AGENT_ID,
        status: { in: ['pending', 'leased'] },
      },
    }),
    db.agentLog.count({
      where: {
        agentId: DEFAULT_AGENT_ID,
        createdAt: { gte: new Date(Date.now() - 24 * 60 * 60_000) },
      },
    }),
  ])

  res.json({
    agents: [
      {
        id: DEFAULT_AGENT_ID,
        name: 'Eve',
        role: 'mono-agent',
        paperOnly: true,
        humanConfirmDefault: true,
        autoOpen: false,
        openTasks,
        logs24h: recentLogs,
        chat: 'copilot_threads',
      },
    ],
  })
}

export async function handleListAgentTasks(req: Request, res: Response): Promise<void> {
  const agentId = String(req.params.id || DEFAULT_AGENT_ID)
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
  const agentId =
    typeof req.query.agentId === 'string' && req.query.agentId.trim()
      ? req.query.agentId.trim()
      : undefined

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
