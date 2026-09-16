import type { Request, Response } from 'express'
import { config } from '../config.js'
import { resolveTwelveDataKeyForUser } from '../settings/resolve.js'

/**
 * Thin passthrough to the Python engine (ichivol-app/engine).
 * Forwards GET/POST; injects session `user_id` on paper routes so the front
 * cannot spoof another user's portfolio.
 */
export async function proxyToEngine(req: Request, res: Response): Promise<void> {
  let targetUrl = `${config.engineUrl}${req.originalUrl}`

  if (req.user && req.path.includes('/paper/')) {
    const u = new URL(targetUrl)
    const source = u.searchParams.get('source')
    // auto_watchlist has user_id=NULL — never filter it by session id.
    // user_confirmed + POST open always bind to the logged-in user.
    if (req.method === 'POST' || source === 'user_confirmed') {
      u.searchParams.set('user_id', req.user.id)
    }
    targetUrl = u.toString()
  }

  const timeoutMs = req.path.includes('/screener') ? 120_000 : 60_000
  try {
    const twelveDataKey = req.user ? await resolveTwelveDataKeyForUser(req.user.id) : undefined
    const headers: Record<string, string> = {}
    if (twelveDataKey) headers['X-Twelve-Data-Key'] = twelveDataKey

    const init: RequestInit = {
      method: req.method,
      signal: AbortSignal.timeout(timeoutMs),
      headers,
    }
    if (req.method !== 'GET' && req.method !== 'HEAD' && req.body != null) {
      headers['content-type'] = 'application/json'
      init.body = JSON.stringify(req.body)
    }

    const upstream = await fetch(targetUrl, init)
    const body = await upstream.text()
    res.status(upstream.status)
    res.setHeader('content-type', upstream.headers.get('content-type') ?? 'application/json')
    res.send(body)
  } catch (err) {
    const detail = err instanceof Error ? err.message : String(err)
    const timedOut = /aborted|timeout/i.test(detail)
    res.status(timedOut ? 504 : 502).json({
      error: timedOut ? 'engine_timeout' : 'engine_unreachable',
      message: timedOut
        ? `Le moteur a dépassé ${timeoutMs / 1000}s (screener live trop long). Réessaie ou remets les seuils Settings aux défauts pour utiliser le cache.`
        : `Could not reach the Python engine at ${config.engineUrl}. Is it running?`,
      detail,
    })
  }
}
