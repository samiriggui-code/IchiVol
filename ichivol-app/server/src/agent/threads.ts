import { db } from '../db.js'
import type { Citation } from './types.js'

const HISTORY_LIMIT = 24

export async function getThreadForUser(threadId: string, userId: string) {
  return db.agentThread.findFirst({
    where: { id: threadId, userId },
  })
}

export async function createThread(input: {
  userId: string
  assumedSymbol?: string
  assumedTimeframe?: string
  lastMode?: string
  title?: string
}) {
  return db.agentThread.create({
    data: {
      userId: input.userId,
      assumedSymbol: input.assumedSymbol ?? null,
      assumedTimeframe: input.assumedTimeframe ?? null,
      lastMode: input.lastMode ?? null,
      title: input.title ?? null,
    },
  })
}

export async function touchThreadSlots(
  threadId: string,
  slots: {
    assumedSymbol?: string | null
    assumedTimeframe?: string | null
    pendingIntent?: string | null
    lastMode?: string | null
    title?: string | null
  },
) {
  return db.agentThread.update({
    where: { id: threadId },
    data: {
      ...(slots.assumedSymbol !== undefined ? { assumedSymbol: slots.assumedSymbol } : {}),
      ...(slots.assumedTimeframe !== undefined
        ? { assumedTimeframe: slots.assumedTimeframe }
        : {}),
      ...(slots.pendingIntent !== undefined ? { pendingIntent: slots.pendingIntent } : {}),
      ...(slots.lastMode !== undefined ? { lastMode: slots.lastMode } : {}),
      ...(slots.title !== undefined ? { title: slots.title } : {}),
    },
  })
}

export async function appendMessage(input: {
  threadId: string
  role: 'user' | 'assistant'
  content: string
  mode?: string
  intent?: string
  citations?: Citation[]
}) {
  return db.agentMessage.create({
    data: {
      threadId: input.threadId,
      role: input.role,
      content: input.content,
      mode: input.mode ?? null,
      intent: input.intent ?? null,
      citations: input.citations
        ? (JSON.parse(JSON.stringify(input.citations)) as object)
        : undefined,
    },
  })
}

export async function loadThreadHistory(
  threadId: string,
): Promise<Array<{ role: 'user' | 'assistant'; content: string }>> {
  const rows = await db.agentMessage.findMany({
    where: { threadId },
    orderBy: { createdAt: 'asc' },
    take: HISTORY_LIMIT,
    select: { role: true, content: true },
  })
  return rows
    .filter((r) => r.role === 'user' || r.role === 'assistant')
    .map((r) => ({
      role: r.role as 'user' | 'assistant',
      content: r.content,
    }))
}

export async function listThreadsForUser(userId: string, take = 20) {
  return db.agentThread.findMany({
    where: { userId },
    orderBy: { updatedAt: 'desc' },
    take,
    select: {
      id: true,
      title: true,
      assumedSymbol: true,
      assumedTimeframe: true,
      pendingIntent: true,
      lastMode: true,
      updatedAt: true,
      createdAt: true,
      _count: { select: { messages: true } },
    },
  })
}

export async function getThreadWithMessages(threadId: string, userId: string) {
  return db.agentThread.findFirst({
    where: { id: threadId, userId },
    include: {
      messages: {
        orderBy: { createdAt: 'asc' },
        take: HISTORY_LIMIT,
      },
    },
  })
}
