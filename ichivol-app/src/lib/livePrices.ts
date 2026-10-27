/**
 * Prix crypto en direct dans le navigateur : flux public Binance `wss://data-stream.binance.vision`
 * (données de marché seulement, aucune clé, aucun ordre).
 *
 * Affichage seulement : aucune règle de trading ici. Les stops et objectifs sont contrôlés par le moteur
 * (app/paper/live_protection.py), qui lit son propre flux bookTicker. Le navigateur s'abonne à `<paire>@miniTicker`
 * (un message par seconde et par paire, dernier prix échangé), beaucoup plus léger que bookTicker.
 *
 * - une seule connexion partagée par toutes les cellules (compteur de références par symbole) ;
 * - reconnexion avec backoff (1 s doublé jusqu'à 30 s) ;
 * - flux figé : aucun message depuis STALE_AFTER_MS → « différé », la connexion est rouverte ;
 * - hors crypto (CFD, futures) : rien n'est demandé, la page garde le prix du serveur.
 */

export const LIVE_WS_BASE = 'wss://data-stream.binance.vision'
export const STALE_AFTER_MS = 10_000
const MAX_BACKOFF_MS = 30_000

export interface LiveTick {
  symbol: string
  price: number
  /** Heure de l'événement côté Binance (ms). */
  eventMs: number
  /** Heure de réception locale (ms) : sert à l'âge affiché. */
  receivedMs: number
}

export type LiveState = 'live' | 'delayed'

/** Paire crypto au comptant cotée en USDT (seules ces paires ont un flux Binance). */
export function isLiveCryptoSymbol(symbol: string | null | undefined): boolean {
  return typeof symbol === 'string' && /^[A-Z0-9]{2,15}USDT$/.test(symbol.toUpperCase())
}

export function buildLiveStreamUrl(symbols: readonly string[], base = LIVE_WS_BASE): string | null {
  const list = [...new Set(symbols.filter(isLiveCryptoSymbol).map((s) => s.toLowerCase()))].sort()
  if (list.length === 0) return null
  return `${base}/stream?streams=${list.map((s) => `${s}@miniTicker`).join('/')}`
}

/** Message combiné `{stream, data}` (ou brut) d'un miniTicker → tick, sinon null. */
export function parseLiveMessage(text: string, receivedMs: number): LiveTick | null {
  let msg: unknown
  try {
    msg = JSON.parse(text)
  } catch {
    return null
  }
  if (msg == null || typeof msg !== 'object') return null
  const outer = msg as Record<string, unknown>
  const data = (outer.data ?? outer) as Record<string, unknown>
  if (data == null || typeof data !== 'object' || typeof data.s !== 'string') return null
  const price = Number(data.c)
  if (!Number.isFinite(price) || price <= 0) return null
  const eventMs = Number(data.E)
  return {
    symbol: data.s.toUpperCase(),
    price,
    eventMs: Number.isFinite(eventMs) ? eventMs : receivedMs,
    receivedMs,
  }
}

export function liveState(tick: LiveTick | undefined, nowMs: number, staleMs = STALE_AFTER_MS): LiveState {
  if (!tick) return 'delayed'
  return nowMs - tick.receivedMs <= staleMs ? 'live' : 'delayed'
}

export function formatLiveAge(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000))
  if (s < 60) return `${s} s`
  const m = Math.round(s / 60)
  if (m < 60) return `${m} min`
  return `${Math.round(m / 60)} h`
}

/** Prix à afficher : le tick s'il est frais, sinon le prix du serveur (différé). */
export function displayPrice(
  tick: LiveTick | undefined,
  fallback: number | null | undefined,
  nowMs: number,
  staleMs = STALE_AFTER_MS,
): { price: number | null; state: LiveState; ageMs: number | null } {
  if (tick && liveState(tick, nowMs, staleMs) === 'live') {
    return { price: tick.price, state: 'live', ageMs: nowMs - tick.receivedMs }
  }
  return { price: fallback ?? null, state: 'delayed', ageMs: tick ? nowMs - tick.receivedMs : null }
}

/** Sous-ensemble de WebSocket utilisé (injectable dans les tests). */
export interface WsLike {
  onopen: ((ev: unknown) => void) | null
  onmessage: ((ev: { data: unknown }) => void) | null
  onclose: ((ev: unknown) => void) | null
  onerror: ((ev: unknown) => void) | null
  close(): void
}

export interface LivePriceFeedOptions {
  wsFactory?: (url: string) => WsLike
  now?: () => number
  setTimer?: (fn: () => void, ms: number) => unknown
  clearTimer?: (h: unknown) => void
  staleMs?: number
  base?: string
}

/** Connexion partagée ; les abonnés sont prévenus à chaque prix reçu. */
export class LivePriceFeed {
  private readonly refs = new Map<string, number>()
  private readonly ticks = new Map<string, LiveTick>()
  private readonly listeners = new Set<() => void>()
  private ws: WsLike | null = null
  private url: string | null = null
  private backoffMs = 1000
  private reconnectTimer: unknown = null
  private watchdog: unknown = null
  private syncTimer: unknown = null
  private lastMessageMs = 0
  reconnects = 0
  private readonly o: Required<Omit<LivePriceFeedOptions, 'wsFactory'>> & { wsFactory: (url: string) => WsLike }

  constructor(opts: LivePriceFeedOptions = {}) {
    this.o = {
      wsFactory: opts.wsFactory ?? ((url) => new WebSocket(url) as unknown as WsLike),
      now: opts.now ?? (() => Date.now()),
      setTimer: opts.setTimer ?? ((fn, ms) => setTimeout(fn, ms)),
      clearTimer: opts.clearTimer ?? ((h) => clearTimeout(h as ReturnType<typeof setTimeout>)),
      staleMs: opts.staleMs ?? STALE_AFTER_MS,
      base: opts.base ?? LIVE_WS_BASE,
    }
  }

  /** Demande le flux d'un symbole ; renvoie la fonction de libération. */
  acquire(symbol: string): () => void {
    const s = symbol.toUpperCase()
    if (!isLiveCryptoSymbol(s)) return () => {}
    this.refs.set(s, (this.refs.get(s) ?? 0) + 1)
    this.scheduleSync()
    let released = false
    return () => {
      if (released) return
      released = true
      const n = (this.refs.get(s) ?? 1) - 1
      if (n <= 0) this.refs.delete(s)
      else this.refs.set(s, n)
      this.scheduleSync()
    }
  }

  get(symbol: string): LiveTick | undefined {
    return this.ticks.get(symbol.toUpperCase())
  }

  subscribe(fn: () => void): () => void {
    this.listeners.add(fn)
    return () => {
      this.listeners.delete(fn)
    }
  }

  /** Tick le plus récent parmi les paires demandées (état global du flux). */
  freshest(): LiveTick | undefined {
    let best: LiveTick | undefined
    for (const s of this.refs.keys()) {
      const t = this.ticks.get(s)
      if (t && (!best || t.receivedMs > best.receivedMs)) best = t
    }
    return best
  }

  symbols(): string[] {
    return [...this.refs.keys()].sort()
  }

  /** Regroupe les acquisitions d'un même rendu en une seule (re)connexion. */
  private scheduleSync(): void {
    if (this.syncTimer != null) return
    this.syncTimer = this.o.setTimer(() => {
      this.syncTimer = null
      this.sync()
    }, 50)
  }

  sync(): void {
    const url = buildLiveStreamUrl(this.symbols(), this.o.base)
    if (url === this.url && this.ws) return
    this.url = url
    this.disconnect()
    if (url) this.connect()
  }

  private connect(): void {
    if (!this.url) return
    const ws = this.o.wsFactory(this.url)
    this.ws = ws
    this.lastMessageMs = this.o.now()
    ws.onopen = () => {
      this.armWatchdog()
    }
    ws.onmessage = (ev) => {
      if (this.ws !== ws) return
      const now = this.o.now()
      this.lastMessageMs = now
      this.backoffMs = 1000 // flux qui parle : backoff remis à zéro
      const tick = typeof ev.data === 'string' ? parseLiveMessage(ev.data, now) : null
      if (tick) {
        this.ticks.set(tick.symbol, tick)
        for (const fn of this.listeners) fn()
      }
    }
    ws.onerror = () => {
      /* la fermeture suit : reconnexion gérée par onclose */
    }
    ws.onclose = () => {
      if (this.ws !== ws) return
      this.ws = null
      this.scheduleReconnect()
    }
    this.armWatchdog()
  }

  private armWatchdog(): void {
    if (this.watchdog != null) this.o.clearTimer(this.watchdog)
    this.watchdog = this.o.setTimer(() => {
      this.watchdog = null
      if (!this.ws) return
      if (this.o.now() - this.lastMessageMs > this.o.staleMs) {
        // flux figé : on ferme et on rouvre (les abonnés voient « différé » d'ici là)
        const ws = this.ws
        this.ws = null
        try {
          ws.close()
        } catch {
          /* déjà fermé */
        }
        for (const fn of this.listeners) fn()
        this.scheduleReconnect()
        return
      }
      this.armWatchdog()
    }, Math.min(this.o.staleMs, 2000))
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer != null || !this.url) return
    const wait = this.backoffMs
    this.backoffMs = Math.min(this.backoffMs * 2, MAX_BACKOFF_MS)
    this.reconnectTimer = this.o.setTimer(() => {
      this.reconnectTimer = null
      if (this.ws || !this.url) return
      this.reconnects += 1
      this.connect()
    }, wait)
  }

  private disconnect(): void {
    if (this.reconnectTimer != null) {
      this.o.clearTimer(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.watchdog != null) {
      this.o.clearTimer(this.watchdog)
      this.watchdog = null
    }
    const ws = this.ws
    this.ws = null
    if (ws) {
      try {
        ws.close()
      } catch {
        /* déjà fermé */
      }
    }
  }

  close(): void {
    this.refs.clear()
    this.url = null
    this.disconnect()
  }
}
