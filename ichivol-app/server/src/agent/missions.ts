/**
 * Chantier 2 E1 — 1-symbol missions (mono-agent + Copilot thread continuity).
 *
 * DOES: create mission AgentTask linked to an existing Copilot thread.
 * DOES NOT: open paper, call broker, spawn a second chat system.
 */
import type { Prisma } from '@prisma/client'
import { nextClosedCandleDueAt } from './candleDue.js'
import { DEFAULT_AGENT_ID } from './taskConfig.js'
import { scheduleTask } from './tasks.js'
import { writeAgentLog } from './agentLog.js'
import { defaultMissionSkills } from './skills/loadSkills.js'
import { createThread, getThreadForUser } from './threads.js'

export type CreateMissionInput = {
  userId: string
  symbol: string
  timeframe?: string
  /** Existing Copilot thread — Eve extends it, does not create a parallel chat product. */
  threadId?: string | null
  reason?: string
  skills?: string[]
  dueAt?: Date
  condition?: Prisma.InputJsonValue | null
  agentId?: string
}

export type CreateMissionResult = {
  taskId: string
  threadId: string
  created: boolean
  symbol: string
  timeframe: string
  dueAt: string
}

export async function createMission(input: CreateMissionInput): Promise<CreateMissionResult> {
  const symbol = input.symbol.trim().toUpperCase()
  if (!symbol) throw new Error('symbol is required')
  // E1: exactly one symbol — reject commas / spaces lists.
  if (/[,\s]/.test(input.symbol.trim())) {
    throw new Error('mission accepts exactly one symbol')
  }

  const timeframe = (input.timeframe ?? '1h').trim() || '1h'
  const agentId = input.agentId ?? DEFAULT_AGENT_ID
  const dueAt = input.dueAt ?? nextClosedCandleDueAt(timeframe)
  const skills = input.skills?.length ? input.skills : defaultMissionSkills('mission')
  const reason =
    (input.reason?.trim() || `Mission watch ${symbol} ${timeframe}`).slice(0, 500)

  let threadId = input.threadId ?? null
  if (threadId) {
    const owned = await getThreadForUser(threadId, input.userId)
    if (!owned) throw new Error('thread not found for user')
  } else {
    const thread = await createThread({
      userId: input.userId,
      assumedSymbol: symbol,
      assumedTimeframe: timeframe,
      lastMode: 'explain_decision',
      title: `Mission · ${symbol} · ${timeframe}`,
    })
    threadId = thread.id
  }

  const payload: Prisma.InputJsonValue = {
    reason,
    timeframe,
    userId: input.userId,
    threadId,
    skills,
    humanConfirmDefault: true,
    autoOpen: false,
    paperOnly: true,
  }

  const idempotencyKey = `mission:${agentId}:${input.userId}:${symbol}:${timeframe}:${dueAt.getTime()}`
  const scheduled = await scheduleTask({
    agentId,
    kind: 'mission',
    symbol,
    dueAt,
    idempotencyKey,
    payload,
    condition: input.condition ?? null,
  })

  await writeAgentLog({
    agentId,
    level: 'PASSE',
    source: 'missions.create',
    message: `Mission ${symbol} ${timeframe} — thread ${threadId}`,
    taskId: scheduled.id,
    meta: { threadId, dueAt: dueAt.toISOString(), skills },
  }).catch(() => {})

  return {
    taskId: scheduled.id,
    threadId,
    created: scheduled.created,
    symbol,
    timeframe,
    dueAt: dueAt.toISOString(),
  }
}
