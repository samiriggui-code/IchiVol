/**
 * Chantier 2 E0 — AgentLog writer (PASSE / PRUDENCE / REFUSÉ).
 * Observability only — never opens paper or calls LLM.
 */
import { Prisma } from '@prisma/client'
import { db } from '../db.js'
import type { AgentLogLevel } from './taskConfig.js'
import { DEFAULT_AGENT_ID } from './taskConfig.js'

export type WriteAgentLogInput = {
  agentId?: string
  level: AgentLogLevel
  source: string
  message: string
  decisionId?: string | null
  positionId?: string | null
  taskId?: string | null
  meta?: Prisma.InputJsonValue | null
}

export async function writeAgentLog(input: WriteAgentLogInput): Promise<{ id: string }> {
  const row = await db.agentLog.create({
    data: {
      agentId: input.agentId ?? DEFAULT_AGENT_ID,
      level: input.level,
      source: input.source,
      message: input.message.slice(0, 4000),
      decisionId: input.decisionId ?? null,
      positionId: input.positionId ?? null,
      taskId: input.taskId ?? null,
      meta: input.meta ?? undefined,
    },
    select: { id: true },
  })
  return row
}
