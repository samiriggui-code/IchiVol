import type { Request, Response } from 'express'
import { search } from '../knowledge/retriever.js'
import { db } from '../db.js'
import { getProvider } from '../providers/index.js'
import { resolveLlmForUser } from '../settings/resolve.js'
import { SOURCES } from '../sources/registry.js'
import { formatDecisionContext, formatLiveContext, formatScreenerRows } from './context.js'
import { intentToMode, planIntent } from './planner.js'
import { buildSystemPrompt, TRADE_IDEA_DISCLAIMER } from './systemPrompt.js'
import {
  appendMessage,
  createThread,
  getThreadForUser,
  loadThreadHistory,
  touchThreadSlots,
} from './threads.js'
import { runReadOnlyToolsForMode } from './tools/index.js'
import type { AgentChatRequest, AgentChatResponse, Citation } from './types.js'
import {
  hasFullClientDecision,
  resolveSymbolTimeframe,
  validateAgentChatRequest,
} from './validate.js'

export async function handleAgentChat(req: Request, res: Response): Promise<void> {
  const validationError = validateAgentChatRequest(req.body)
  if (validationError) {
    res.status(400).json({ error: validationError })
    return
  }

  if (!req.user) {
    res.status(401).json({ error: 'Non authentifié' })
    return
  }

  const body = req.body as AgentChatRequest
  const resolvedHints = resolveSymbolTimeframe(body)

  let thread =
    body.threadId != null
      ? await getThreadForUser(body.threadId, req.user.id)
      : null

  if (body.threadId && !thread) {
    res.status(404).json({ error: 'Thread introuvable' })
    return
  }

  const plan = planIntent({
    question: body.question,
    uiMode: body.mode,
    knownSymbol: resolvedHints.symbol ?? thread?.assumedSymbol ?? undefined,
    knownTimeframe:
      (body.decision?.timeframe ||
        body.timeframe ||
        body.live?.interval ||
        thread?.assumedTimeframe ||
        undefined) ?? '1h',
  })

  const effectiveMode = intentToMode(plan.intent, body.mode)
  const symbol =
    plan.params.symbol ??
    resolvedHints.symbol ??
    thread?.assumedSymbol ??
    undefined
  const timeframe =
    plan.params.timeframe ??
    resolvedHints.timeframe ??
    thread?.assumedTimeframe ??
    '1h'

  if (!thread) {
    thread = await createThread({
      userId: req.user.id,
      assumedSymbol: symbol,
      assumedTimeframe: timeframe,
      lastMode: effectiveMode,
      title: symbol ? `${symbol} · ${timeframe}` : `Chat ${effectiveMode}`,
    })
  }

  const userContent =
    body.question.trim() ||
    (effectiveMode === 'explain_decision'
      ? `Explique la décision sur ${symbol ?? 'ce symbole'}.`
      : effectiveMode === 'explain_signal'
        ? `Explique le signal sur ${symbol ?? 'ce symbole'}.`
        : body.question)

  await appendMessage({
    threadId: thread.id,
    role: 'user',
    content: userContent || '(message vide)',
    mode: effectiveMode,
    intent: plan.intent,
  })

  await touchThreadSlots(thread.id, {
    assumedSymbol: symbol ?? thread.assumedSymbol,
    assumedTimeframe: timeframe,
    pendingIntent: plan.needsConfirm ? plan.intent : null,
    lastMode: effectiveMode,
    title: symbol ? `${symbol} · ${timeframe}` : thread.title,
  })

  if (plan.shortCircuitAnswer) {
    await appendMessage({
      threadId: thread.id,
      role: 'assistant',
      content: plan.shortCircuitAnswer,
      mode: effectiveMode,
      intent: plan.intent,
    })

    let pendingAction: AgentChatResponse['pendingAction']
    if (
      plan.needsConfirm &&
      (plan.intent === 'save_decision' ||
        plan.intent === 'pin_symbol' ||
        plan.intent === 'open_paper_position')
    ) {
      const proposed = await db.agentAction.create({
        data: {
          userId: req.user.id,
          kind: plan.intent,
          status: 'proposed',
          symbol: symbol ?? null,
          timeframe,
          threadId: thread.id,
          payload: { intent: plan.intent, symbol, timeframe },
        },
      })
      pendingAction = {
        intent: plan.intent,
        symbol,
        timeframe,
        actionId: proposed.id,
      }
    }

    const response: AgentChatResponse = {
      answer: plan.shortCircuitAnswer,
      citations: [],
      provider: 'planner',
      model: 'rules-v1',
      intent: plan.intent,
      threadId: thread.id,
      assumedSymbol: symbol ?? null,
      assumedTimeframe: timeframe,
      pendingAction,
    }
    res.json(response)
    return
  }

  const clientDecisionFull = hasFullClientDecision(body)
  const hasClientLive = body.live != null

  const toolRun = await runReadOnlyToolsForMode(
    effectiveMode,
    {
      userId: req.user.id,
      mode: effectiveMode,
      question: body.question,
      symbol,
      timeframe,
    },
    {
      hasClientDecision: clientDecisionFull,
      hasClientLive,
    },
  )

  const decisionPayload =
    clientDecisionFull && body.decision
      ? body.decision
      : toolRun.decisionFromTool

  if (effectiveMode === 'explain_decision' && !decisionPayload) {
    const failedDetail = toolRun.results.find((r) => r.tool === 'get_decision_detail' && !r.ok)
    const err =
      (failedDetail && !failedDetail.ok ? failedDetail.error : undefined) ??
      (symbol
        ? 'Impossible de charger la décision moteur'
        : 'Symbole requis pour expliquer une décision (ex. NEARUSDT)')
    res.status(502).json({ error: err })
    return
  }

  const livePayload = body.live ?? toolRun.liveFromTool

  const liveBlock = formatLiveContext(livePayload)
  const screenerBlock = formatScreenerRows(body.screenerRows)
  const decisionBlock = formatDecisionContext(decisionPayload)

  const searchQuery = [
    body.question,
    livePayload?.symbol,
    decisionPayload?.symbol,
    effectiveMode,
  ]
    .filter(Boolean)
    .join(' ')
  const chunks = search(searchQuery, 4)

  const systemPrompt = buildSystemPrompt({
    mode: effectiveMode,
    liveBlock,
    screenerBlock,
    decisionBlock,
    toolsBlock: toolRun.toolsBlock,
    chunks,
    question: body.question,
  })

  const dbHistory = await loadThreadHistory(thread.id)
  // Historique DB sans le message user qu'on vient d'ajouter (déjà dans userMessage)
  const historyForLlm = dbHistory.slice(0, -1)

  try {
    const resolved = await resolveLlmForUser(req.user.id)
    if (!resolved.apiKey) {
      res.status(400).json({
        error:
          'Aucune clé LLM résolue pour ce provider. Vérifie Settings → Agent LLM (OpenRouter déjà possible via .env).',
      })
      return
    }

    const provider = getProvider({
      provider: body.provider ?? resolved.provider,
      apiKey: resolved.apiKey,
      model: resolved.model,
    })
    const result = await provider.chat([
      { role: 'system', content: systemPrompt },
      ...historyForLlm,
      { role: 'user', content: userContent || body.question },
    ])

    const seenDocs = new Set<string>()
    const citations: Citation[] = chunks
      .filter((c) => (seenDocs.has(c.docId) ? false : seenDocs.add(c.docId)))
      .map((c) => ({ id: c.docId, title: c.title, url: c.url, kind: 'kb' as const }))
    if (liveBlock || screenerBlock || decisionBlock) {
      const marketSource = SOURCES['binance-market-data']
      citations.push({
        id: marketSource.id,
        title: marketSource.title,
        url: marketSource.baseUrl,
        kind: 'live-api',
      })
    }

    await appendMessage({
      threadId: thread.id,
      role: 'assistant',
      content: result.text,
      mode: effectiveMode,
      intent: plan.intent,
      citations,
    })

    const response: AgentChatResponse = {
      answer: result.text,
      disclaimer: effectiveMode === 'trade_idea' ? TRADE_IDEA_DISCLAIMER : undefined,
      citations,
      provider: result.provider,
      model: result.model,
      intent: plan.intent,
      threadId: thread.id,
      assumedSymbol: symbol ?? null,
      assumedTimeframe: timeframe,
    }
    res.json(response)
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Erreur inconnue'
    res.status(502).json({ error: message })
  }
}
