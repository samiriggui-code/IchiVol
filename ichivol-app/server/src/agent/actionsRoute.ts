import type { Request, Response } from 'express'
import { config } from '../config.js'
import { writeAuditLog } from '../audit/log.js'
import { db } from '../db.js'
import { createNotification } from '../notifications/create.js'
import { getDecisionDetailTool } from './tools/getDecisionDetail.js'
import { appendMessage, getThreadForUser, touchThreadSlots } from './threads.js'

const ALLOWED = new Set(['save_decision', 'pin_symbol', 'open_paper_position'])

function parseBody(body: unknown):
  | {
      ok: true
      data: {
        intent: 'save_decision' | 'pin_symbol' | 'open_paper_position'
        confirm: boolean
        symbol?: string
        timeframe?: string
        threadId?: string
        actionId?: string
      }
    }
  | { ok: false; error: string } {
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return { ok: false, error: 'Body JSON requis' }
  }
  const raw = body as Record<string, unknown>
  const intent = typeof raw.intent === 'string' ? raw.intent : ''
  if (!ALLOWED.has(intent)) {
    return { ok: false, error: 'intent non allowlisté (save_decision|pin_symbol|open_paper_position)' }
  }
  if (typeof raw.confirm !== 'boolean') {
    return { ok: false, error: 'confirm boolean requis' }
  }
  return {
    ok: true,
    data: {
      intent: intent as 'save_decision' | 'pin_symbol' | 'open_paper_position',
      confirm: raw.confirm,
      symbol: typeof raw.symbol === 'string' ? raw.symbol.trim().toUpperCase() : undefined,
      timeframe: typeof raw.timeframe === 'string' ? raw.timeframe.trim() : undefined,
      threadId: typeof raw.threadId === 'string' ? raw.threadId : undefined,
      actionId: typeof raw.actionId === 'string' ? raw.actionId : undefined,
    },
  }
}

async function executeSaveDecision(
  userId: string,
  symbol: string,
  timeframe: string,
): Promise<{ ok: true; result: Record<string, unknown> } | { ok: false; error: string }> {
  const detail = await getDecisionDetailTool(symbol, timeframe)
  if (!detail.ok) {
    return { ok: false, error: detail.error }
  }
  const d = detail.data
  const bias = d.direction
  const rvol = d.rvol ?? 0

  const existing = await db.decision.findFirst({
    where: { userId, symbol: d.symbol, interval: d.timeframe, status: 'confirmed' },
    orderBy: { createdAt: 'desc' },
  })

  if (existing) {
    const prevGate = existing.gateDecision
    const row = await db.decision.update({
      where: { id: existing.id },
      data: {
        bias,
        rvol,
        signalKind: d.combiner,
        gateDecision: d.gateDecision ?? existing.gateDecision,
        confidence: d.confidence ?? existing.confidence,
      },
    })
    const nextGate = row.gateDecision
    if (nextGate && prevGate && nextGate !== prevGate) {
      await createNotification({
        userId,
        kind: 'pipeline_change',
        title: `${row.symbol} · portes mises à jour`,
        body: `${prevGate} → ${nextGate} (${row.interval}) via Copilot.`,
        payload: {
          decisionId: row.id,
          symbol: row.symbol,
          interval: row.interval,
          prevGate,
          nextGate,
          via: 'agent',
        },
      })
    }
    return {
      ok: true,
      result: { decisionId: row.id, deduped: true, symbol: row.symbol, gateDecision: row.gateDecision },
    }
  }

  const row = await db.decision.create({
    data: {
      userId,
      symbol: d.symbol,
      interval: d.timeframe,
      bias,
      rvol,
      signalKind: d.combiner,
      gateDecision: d.gateDecision ?? undefined,
      confidence: d.confidence ?? undefined,
      status: 'confirmed',
    },
  })
  await createNotification({
    userId,
    kind: 'journal_confirm',
    title: `${row.symbol} · au journal`,
    body: `Confirmé via Copilot (${row.interval}${row.gateDecision ? ` · ${row.gateDecision}` : ''}).`,
    payload: { decisionId: row.id, symbol: row.symbol, interval: row.interval, via: 'agent' },
  })
  return {
    ok: true,
    result: { decisionId: row.id, deduped: false, symbol: row.symbol, gateDecision: row.gateDecision },
  }
}

async function executePinSymbol(
  userId: string,
  symbol: string,
): Promise<{ ok: true; result: Record<string, unknown> } | { ok: false; error: string }> {
  const row = await db.watchlistItem.upsert({
    where: { userId_symbol: { userId, symbol } },
    create: { userId, symbol },
    update: { updatedAt: new Date() },
  })
  return { ok: true, result: { watchlistId: row.id, symbol: row.symbol } }
}

const OPEN_PAPER_TIMEOUT_MS = 45_000

/**
 * Ouvre une position papier (virtuelle, jamais un ordre réel) en relayant
 * tel quel POST /api/engine/paper/positions -- le moteur rescane le symbole
 * en live et tranche seul sur pipeline.decision ; ce handler ne transmet
 * jamais de direction/decision choisie par le LLM (seul symbol+timeframe
 * partent vers l'engine), pour qu'un vote LLM ne puisse pas se glisser ici.
 */
async function executeOpenPaperPosition(
  userId: string,
  symbol: string,
  timeframe: string,
): Promise<{ ok: true; result: Record<string, unknown> } | { ok: false; error: string }> {
  const url = new URL(`${config.engineUrl}/api/engine/paper/positions`)
  url.searchParams.set('symbol', symbol)
  url.searchParams.set('user_id', userId)
  url.searchParams.set('timeframe', timeframe)

  let engineRes: globalThis.Response
  try {
    engineRes = await fetch(url, { method: 'POST', signal: AbortSignal.timeout(OPEN_PAPER_TIMEOUT_MS) })
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : 'engine unreachable' }
  }

  const body = (await engineRes.json().catch(() => null)) as Record<string, unknown> | null

  if (!engineRes.ok) {
    const detail = body && typeof body.detail === 'string' ? body.detail : null
    if (engineRes.status === 422) {
      return {
        ok: false,
        error:
          detail ??
          'not_actionable : le moteur ne confirme plus de BUY/SELL sur ce symbole au moment de la confirmation',
      }
    }
    if (engineRes.status === 404) {
      return { ok: false, error: detail ?? 'historique insuffisant pour ce symbole/timeframe' }
    }
    return { ok: false, error: detail ?? `engine HTTP ${engineRes.status}` }
  }

  return { ok: true, result: body ?? {} }
}

/**
 * POST /api/agent/actions/confirm
 * Exécute une action mute allowlistée après confirmation UI.
 */
export async function handleConfirmAgentAction(req: Request, res: Response): Promise<void> {
  if (!req.user) {
    res.status(401).json({ error: 'Non authentifié' })
    return
  }

  const parsed = parseBody(req.body)
  if (!parsed.ok) {
    res.status(400).json({ error: parsed.error })
    return
  }

  const { intent, confirm, threadId, actionId } = parsed.data
  let symbol = parsed.data.symbol
  let timeframe = parsed.data.timeframe ?? '1h'

  if (threadId) {
    const thread = await getThreadForUser(threadId, req.user.id)
    if (!thread) {
      res.status(404).json({ error: 'Thread introuvable' })
      return
    }
    symbol = symbol ?? thread.assumedSymbol ?? undefined
    timeframe = parsed.data.timeframe ?? thread.assumedTimeframe ?? '1h'
  }

  if (!symbol) {
    res.status(400).json({ error: 'symbol requis' })
    return
  }

  let action =
    actionId != null
      ? await db.agentAction.findFirst({ where: { id: actionId, userId: req.user.id } })
      : null

  if (!action) {
    action = await db.agentAction.create({
      data: {
        userId: req.user.id,
        kind: intent,
        status: 'proposed',
        symbol,
        timeframe,
        threadId: threadId ?? null,
        payload: { intent, symbol, timeframe },
      },
    })
  }

  if (!confirm) {
    const rejected = await db.agentAction.update({
      where: { id: action.id },
      data: { status: 'rejected' },
    })
    await writeAuditLog({
      userId: req.user.id,
      action: 'agent.action.reject',
      meta: { actionId: rejected.id, intent, symbol },
    })
    if (threadId) {
      await touchThreadSlots(threadId, { pendingIntent: null })
      await appendMessage({
        threadId,
        role: 'assistant',
        content: `Action annulée : ${intent} sur ${symbol}.`,
        intent,
      })
    }
    res.json({ ok: true, status: 'rejected', actionId: rejected.id })
    return
  }

  const exec =
    intent === 'save_decision'
      ? await executeSaveDecision(req.user.id, symbol, timeframe)
      : intent === 'pin_symbol'
        ? await executePinSymbol(req.user.id, symbol)
        : await executeOpenPaperPosition(req.user.id, symbol, timeframe)

  if (!exec.ok) {
    await db.agentAction.update({
      where: { id: action.id },
      data: { status: 'failed', error: exec.error },
    })
    await writeAuditLog({
      userId: req.user.id,
      action: 'agent.action.fail',
      meta: { actionId: action.id, intent, symbol, error: exec.error },
    })
    res.status(502).json({ error: exec.error, actionId: action.id })
    return
  }

  const done = await db.agentAction.update({
    where: { id: action.id },
    data: {
      status: 'confirmed',
      result: exec.result as object,
      error: null,
    },
  })

  await writeAuditLog({
    userId: req.user.id,
    action: 'agent.action.confirm',
    meta: { actionId: done.id, intent, symbol, result: exec.result },
  })

  if (threadId) {
    await touchThreadSlots(threadId, { pendingIntent: null, assumedSymbol: symbol })
    const msg =
      intent === 'save_decision'
        ? `Décision ${symbol} enregistrée dans le journal${exec.result.deduped ? ' (mise à jour)' : ''}.`
        : intent === 'pin_symbol'
          ? `${symbol} ajouté à la watchlist.`
          : `Position papier ouverte sur ${symbol}${
              typeof exec.result.direction === 'string' ? ` (${exec.result.direction})` : ''
            }.`
    await appendMessage({
      threadId,
      role: 'assistant',
      content: msg,
      intent,
    })
  }

  res.json({
    ok: true,
    status: 'confirmed',
    actionId: done.id,
    intent,
    result: exec.result,
    message:
      intent === 'save_decision'
        ? `Décision ${symbol} enregistrée.`
        : intent === 'pin_symbol'
          ? `${symbol} épinglé.`
          : `Position papier ouverte sur ${symbol}.`,
  })
}
