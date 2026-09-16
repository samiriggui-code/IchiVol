/**
 * Appels engine canal agent — contrat live (engine README § Agent command channel).
 * Réponses : `{ ok, cmd, data|error }` ; tools : `{ tools: [...] }`.
 */

import { config } from '../config.js'

export type EngineAgentCommandRequest = {
  cmd: string
  args?: Record<string, unknown>
}

export type EngineAgentToolSpec = {
  name: string
  description: string
  read_only: boolean
  args: Record<string, string>
}

export type EngineAgentCommandOk = {
  ok: true
  cmd: string
  data: unknown
}

export type EngineAgentCommandErr = {
  ok: false
  cmd?: string
  error: string
}

export type EngineAgentCommandResult = EngineAgentCommandOk | EngineAgentCommandErr

async function engineFetch(path: string, init?: RequestInit): Promise<Response> {
  const url = `${config.engineUrl}/api/engine${path}`
  return fetch(url, {
    ...init,
    signal: init?.signal ?? AbortSignal.timeout(45_000),
    headers: {
      Accept: 'application/json',
      ...(init?.headers ?? {}),
    },
  })
}

export async function engineAgentTools(): Promise<
  | { ok: true; tools: EngineAgentToolSpec[] }
  | { ok: false; error: string }
> {
  try {
    const res = await engineFetch('/agent/tools')
    if (!res.ok) return { ok: false, error: `http_${res.status}` }
    const body = (await res.json()) as { tools?: EngineAgentToolSpec[] }
    if (!Array.isArray(body.tools)) return { ok: false, error: 'invalid_manifest' }
    return { ok: true, tools: body.tools }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : 'fetch_failed' }
  }
}

export async function engineAgentCapabilities(): Promise<
  | {
      ok: true
      data: {
        version?: string
        read_only?: boolean
        write_tier_enabled?: boolean
        max_batch_items?: number
        commands?: string[]
      }
    }
  | { ok: false; error: string }
> {
  try {
    const res = await engineFetch('/agent/capabilities')
    if (!res.ok) return { ok: false, error: `http_${res.status}` }
    return { ok: true, data: (await res.json()) as Record<string, unknown> }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : 'fetch_failed' }
  }
}

export async function engineAgentCommand(
  req: EngineAgentCommandRequest,
): Promise<EngineAgentCommandResult> {
  try {
    const res = await engineFetch('/agent/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cmd: req.cmd, args: req.args ?? {} }),
    })
    if (!res.ok) {
      return { ok: false, cmd: req.cmd, error: `http_${res.status}` }
    }
    const body = (await res.json()) as EngineAgentCommandResult
    if (!body || typeof body !== 'object' || !('ok' in body)) {
      return { ok: false, cmd: req.cmd, error: 'invalid_response' }
    }
    return body
  } catch (e) {
    return {
      ok: false,
      cmd: req.cmd,
      error: e instanceof Error ? e.message : 'fetch_failed',
    }
  }
}

export async function engineAgentBatch(
  commands: EngineAgentCommandRequest[],
): Promise<
  | { ok: true; results: EngineAgentCommandResult[] }
  | { ok: false; error: string }
> {
  try {
    const res = await engineFetch('/agent/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ commands }),
    })
    if (!res.ok) {
      return { ok: false, error: `http_${res.status}` }
    }
    const body = (await res.json()) as { results?: EngineAgentCommandResult[] }
    if (!Array.isArray(body.results)) {
      return { ok: false, error: 'invalid_response' }
    }
    return { ok: true, results: body.results }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : 'fetch_failed' }
  }
}
