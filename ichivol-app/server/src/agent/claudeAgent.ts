import { search } from '../knowledge/retriever.js'
import type { ScoredChunk } from '../knowledge/types.js'
import {
  SEARCH_KB_TOOL,
  type AgentStreamEvent,
  runClaudeToolLoop,
  toolsFromEngineManifest,
  type AnthropicTool,
  type ClaudeMessage,
  type ToolCallTrace,
  type ToolExecutor,
} from './claudeTools.js'
import { engineAgentCommand, engineAgentTools } from './engineAgentChannel.js'
import {
  executeScheduleRecheck,
  SCHEDULE_RECHECK_TOOL,
} from './tools/scheduleRecheck.js'
import type { Citation } from './types.js'

const MANIFEST_TTL_MS = 5 * 60_000
let manifestCache: { at: number; tools: AnthropicTool[] } | null = null

/** Manifeste moteur → outils Claude (cache 5 min : le moteur change rarement). */
async function loadEngineTools(): Promise<AnthropicTool[]> {
  if (manifestCache && Date.now() - manifestCache.at < MANIFEST_TTL_MS) return manifestCache.tools
  const manifest = await engineAgentTools()
  if (!manifest.ok) throw new Error(`Moteur injoignable (${manifest.error})`)
  const tools = toolsFromEngineManifest(manifest.tools)
  manifestCache = { at: Date.now(), tools }
  return tools
}

export interface ClaudeAgentToolContext {
  agentId?: string
  userId?: string | null
  threadId?: string | null
  maxIterations?: number
  maxTokens?: number
}

export interface ClaudeAgentInput {
  apiKey: string
  model: string
  system: string
  history: ClaudeMessage[]
  question: string
  onEvent?: (event: AgentStreamEvent) => void
  signal?: AbortSignal
  /** E1 — schedule_recheck context + mission budget caps. */
  toolContext?: ClaudeAgentToolContext
}

export interface ClaudeAgentOutput {
  answer: string
  model: string
  toolCalls: ToolCallTrace[]
  citations: Citation[]
}

export async function runClaudeAgent(input: ClaudeAgentInput): Promise<ClaudeAgentOutput> {
  const engineTools = await loadEngineTools()
  const kbChunks: ScoredChunk[] = []
  const ctx = input.toolContext

  const execute: ToolExecutor = async (name, args) => {
    if (name === SEARCH_KB_TOOL.name) {
      const chunks = search(String(args.query ?? ''), 4)
      kbChunks.push(...chunks)
      return {
        ok: true,
        content: JSON.stringify(
          chunks.map((c) => ({ titre: c.title, url: c.url, extrait: c.text })),
        ),
      }
    }
    if (name === SCHEDULE_RECHECK_TOOL.name) {
      // Server-side task write — LLM never touches Prisma/broker directly.
      return executeScheduleRecheck(args, {
        agentId: ctx?.agentId,
        userId: ctx?.userId,
        threadId: ctx?.threadId,
      })
    }
    const res = await engineAgentCommand({ cmd: name, args })
    return res.ok
      ? { ok: true, content: JSON.stringify(res.data) }
      : { ok: false, content: res.error }
  }

  const result = await runClaudeToolLoop({
    apiKey: input.apiKey,
    model: input.model,
    system: input.system,
    messages: [...input.history, { role: 'user', content: input.question }],
    tools: [...engineTools, SEARCH_KB_TOOL, SCHEDULE_RECHECK_TOOL],
    execute,
    onEvent: input.onEvent,
    signal: input.signal,
    maxIterations: ctx?.maxIterations,
    maxTokens: ctx?.maxTokens,
  })

  const seen = new Set<string>()
  const citations: Citation[] = kbChunks
    .filter((c) => (seen.has(c.docId) ? false : seen.add(c.docId)))
    .map((c) => ({ id: c.docId, title: c.title, url: c.url, kind: 'kb' as const }))

  return {
    answer: result.text || "Je n'ai pas pu formuler de réponse. Reformule ou précise le symbole.",
    model: result.model,
    toolCalls: result.toolCalls,
    citations,
  }
}
