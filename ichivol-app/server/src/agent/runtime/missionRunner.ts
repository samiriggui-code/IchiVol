/**
 * Chantier 2 E1 — missionRunner: bounded wake for claimed tasks.
 *
 * DOES: freshness gate, defer on stale/data_late, skill-loaded Claude wake
 *       into existing Copilot threads, schedule_recheck available as tool.
 * DOES NOT: evaluate_watch_condition DSL (E2), auto-open paper, broker access.
 */
import type { Prisma } from '@prisma/client'
import { resolveLlmForUser } from '../../settings/resolve.js'
import { writeAgentLog } from '../agentLog.js'
import { deferOneBar } from '../candleDue.js'
import { runClaudeAgent, toolTraceMeta } from '../claudeAgent.js'
import { buildAgentSystemPrompt } from '../systemPrompt.js'
import {
  appendMessage,
  createThread,
  getThreadForUser,
  loadThreadHistory,
  touchThreadSlots,
} from '../threads.js'
import { loadSkills, resolveSkillsForTask } from '../skills/loadSkills.js'
import {
  completeTask,
  deferTask,
  type LeasedTask,
} from '../tasks.js'
import { AGENT_LOG_LEVEL } from '../taskConfig.js'
import { checkSymbolFreshness } from './dataQualityGate.js'

/** Hard caps for a single autonomous wake (budget). */
export const MISSION_MAX_ITERATIONS = 4
export const MISSION_MAX_TOKENS = 1024

export type ProcessOutcome =
  | {
      action: 'completed'
      wakeLlm: boolean
      detail: string
    }
  | {
      action: 'deferred'
      reason: string
      dueAt: string
    }
  | {
      action: 'failed'
      error: string
    }

function asPayload(raw: Prisma.JsonValue | null): Record<string, unknown> {
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
    return raw as Record<string, unknown>
  }
  return {}
}

function payloadTimeframe(payload: Record<string, unknown>, fallback = '1h'): string {
  return typeof payload.timeframe === 'string' && payload.timeframe.trim()
    ? payload.timeframe.trim()
    : fallback
}

export type ProcessDeps = {
  checkFreshness?: (
    symbol: string | null | undefined,
    timeframe?: string,
  ) => Promise<import('./dataQualityGate.js').FreshnessVerdict>
}

/**
 * Process one leased task (E1).
 * Condition present → defer (E2 evaluate_watch), do not stub-complete.
 * stale / data_late → no LLM, defer + log.
 */
export async function processClaimedTask(
  task: LeasedTask,
  deps: ProcessDeps = {},
): Promise<ProcessOutcome> {
  const payload = asPayload(task.payload)
  const timeframe = payloadTimeframe(payload)
  const hasCondition = task.condition != null
  const checkFreshness = deps.checkFreshness ?? checkSymbolFreshness

  // --- Freshness gate (audit: stale/data_late → no LLM wake) ---
  if (task.symbol) {
    const fresh = await checkFreshness(task.symbol, timeframe)
    if (!fresh.ok && (fresh.reason === 'stale' || fresh.reason === 'data_late')) {
      const dueAt = deferOneBar(timeframe)
      await deferTask(task.id, dueAt, fresh.reason)
      await writeAgentLog({
        agentId: task.agentId,
        level: AGENT_LOG_LEVEL.prudence,
        source: 'runtime.missionRunner',
        message: `No LLM wake — ${fresh.reason}; rescheduled ${task.symbol}`,
        taskId: task.id,
        meta: {
          reason: fresh.reason,
          dueAt: dueAt.toISOString(),
          stale: fresh.stale,
          dataLate: fresh.dataLate,
          wakeLlm: false,
        },
      })
      return { action: 'deferred', reason: fresh.reason, dueAt: dueAt.toISOString() }
    }
    if (!fresh.ok && fresh.reason === 'engine_error') {
      // Engine blip: defer, don't burn LLM budget on empty context.
      const dueAt = deferOneBar(timeframe)
      await deferTask(task.id, dueAt, `engine_error:${fresh.detail ?? ''}`)
      await writeAgentLog({
        agentId: task.agentId,
        level: AGENT_LOG_LEVEL.prudence,
        source: 'runtime.missionRunner',
        message: `No LLM wake — engine_error; rescheduled ${task.symbol}`,
        taskId: task.id,
        meta: { reason: 'engine_error', detail: fresh.detail, dueAt: dueAt.toISOString() },
      })
      return { action: 'deferred', reason: 'engine_error', dueAt: dueAt.toISOString() }
    }
  }

  // --- Condition DSL → E2 (do not stub-complete) ---
  if (hasCondition) {
    const dueAt = deferOneBar(timeframe)
    await deferTask(task.id, dueAt, 'condition_deferred_e2')
    await writeAgentLog({
      agentId: task.agentId,
      level: AGENT_LOG_LEVEL.prudence,
      source: 'runtime.missionRunner',
      message: `Condition present — evaluate_watch deferred to E2; no LLM (${task.kind} ${task.symbol ?? ''})`,
      taskId: task.id,
      meta: { dueAt: dueAt.toISOString(), wakeLlm: false },
    })
    return { action: 'deferred', reason: 'condition_deferred_e2', dueAt: dueAt.toISOString() }
  }

  // --- Wake path (mission / recheck without condition) ---
  const userId = typeof payload.userId === 'string' ? payload.userId : null
  if (!userId) {
    // No user context → cannot resolve LLM keys; complete without wake.
    await writeAgentLog({
      agentId: task.agentId,
      level: AGENT_LOG_LEVEL.passe,
      source: 'runtime.missionRunner',
      message: `Completed ${task.kind} without LLM (no userId in payload)`,
      taskId: task.id,
      meta: { wakeLlm: false },
    })
    await completeTask(task.id, {
      phase: 'E1',
      wakeLlm: false,
      reason: 'no_user_id',
      processedAt: new Date().toISOString(),
    })
    return { action: 'completed', wakeLlm: false, detail: 'no_user_id' }
  }

  const woke = await wakeMissionLlm(task, payload, timeframe, userId)
  return woke
}

async function wakeMissionLlm(
  task: LeasedTask,
  payload: Record<string, unknown>,
  timeframe: string,
  userId: string,
): Promise<ProcessOutcome> {
  let resolved: Awaited<ReturnType<typeof resolveLlmForUser>>
  try {
    // Tool loop talks to Anthropic Messages API — prefer anthropic key even if
    // the user's active provider is openrouter/openai.
    resolved = await resolveLlmForUser(userId, 'anthropic')
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    await writeAgentLog({
      agentId: task.agentId,
      level: AGENT_LOG_LEVEL.prudence,
      source: 'runtime.missionRunner',
      message: `LLM resolve failed — completed without wake: ${msg}`,
      taskId: task.id,
    })
    await completeTask(task.id, {
      phase: 'E1',
      wakeLlm: false,
      reason: 'llm_resolve_failed',
      error: msg,
    })
    return { action: 'completed', wakeLlm: false, detail: 'llm_resolve_failed' }
  }

  if (resolved.provider !== 'anthropic' || !resolved.apiKey) {
    await writeAgentLog({
      agentId: task.agentId,
      level: AGENT_LOG_LEVEL.prudence,
      source: 'runtime.missionRunner',
      message: `Wake skipped — need Anthropic key (got ${resolved.provider}, key=${Boolean(resolved.apiKey)})`,
      taskId: task.id,
    })
    await completeTask(task.id, {
      phase: 'E1',
      wakeLlm: false,
      reason: 'anthropic_required_for_tools',
    })
    return { action: 'completed', wakeLlm: false, detail: 'anthropic_required' }
  }

  // Eve chat = Copilot thread (reuse or create).
  let threadId = typeof payload.threadId === 'string' ? payload.threadId : null
  if (threadId) {
    const owned = await getThreadForUser(threadId, userId)
    if (!owned) threadId = null
  }
  if (!threadId) {
    const thread = await createThread({
      userId,
      assumedSymbol: task.symbol ?? undefined,
      assumedTimeframe: timeframe,
      lastMode: 'explain_decision',
      title: task.symbol
        ? `Mission · ${task.symbol} · ${timeframe}`
        : `Mission · ${task.kind}`,
    })
    threadId = thread.id
  }

  const skillNames = resolveSkillsForTask(task.kind, payload)
  const { block: skillsBlock, names: loadedSkills } = loadSkills(skillNames)

  let system = buildAgentSystemPrompt({
    mode: 'explain_decision',
    symbol: task.symbol ?? undefined,
    timeframe,
    liveBlock: null,
    screenerBlock: null,
    decisionBlock: null,
  })
  system +=
    '\n\nContexte runtime E1 : tu es réveillé par une tâche agent (recheck/mission). ' +
    'Paper only. Confirmation humaine par défaut — jamais d’auto-open. ' +
    'Utilise schedule_recheck si un suivi ultérieur est nécessaire.'
  if (skillsBlock) system += `\n\n${skillsBlock}`

  const reason =
    typeof payload.reason === 'string' ? payload.reason : `Recheck ${task.kind}`
  const question =
    `[Wake agent ${task.kind}] Symbole ${task.symbol ?? '—'} (${timeframe}). ` +
    `Raison : ${reason}. Interroge le moteur, explique le verdict, ` +
    `et schedule_recheck si tu dois revenir après la prochaine bougie.`

  await appendMessage({
    threadId,
    role: 'user',
    content: question,
    mode: 'explain_decision',
    intent: 'mission_wake',
  })
  await touchThreadSlots(threadId, {
    assumedSymbol: task.symbol,
    assumedTimeframe: timeframe,
    lastMode: 'explain_decision',
  })

  try {
    const out = await runClaudeAgent({
      apiKey: resolved.apiKey,
      model: resolved.model,
      system,
      history: (await loadThreadHistory(threadId)).slice(0, -1),
      question,
      // Budget: claudeAgent uses tool loop defaults; we pass via monkey? 
      // runClaudeAgent doesn't expose maxIterations — extend below if needed.
      toolContext: {
        agentId: task.agentId,
        userId,
        threadId,
        maxIterations: MISSION_MAX_ITERATIONS,
        maxTokens: MISSION_MAX_TOKENS,
      },
    })

    await appendMessage({
      threadId,
      role: 'assistant',
      content: out.answer,
      mode: 'explain_decision',
      intent: 'mission_wake',
      citations: out.citations,
      meta: toolTraceMeta(out),
    })

    await writeAgentLog({
      agentId: task.agentId,
      level: AGENT_LOG_LEVEL.passe,
      source: 'runtime.missionRunner',
      message: `LLM wake OK — ${task.kind} ${task.symbol ?? ''} → thread ${threadId}`,
      taskId: task.id,
      meta: {
        wakeLlm: true,
        threadId,
        skills: loadedSkills,
        toolCalls: out.toolCalls.length,
        model: out.model,
        promptVersion: out.promptVersion,
        usage: out.usageTotal ?? null,
      },
    })

    await completeTask(task.id, {
      phase: 'E1',
      wakeLlm: true,
      threadId,
      skills: loadedSkills,
      toolCalls: out.toolCalls.length,
      processedAt: new Date().toISOString(),
    })
    return { action: 'completed', wakeLlm: true, detail: threadId }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    await writeAgentLog({
      agentId: task.agentId,
      level: AGENT_LOG_LEVEL.refuse,
      source: 'runtime.missionRunner',
      message: `LLM wake failed: ${msg}`,
      taskId: task.id,
    })
    // Defer rather than fail hard — retry next bar within attempt budget.
    const dueAt = deferOneBar(timeframe)
    await deferTask(task.id, dueAt, `wake_failed:${msg}`)
    return { action: 'deferred', reason: `wake_failed:${msg}`, dueAt: dueAt.toISOString() }
  }
}
