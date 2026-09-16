import type { ProviderName } from '../config.js'

export type LlmTestStatus = 'ok' | 'no_key' | 'bad_key' | 'unreachable' | 'error'

export interface LlmTestResult {
  ok: boolean
  status: LlmTestStatus
  provider: ProviderName
  model: string
  latencyMs: number
  message: string
}

function classifyHttpError(status: number, body: string): { status: LlmTestStatus; message: string } {
  if (status === 401 || status === 403) {
    return { status: 'bad_key', message: 'Clé API refusée (401/403) — vérifie la clé et le provider.' }
  }
  if (status === 404) {
    return { status: 'error', message: `Modèle introuvable (404) : ${body.slice(0, 180)}` }
  }
  if (status === 429) {
    return { status: 'error', message: 'Quota / rate-limit atteint (429).' }
  }
  return { status: 'error', message: `HTTP ${status}: ${body.slice(0, 220)}` }
}

async function pingAnthropic(apiKey: string, model: string): Promise<Omit<LlmTestResult, 'provider' | 'model' | 'latencyMs'>> {
  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model,
      max_tokens: 16,
      messages: [{ role: 'user', content: 'ping' }],
    }),
  })
  if (!res.ok) {
    const body = await res.text()
    const c = classifyHttpError(res.status, body)
    return { ok: false, ...c }
  }
  return { ok: true, status: 'ok', message: 'Connexion Anthropic OK' }
}

async function pingOpenAiCompatible(
  name: 'openai' | 'openrouter',
  baseUrl: string,
  apiKey: string,
  model: string,
  extraHeaders?: Record<string, string>,
): Promise<Omit<LlmTestResult, 'provider' | 'model' | 'latencyMs'>> {
  const res = await fetch(`${baseUrl}/chat/completions`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      authorization: `Bearer ${apiKey}`,
      ...extraHeaders,
    },
    body: JSON.stringify({
      model,
      max_tokens: 16,
      messages: [{ role: 'user', content: 'ping' }],
    }),
  })
  if (!res.ok) {
    const body = await res.text()
    const c = classifyHttpError(res.status, body)
    return { ok: false, ...c }
  }
  return { ok: true, status: 'ok', message: `Connexion ${name} OK` }
}

export async function testLlmConnection(opts: {
  provider: ProviderName
  model: string
  apiKey: string | undefined
}): Promise<LlmTestResult> {
  const started = Date.now()
  if (!opts.apiKey?.trim()) {
    return {
      ok: false,
      status: 'no_key',
      provider: opts.provider,
      model: opts.model,
      latencyMs: 0,
      message: 'Aucune clé API — configure-la dans Paramètres.',
    }
  }

  try {
    let result: Omit<LlmTestResult, 'provider' | 'model' | 'latencyMs'>
    switch (opts.provider) {
      case 'anthropic':
        result = await pingAnthropic(opts.apiKey, opts.model)
        break
      case 'openai':
        result = await pingOpenAiCompatible('openai', 'https://api.openai.com/v1', opts.apiKey, opts.model)
        break
      case 'openrouter':
        result = await pingOpenAiCompatible(
          'openrouter',
          'https://openrouter.ai/api/v1',
          opts.apiKey,
          opts.model,
          {
            'HTTP-Referer': 'http://localhost:5173',
            'X-Title': 'IchiVol',
          },
        )
        break
      default: {
        const _exhaustive: never = opts.provider
        return _exhaustive
      }
    }
    return {
      ...result,
      provider: opts.provider,
      model: opts.model,
      latencyMs: Date.now() - started,
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Erreur réseau'
    const unreachable = /fetch failed|ECONNREFUSED|ENOTFOUND|ETIMEDOUT|network/i.test(message)
    return {
      ok: false,
      status: unreachable ? 'unreachable' : 'error',
      provider: opts.provider,
      model: opts.model,
      latencyMs: Date.now() - started,
      message: unreachable ? `Provider injoignable — ${message}` : message,
    }
  }
}
