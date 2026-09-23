/**
 * Boucle d'outils Claude (Anthropic tool use) sur le canal agent du moteur.
 *
 * Claude choisit lui-même quelles commandes moteur appeler. Lecture seule par
 * défaut ; T2b autorise aussi les outils chart write (draw_* / delete_chart_object).
 * Module pur : `fetchImpl` et `execute` sont injectés pour tester sans réseau.
 */

import type { EngineAgentToolSpec } from './engineAgentChannel.js'

export interface AnthropicTool {
  name: string
  description: string
  input_schema: {
    type: 'object'
    properties: Record<string, Record<string, unknown>>
    required: string[]
  }
}

export interface ToolExecResult {
  ok: boolean
  content: string
}

export type ToolExecutor = (name: string, input: Record<string, unknown>) => Promise<ToolExecResult>

export interface ToolCallTrace {
  name: string
  input: Record<string, unknown>
  ok: boolean
  ms: number
}

export interface ClaudeMessage {
  role: 'user' | 'assistant'
  content: string | Array<Record<string, unknown>>
}

export const SEARCH_KB_TOOL: AnthropicTool = {
  name: 'search_knowledge',
  description:
    "Cherche dans le référentiel pédagogique (Binance Academy : Ichimoku, volume, stratégies). À utiliser pour la THÉORIE uniquement, jamais pour un chiffre de marché.",
  input_schema: {
    type: 'object',
    properties: { query: { type: 'string', description: 'Question ou mots-clés' } },
    required: ['query'],
  },
}

/** Chart-overlay writes (T2b). Paper / brokerage writes stay excluded. */
export const CHART_WRITE_TOOL_NAMES = new Set([
  'draw_horizontal_line',
  'draw_trend_line',
  'draw_ray',
  'draw_zone',
  'draw_rectangle',
  'draw_channel',
  'draw_marker',
  'draw_text',
  'draw_entry',
  'draw_stop',
  'draw_target',
  'delete_chart_object',
])

/** Tronque un résultat d'outil : garde le contexte (et le coût) sous contrôle. */
export const MAX_TOOL_RESULT_CHARS = 12_000

function jsonSchemaFor(argSpec: string): Record<string, unknown> {
  const spec = argSpec.trim()
  const head = spec.split(/[,\s]/)[0]
  if (head === 'int') return { type: 'integer', description: spec }
  if (head === 'float') return { type: 'number', description: spec }
  if (head === 'bool') return { type: 'boolean', description: spec }
  if (head.startsWith('list[int]')) return { type: 'array', items: { type: 'integer' }, description: spec }
  // ChartObject points: list[{time,price}] — must be objects, not strings.
  if (/list\[\{.*time.*price/i.test(spec) || /list\[\{time,price\}\]/i.test(spec)) {
    return {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          time: { type: 'integer', description: 'unix seconds' },
          price: { type: 'number' },
        },
        required: ['time', 'price'],
      },
      description: spec,
    }
  }
  if (head.startsWith('list')) return { type: 'array', items: { type: 'string' }, description: spec }
  if (head === 'object') return { type: 'object', description: spec }
  return { type: 'string', description: spec }
}

export function engineSpecToAnthropicTool(spec: EngineAgentToolSpec): AnthropicTool {
  const properties: Record<string, Record<string, unknown>> = {}
  const required: string[] = []
  for (const [name, argSpec] of Object.entries(spec.args ?? {})) {
    properties[name] = jsonSchemaFor(argSpec)
    if (/requis|required/i.test(argSpec)) required.push(name)
  }
  return {
    name: spec.name,
    description: spec.description,
    input_schema: { type: 'object', properties, required },
  }
}

function isExposedToClaude(spec: EngineAgentToolSpec): boolean {
  if (spec.name === 'list_tools') return false
  if (spec.read_only) return true
  return CHART_WRITE_TOOL_NAMES.has(spec.name)
}

/** Outils lecture seule + draw_* et delete_chart_object (T2b). Pas de paper write. */
export function toolsFromEngineManifest(specs: EngineAgentToolSpec[]): AnthropicTool[] {
  return specs.filter(isExposedToClaude).map(engineSpecToAnthropicTool)
}

export function truncateToolResult(text: string): string {
  if (text.length <= MAX_TOOL_RESULT_CHARS) return text
  return `${text.slice(0, MAX_TOOL_RESULT_CHARS)}\n…[tronqué : ${text.length - MAX_TOOL_RESULT_CHARS} caractères omis]`
}

interface AnthropicResponse {
  content: Array<{ type: string; text?: string; id?: string; name?: string; input?: unknown }>
  stop_reason: string
  model: string
}

/** Événements poussés au client pendant que Claude travaille. */
export type AgentStreamEvent =
  | { type: 'text'; delta: string }
  | { type: 'tool_start'; name: string; input: Record<string, unknown> }
  | { type: 'tool_end'; name: string; ok: boolean; ms: number }

interface StreamBlock {
  type: string
  text: string
  id?: string
  name?: string
  json: string
}

/**
 * Lit un flux SSE Anthropic (`stream: true`) et le reconstitue en réponse
 * complète identique à la version non-streamée ; le texte est transmis au fil
 * de l'eau via `onText`.
 */
export async function readAnthropicStream(
  res: Response,
  onText?: (delta: string) => void,
): Promise<AnthropicResponse> {
  if (!res.body) throw new Error('Anthropic: flux vide')
  const blocks = new Map<number, StreamBlock>()
  let model = ''
  let stopReason = ''

  const handle = (raw: string) => {
    const dataLine = raw.split('\n').find((l) => l.startsWith('data:'))
    if (!dataLine) return
    const evt = JSON.parse(dataLine.slice(5).trim()) as Record<string, any>
    switch (evt.type) {
      case 'message_start':
        model = evt.message?.model ?? model
        break
      case 'content_block_start':
        blocks.set(evt.index, {
          type: evt.content_block.type,
          text: evt.content_block.text ?? '',
          id: evt.content_block.id,
          name: evt.content_block.name,
          json: '',
        })
        break
      case 'content_block_delta': {
        const block = blocks.get(evt.index)
        if (!block) break
        if (evt.delta.type === 'text_delta') {
          block.text += evt.delta.text
          onText?.(evt.delta.text)
        } else if (evt.delta.type === 'input_json_delta') {
          block.json += evt.delta.partial_json
        }
        break
      }
      case 'message_delta':
        stopReason = evt.delta?.stop_reason ?? stopReason
        break
      case 'error':
        throw new Error(`Anthropic stream: ${evt.error?.message ?? 'erreur inconnue'}`)
    }
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let sep: number
    while ((sep = buffer.indexOf('\n\n')) !== -1) {
      handle(buffer.slice(0, sep))
      buffer = buffer.slice(sep + 2)
    }
  }
  if (buffer.trim()) handle(buffer)

  const content = [...blocks.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([, b]) =>
      b.type === 'tool_use'
        ? { type: 'tool_use', id: b.id, name: b.name, input: b.json ? JSON.parse(b.json) : {} }
        : { type: b.type, text: b.text },
    )
  return { content, stop_reason: stopReason, model }
}

export interface ToolLoopOptions {
  apiKey: string
  model: string
  system: string
  messages: ClaudeMessage[]
  tools: AnthropicTool[]
  execute: ToolExecutor
  maxIterations?: number
  maxTokens?: number
  fetchImpl?: typeof fetch
  /** Si fourni, la réponse est streamée et chaque événement est transmis ici. */
  onEvent?: (event: AgentStreamEvent) => void
  signal?: AbortSignal
}

export interface ToolLoopResult {
  text: string
  model: string
  toolCalls: ToolCallTrace[]
  iterations: number
}

export async function runClaudeToolLoop(opts: ToolLoopOptions): Promise<ToolLoopResult> {
  const doFetch = opts.fetchImpl ?? fetch
  const maxIterations = opts.maxIterations ?? 6
  const allowed = new Set(opts.tools.map((t) => t.name))
  const messages: ClaudeMessage[] = [...opts.messages]
  const toolCalls: ToolCallTrace[] = []
  let model = opts.model

  const call = async (forceText: boolean): Promise<AnthropicResponse> => {
    const res = await doFetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': opts.apiKey,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: opts.model,
        max_tokens: opts.maxTokens ?? 2048,
        system: [{ type: 'text', text: opts.system, cache_control: { type: 'ephemeral' } }],
        tools: opts.tools,
        ...(forceText ? { tool_choice: { type: 'none' } } : {}),
        ...(opts.onEvent ? { stream: true } : {}),
        messages,
      }),
      signal: opts.signal,
    })
    if (!res.ok) throw new Error(`Anthropic ${res.status}: ${await res.text()}`)
    if (opts.onEvent) {
      const emit = opts.onEvent
      return readAnthropicStream(res, (delta) => emit({ type: 'text', delta }))
    }
    return (await res.json()) as AnthropicResponse
  }

  for (let iteration = 1; iteration <= maxIterations + 1; iteration++) {
    // Dernier tour : on interdit les outils pour obtenir une réponse rédigée.
    const forceText = iteration === maxIterations + 1
    const data = await call(forceText)
    model = data.model || model

    const uses = data.content.filter((b) => b.type === 'tool_use')
    if (data.stop_reason !== 'tool_use' || uses.length === 0 || forceText) {
      const text = data.content
        .filter((b) => b.type === 'text' && b.text)
        .map((b) => b.text)
        .join('\n')
      return { text, model, toolCalls, iterations: iteration }
    }

    messages.push({ role: 'assistant', content: data.content as Array<Record<string, unknown>> })

    const results = await Promise.all(
      uses.map(async (use) => {
        const name = String(use.name)
        const input = (use.input && typeof use.input === 'object' ? use.input : {}) as Record<
          string,
          unknown
        >
        const started = Date.now()
        opts.onEvent?.({ type: 'tool_start', name, input })
        let exec: ToolExecResult
        if (!allowed.has(name)) {
          exec = { ok: false, content: `outil non autorisé: ${name}` }
        } else {
          try {
            exec = await opts.execute(name, input)
          } catch (e) {
            exec = { ok: false, content: e instanceof Error ? e.message : 'erreur outil' }
          }
        }
        const ms = Date.now() - started
        toolCalls.push({ name, input, ok: exec.ok, ms })
        opts.onEvent?.({ type: 'tool_end', name, ok: exec.ok, ms })
        return {
          type: 'tool_result',
          tool_use_id: use.id,
          content: truncateToolResult(exec.content),
          ...(exec.ok ? {} : { is_error: true }),
        }
      }),
    )
    messages.push({ role: 'user', content: results })
  }

  return { text: '', model, toolCalls, iterations: maxIterations + 1 }
}
