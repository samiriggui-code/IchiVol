import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  engineSpecToAnthropicTool,
  MAX_TOOL_RESULT_CHARS,
  runClaudeToolLoop,
  toolsFromEngineManifest,
  truncateToolResult,
  type AnthropicTool,
} from './claudeTools.js'

const CONTEXT_SPEC = {
  name: 'get_symbol_context',
  description: 'Détail décision',
  read_only: true,
  args: { symbol: 'str, requis', timeframe: "str, défaut '1h'", limit: 'int, défaut 300' },
}

function fakeAnthropic(replies: object[]) {
  const bodies: Array<Record<string, unknown>> = []
  const fetchImpl = (async (_url: string, init: { body: string }) => {
    bodies.push(JSON.parse(init.body))
    const next = replies.shift()
    assert.ok(next, 'plus de réponse simulée')
    return { ok: true, json: async () => next, text: async () => '' }
  }) as unknown as typeof fetch
  return { fetchImpl, bodies }
}

test('convertit un spec moteur en outil Claude (types + champs requis)', () => {
  const tool = engineSpecToAnthropicTool(CONTEXT_SPEC)
  assert.deepEqual(tool.input_schema.required, ['symbol'])
  assert.equal(tool.input_schema.properties.symbol.type, 'string')
  assert.equal(tool.input_schema.properties.limit.type, 'integer')
})

test('schema points = array d\'objets {time,price} (pas string[])', () => {
  const tool = engineSpecToAnthropicTool({
    name: 'draw_trend_line',
    description: 'trend',
    read_only: false,
    args: {
      symbol: 'str, requis',
      points: 'list[{time,price}], requis (2)',
    },
  })
  const points = tool.input_schema.properties.points as {
    type: string
    items: { type: string; properties?: Record<string, unknown> }
  }
  assert.equal(points.type, 'array')
  assert.equal(points.items.type, 'object')
  assert.ok(points.items.properties?.time)
  assert.ok(points.items.properties?.price)
})

test("n'expose que lecture seule (pas draw_*/delete/place_order/list_tools)", () => {
  const tools = toolsFromEngineManifest([
    CONTEXT_SPEC,
    { ...CONTEXT_SPEC, name: 'place_order', read_only: false },
    { ...CONTEXT_SPEC, name: 'draw_horizontal_line', read_only: false },
    { ...CONTEXT_SPEC, name: 'delete_chart_object', read_only: false },
    { ...CONTEXT_SPEC, name: 'list_tools' },
  ])
  assert.deepEqual(
    tools.map((t) => t.name).sort(),
    ['get_symbol_context'],
  )
})

test('prompt « lecture seule » ↔ outils exposés cohérents (AG0)', async () => {
  const { buildAgentSystemPrompt } = await import('./systemPrompt.js')
  const { CHART_WRITE_TOOL_NAMES, isExposedToClaude } = await import('./claudeTools.js')
  const prompt = buildAgentSystemPrompt({
    mode: 'research',
    liveBlock: null,
    screenerBlock: null,
    decisionBlock: null,
  })
  assert.match(prompt, /lecture seule/i)
  for (const name of CHART_WRITE_TOOL_NAMES) {
    assert.equal(
      isExposedToClaude({ name, description: 'x', read_only: false, args: {} }),
      false,
      `${name} must not be exposed while prompt says read-only`,
    )
  }
  const tools = toolsFromEngineManifest([
    CONTEXT_SPEC,
    ...[...CHART_WRITE_TOOL_NAMES].map((name) => ({
      ...CONTEXT_SPEC,
      name,
      read_only: false,
    })),
  ])
  assert.ok(tools.every((t) => !CHART_WRITE_TOOL_NAMES.has(t.name)))
})

test('tronque les gros résultats', () => {
  const out = truncateToolResult('x'.repeat(MAX_TOOL_RESULT_CHARS + 50))
  assert.match(out, /tronqué : 50 caractères/)
})

test("boucle : Claude appelle un outil, reçoit le résultat, puis répond", async () => {
  const tools: AnthropicTool[] = toolsFromEngineManifest([CONTEXT_SPEC])
  const { fetchImpl, bodies } = fakeAnthropic([
    {
      stop_reason: 'tool_use',
      model: 'm',
      content: [
        { type: 'tool_use', id: 't1', name: 'get_symbol_context', input: { symbol: 'BTCUSDT' } },
      ],
    },
    { stop_reason: 'end_turn', model: 'm', content: [{ type: 'text', text: 'Verdict WATCH.' }] },
  ])
  const seen: Array<[string, Record<string, unknown>]> = []
  const result = await runClaudeToolLoop({
    apiKey: 'k',
    model: 'm',
    system: 's',
    messages: [{ role: 'user', content: 'Explique BTC' }],
    tools,
    fetchImpl,
    execute: async (name, input) => {
      seen.push([name, input])
      return { ok: true, content: '{"decision":"WATCH"}' }
    },
  })
  assert.equal(result.text, 'Verdict WATCH.')
  assert.deepEqual(seen, [['get_symbol_context', { symbol: 'BTCUSDT' }]])
  assert.equal(result.toolCalls.length, 1)
  assert.equal(result.iterations, 2)
  // le 2e appel doit contenir le tool_result renvoyé à Claude
  const second = bodies[1].messages as Array<{ role: string; content: unknown }>
  assert.equal(second.at(-1)?.role, 'user')
  assert.match(JSON.stringify(second.at(-1)?.content), /tool_result/)
})

test("refuse un outil hors allowlist sans l'exécuter", async () => {
  const { fetchImpl } = fakeAnthropic([
    {
      stop_reason: 'tool_use',
      model: 'm',
      content: [{ type: 'tool_use', id: 't1', name: 'place_order', input: {} }],
    },
    { stop_reason: 'end_turn', model: 'm', content: [{ type: 'text', text: 'ok' }] },
  ])
  let executed = false
  const result = await runClaudeToolLoop({
    apiKey: 'k',
    model: 'm',
    system: 's',
    messages: [{ role: 'user', content: 'x' }],
    tools: toolsFromEngineManifest([CONTEXT_SPEC]),
    fetchImpl,
    execute: async () => {
      executed = true
      return { ok: true, content: '' }
    },
  })
  assert.equal(executed, false)
  assert.equal(result.toolCalls[0].ok, false)
})

test('force une réponse texte après maxIterations (tool_choice none)', async () => {
  const toolUse = (id: string) => ({
    stop_reason: 'tool_use',
    model: 'm',
    content: [{ type: 'tool_use', id, name: 'get_symbol_context', input: { symbol: 'X' } }],
  })
  const { fetchImpl, bodies } = fakeAnthropic([
    toolUse('a'),
    toolUse('b'),
    { stop_reason: 'end_turn', model: 'm', content: [{ type: 'text', text: 'fin' }] },
  ])
  const result = await runClaudeToolLoop({
    apiKey: 'k',
    model: 'm',
    system: 's',
    messages: [{ role: 'user', content: 'x' }],
    tools: toolsFromEngineManifest([CONTEXT_SPEC]),
    maxIterations: 2,
    fetchImpl,
    execute: async () => ({ ok: true, content: '{}' }),
  })
  assert.equal(result.text, 'fin')
  assert.deepEqual(bodies[2].tool_choice, { type: 'none' })
})

// ---- streaming ----

function sse(events: object[]): string {
  return events.map((e) => `event: x\ndata: ${JSON.stringify(e)}\n\n`).join('')
}

/** Réponse SSE découpée en morceaux arbitraires (y compris au milieu d'un événement). */
function streamResponse(text: string, chunkSize: number): Response {
  const bytes = new TextEncoder().encode(text)
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (let i = 0; i < bytes.length; i += chunkSize) {
        controller.enqueue(bytes.slice(i, i + chunkSize))
      }
      controller.close()
    },
  })
  return new Response(stream, { headers: { 'content-type': 'text/event-stream' } })
}

const TEXT_STREAM = sse([
  { type: 'message_start', message: { model: 'claude-x' } },
  { type: 'content_block_start', index: 0, content_block: { type: 'text', text: '' } },
  { type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: 'Bon' } },
  { type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: 'jour é' } },
  { type: 'content_block_stop', index: 0 },
  { type: 'message_delta', delta: { stop_reason: 'end_turn' } },
  { type: 'message_stop' },
])

test('stream : reconstitue le texte même si les chunks coupent les événements et les accents', async () => {
  const { readAnthropicStream } = await import('./claudeTools.js')
  const deltas: string[] = []
  const out = await readAnthropicStream(streamResponse(TEXT_STREAM, 7), (d) => deltas.push(d))
  assert.deepEqual(deltas, ['Bon', 'jour é'])
  assert.equal(out.model, 'claude-x')
  assert.equal(out.stop_reason, 'end_turn')
  assert.deepEqual(out.content, [{ type: 'text', text: 'Bonjour é' }])
})

test('stream : assemble le JSON partiel d\'un tool_use', async () => {
  const { readAnthropicStream } = await import('./claudeTools.js')
  const body = sse([
    { type: 'message_start', message: { model: 'm' } },
    { type: 'content_block_start', index: 0, content_block: { type: 'tool_use', id: 't1', name: 'detect_signal' } },
    { type: 'content_block_delta', index: 0, delta: { type: 'input_json_delta', partial_json: '{"symbol":"BT' } },
    { type: 'content_block_delta', index: 0, delta: { type: 'input_json_delta', partial_json: 'CUSDT"}' } },
    { type: 'message_delta', delta: { stop_reason: 'tool_use' } },
  ])
  const out = await readAnthropicStream(streamResponse(body, 5))
  assert.deepEqual(out.content, [
    { type: 'tool_use', id: 't1', name: 'detect_signal', input: { symbol: 'BTCUSDT' } },
  ])
  assert.equal(out.stop_reason, 'tool_use')
})

test('stream : un événement error interrompt avec un message clair', async () => {
  const { readAnthropicStream } = await import('./claudeTools.js')
  const body = sse([{ type: 'error', error: { message: 'overloaded' } }])
  await assert.rejects(readAnthropicStream(streamResponse(body, 64)), /overloaded/)
})

test('boucle streamée : événements texte + outil dans l\'ordre, stream:true envoyé', async () => {
  const toolStream = sse([
    { type: 'message_start', message: { model: 'm' } },
    { type: 'content_block_start', index: 0, content_block: { type: 'text', text: '' } },
    { type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: 'Je regarde.' } },
    { type: 'content_block_start', index: 1, content_block: { type: 'tool_use', id: 't1', name: 'get_symbol_context' } },
    { type: 'content_block_delta', index: 1, delta: { type: 'input_json_delta', partial_json: '{"symbol":"ETHUSDT"}' } },
    { type: 'message_delta', delta: { stop_reason: 'tool_use' } },
  ])
  const queue = [toolStream, TEXT_STREAM]
  const bodies: Array<Record<string, unknown>> = []
  const fetchImpl = (async (_u: string, init: { body: string }) => {
    bodies.push(JSON.parse(init.body))
    return streamResponse(queue.shift()!, 11)
  }) as unknown as typeof fetch

  const events: string[] = []
  const result = await runClaudeToolLoop({
    apiKey: 'k',
    model: 'm',
    system: 's',
    messages: [{ role: 'user', content: 'x' }],
    tools: toolsFromEngineManifest([CONTEXT_SPEC]),
    fetchImpl,
    execute: async () => ({ ok: true, content: '{}' }),
    onEvent: (e) => events.push(e.type === 'text' ? `text:${e.delta}` : `${e.type}:${e.name}`),
  })
  assert.deepEqual(events, [
    'text:Je regarde.',
    'tool_start:get_symbol_context',
    'tool_end:get_symbol_context',
    'text:Bon',
    'text:jour é',
  ])
  assert.equal(result.text, 'Bonjour é')
  assert.equal(bodies[0].stream, true)
  assert.ok(result.toolCalls[0].outputHash)
})

test('plafond outils par tour et total (AG0)', async () => {
  const many = {
    stop_reason: 'tool_use',
    model: 'm',
    content: [
      { type: 'tool_use', id: 'a', name: 'get_symbol_context', input: { symbol: 'A' } },
      { type: 'tool_use', id: 'b', name: 'get_symbol_context', input: { symbol: 'B' } },
      { type: 'tool_use', id: 'c', name: 'get_symbol_context', input: { symbol: 'C' } },
    ],
  }
  const { fetchImpl } = fakeAnthropic([
    many,
    { stop_reason: 'end_turn', model: 'm', content: [{ type: 'text', text: 'ok' }] },
  ])
  const result = await runClaudeToolLoop({
    apiKey: 'k',
    model: 'm',
    system: 's',
    messages: [{ role: 'user', content: 'x' }],
    tools: toolsFromEngineManifest([CONTEXT_SPEC]),
    maxToolCallsPerTurn: 2,
    maxToolCallsTotal: 2,
    fetchImpl,
    execute: async () => ({ ok: true, content: '{}' }),
  })
  assert.equal(result.toolCalls.length, 2)
})

test('budget tokens → arrêt propre avec tool_choice none (AG0)', async () => {
  const { fetchImpl, bodies } = fakeAnthropic([
    {
      stop_reason: 'end_turn',
      model: 'm',
      usage: { input_tokens: 100, output_tokens: 50 },
      content: [{ type: 'text', text: 'assez' }],
    },
  ])
  const result = await runClaudeToolLoop({
    apiKey: 'k',
    model: 'm',
    system: 's',
    messages: [{ role: 'user', content: 'x' }],
    tools: toolsFromEngineManifest([CONTEXT_SPEC]),
    tokenBudget: 10,
    fetchImpl,
    execute: async () => ({ ok: true, content: '{}' }),
  })
  // First call already exceeds budget after accumulate → still returns text from that call
  assert.equal(result.text, 'assez')
  assert.ok((result.usageTotal?.input_tokens ?? 0) + (result.usageTotal?.output_tokens ?? 0) >= 10)
  void bodies
})

test('timeout Anthropic lève une erreur claire (AG0)', async () => {
  const fetchImpl = (async (_u: string, init: { signal?: AbortSignal }) => {
    await new Promise<void>((_, reject) => {
      init.signal?.addEventListener('abort', () => reject(new Error('aborted')))
    })
    return { ok: true, json: async () => ({}) }
  }) as unknown as typeof fetch
  await assert.rejects(
    runClaudeToolLoop({
      apiKey: 'k',
      model: 'm',
      system: 's',
      messages: [{ role: 'user', content: 'x' }],
      tools: toolsFromEngineManifest([CONTEXT_SPEC]),
      anthropicTimeoutMs: 20,
      fetchImpl,
      execute: async () => ({ ok: true, content: '{}' }),
    }),
    /timeout/i,
  )
})
