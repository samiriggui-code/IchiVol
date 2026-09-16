import type { Request, Response } from 'express'
import { getThreadWithMessages, listThreadsForUser } from './threads.js'

export async function handleListAgentThreads(req: Request, res: Response): Promise<void> {
  if (!req.user) {
    res.status(401).json({ error: 'Non authentifié' })
    return
  }
  const rows = await listThreadsForUser(req.user.id)
  res.json({
    threads: rows.map((t) => ({
      id: t.id,
      title: t.title,
      assumedSymbol: t.assumedSymbol,
      assumedTimeframe: t.assumedTimeframe,
      pendingIntent: t.pendingIntent,
      lastMode: t.lastMode,
      messageCount: t._count.messages,
      updatedAt: t.updatedAt.toISOString(),
      createdAt: t.createdAt.toISOString(),
    })),
  })
}

export async function handleGetAgentThread(req: Request, res: Response): Promise<void> {
  if (!req.user) {
    res.status(401).json({ error: 'Non authentifié' })
    return
  }
  const id = req.params.id
  if (!id) {
    res.status(400).json({ error: 'id requis' })
    return
  }
  const thread = await getThreadWithMessages(id, req.user.id)
  if (!thread) {
    res.status(404).json({ error: 'Thread introuvable' })
    return
  }
  res.json({
    id: thread.id,
    title: thread.title,
    assumedSymbol: thread.assumedSymbol,
    assumedTimeframe: thread.assumedTimeframe,
    pendingIntent: thread.pendingIntent,
    lastMode: thread.lastMode,
    updatedAt: thread.updatedAt.toISOString(),
    messages: thread.messages.map((m) => ({
      id: m.id,
      role: m.role,
      content: m.content,
      mode: m.mode,
      intent: m.intent,
      citations: m.citations,
      createdAt: m.createdAt.toISOString(),
    })),
  })
}
