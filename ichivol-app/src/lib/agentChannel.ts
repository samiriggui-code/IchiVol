/**
 * Client navigateur — canal agent engine (contrat live).
 * Spec : docs/HANDOFF-CLAUDE-AGENT-CHANNEL.md + engine README § Agent command channel
 *
 * Réponses : `{ ok, cmd, data|error }` ; GET tools → `{ tools: [...] }`.
 */

export type AgentCommandName =
  | 'scan_market'
  | 'get_symbol_context'
  | 'detect_signal'
  | 'compare_timeframes'
  | 'run_backtest'
  | 'run_event_study'
  | 'list_rulesets'
  | 'run_ruleset_event_study'
  | 'get_correlations'
  | 'get_news'
  | 'get_calendar'
  | 'calculate_ichimoku'
  | 'calculate_rvol'
  | 'list_tools'
  | (string & {})

export interface AgentToolSpec {
  name: string
  description: string
  read_only: boolean
  args: Record<string, string>
}

export interface AgentCommandRequest {
  cmd: AgentCommandName
  args?: Record<string, unknown>
}

export type AgentCommandResult =
  | { ok: true; cmd: string; data: unknown }
  | { ok: false; cmd: string; error: string }

export interface AgentBatchResponse {
  results: AgentCommandResult[]
}

async function parseJson(res: Response): Promise<unknown> {
  try {
    return await res.json()
  } catch {
    return null
  }
}

/** GET /api/engine/agent/tools */
export async function fetchAgentTools(): Promise<
  | { ok: true; tools: AgentToolSpec[] }
  | { ok: false; error: string }
> {
  const res = await fetch('/api/engine/agent/tools', { credentials: 'include' })
  if (!res.ok) return { ok: false, error: `http_${res.status}` }
  const body = (await parseJson(res)) as { tools?: AgentToolSpec[] }
  if (!Array.isArray(body?.tools)) return { ok: false, error: 'invalid_manifest' }
  return { ok: true, tools: body.tools }
}

/** GET /api/engine/agent/capabilities */
export async function fetchAgentCapabilities(): Promise<
  | { ok: true; data: Record<string, unknown> }
  | { ok: false; error: string }
> {
  const res = await fetch('/api/engine/agent/capabilities', { credentials: 'include' })
  if (!res.ok) return { ok: false, error: `http_${res.status}` }
  const data = (await parseJson(res)) as Record<string, unknown> | null
  if (!data) return { ok: false, error: 'invalid_response' }
  return { ok: true, data }
}

/** POST /api/engine/agent/command */
export async function runAgentCommand(
  req: AgentCommandRequest,
): Promise<AgentCommandResult> {
  const res = await fetch('/api/engine/agent/command', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cmd: req.cmd, args: req.args ?? {} }),
  })
  const body = (await parseJson(res)) as AgentCommandResult | null
  if (!res.ok) {
    return {
      ok: false,
      cmd: String(req.cmd),
      error:
        body && typeof body === 'object' && 'error' in body && body.error
          ? String(body.error)
          : `http_${res.status}`,
    }
  }
  if (!body || typeof body !== 'object' || !('ok' in body)) {
    return { ok: false, cmd: String(req.cmd), error: 'invalid_response' }
  }
  return body
}

/** POST /api/engine/agent/batch — max 20 côté engine */
export async function runAgentBatch(
  commands: AgentCommandRequest[],
): Promise<
  | { ok: true; results: AgentCommandResult[] }
  | { ok: false; error: string }
> {
  const res = await fetch('/api/engine/agent/batch', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ commands }),
  })
  const body = await parseJson(res)
  if (!res.ok) {
    const err =
      body && typeof body === 'object' && body !== null && 'detail' in body
        ? String((body as { detail: unknown }).detail)
        : `http_${res.status}`
    return { ok: false, error: err }
  }
  if (
    !body ||
    typeof body !== 'object' ||
    !('results' in body) ||
    !Array.isArray((body as AgentBatchResponse).results)
  ) {
    return { ok: false, error: 'invalid_response' }
  }
  return { ok: true, results: (body as AgentBatchResponse).results }
}

/** Brief symbole : contexte + multi-TF en un batch. */
export async function symbolBriefPlaybook(
  symbol: string,
  timeframes: string[] = ['15m', '1h', '4h'],
): Promise<
  | { ok: true; results: AgentCommandResult[] }
  | { ok: false; error: string }
> {
  return runAgentBatch([
    {
      cmd: 'get_symbol_context',
      args: { symbol, timeframe: timeframes.includes('1h') ? '1h' : timeframes[0], persist: false },
    },
    { cmd: 'compare_timeframes', args: { symbol, timeframes } },
  ])
}
