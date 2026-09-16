/** Client corrélations engine (CDC-VIZ-002) — lecture seule, jamais un vote. */

export type CorrelationMethod = 'log_returns' | 'price'

export interface CorrelationSkipped {
  symbol: string
  reason: string
}

export interface CorrelationMatrix {
  timeframe: string
  method: CorrelationMethod | string
  symbols: string[]
  sample_size: number
  /** matrix[i][j] = corr(symbols[i], symbols[j]) ; null si variance nulle */
  matrix: (number | null)[][]
  skipped: CorrelationSkipped[]
}

async function parseError(res: Response): Promise<string> {
  const body = (await res.json().catch(() => null)) as
    | { detail?: string; error?: string; message?: string }
    | null
  return body?.detail ?? body?.error ?? body?.message ?? `Erreur ${res.status}`
}

export async function fetchCorrelations(opts?: {
  timeframe?: string
  method?: CorrelationMethod
  /** Liste explicite ; omit = watchlist moteur (crypto + biquote). */
  symbols?: string[]
  limit?: number
}): Promise<CorrelationMatrix> {
  const params = new URLSearchParams()
  params.set('timeframe', opts?.timeframe ?? '1h')
  params.set('method', opts?.method ?? 'log_returns')
  if (opts?.limit) params.set('limit', String(opts.limit))
  if (opts?.symbols && opts.symbols.length > 0) {
    params.set('symbols', opts.symbols.join(','))
  }
  const res = await fetch(`/api/engine/correlations?${params}`, { credentials: 'include' })
  if (!res.ok) throw new Error(await parseError(res))
  return res.json() as Promise<CorrelationMatrix>
}
