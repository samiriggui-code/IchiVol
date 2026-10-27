/**
 * Prix crypto en direct (flux public Binance, affichage seulement) : URL, parsing, état direct / différé,
 * connexion partagée, flux figé et reconnexion avec un faux WebSocket (aucun réseau).
 */
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  LivePriceFeed,
  buildLiveStreamUrl,
  displayPrice,
  formatLiveAge,
  isLiveCryptoSymbol,
  liveState,
  parseLiveMessage,
  type WsLike,
} from './livePrices.ts'

test('seules les paires USDT ont un flux', () => {
  assert.equal(isLiveCryptoSymbol('BTCUSDT'), true)
  assert.equal(isLiveCryptoSymbol('EURUSD'), false)
  assert.equal(isLiveCryptoSymbol('YM'), false)
  assert.equal(isLiveCryptoSymbol(null), false)
})

test('URL combinée miniTicker, triée, sans doublon ni CFD', () => {
  assert.equal(
    buildLiveStreamUrl(['ETHUSDT', 'BTCUSDT', 'BTCUSDT', 'XAUUSD']),
    'wss://data-stream.binance.vision/stream?streams=btcusdt@miniTicker/ethusdt@miniTicker',
  )
  assert.equal(buildLiveStreamUrl(['EURUSD']), null)
})

test('parsing miniTicker et rejet des messages inutilisables', () => {
  const t = parseLiveMessage(
    JSON.stringify({ stream: 'btcusdt@miniTicker', data: { e: '24hrMiniTicker', E: 1000, s: 'BTCUSDT', c: '80674.01' } }),
    1200,
  )
  assert.deepEqual(t, { symbol: 'BTCUSDT', price: 80674.01, eventMs: 1000, receivedMs: 1200 })
  assert.equal(parseLiveMessage('{"result":null,"id":1}', 1), null)
  assert.equal(parseLiveMessage('pas du json', 1), null)
  assert.equal(parseLiveMessage(JSON.stringify({ data: { s: 'BTCUSDT', c: '0' } }), 1), null)
})

test('direct si le dernier prix a moins de 10 s, sinon différé et prix du serveur', () => {
  const tick = { symbol: 'BTCUSDT', price: 101, eventMs: 0, receivedMs: 1000 }
  assert.equal(liveState(tick, 5000), 'live')
  assert.equal(liveState(tick, 11_001), 'delayed')
  assert.equal(liveState(undefined, 0), 'delayed')
  assert.deepEqual(displayPrice(tick, 99, 3000), { price: 101, state: 'live', ageMs: 2000 })
  assert.deepEqual(displayPrice(tick, 99, 20_000), { price: 99, state: 'delayed', ageMs: 19_000 })
  assert.deepEqual(displayPrice(undefined, null, 0), { price: null, state: 'delayed', ageMs: null })
  assert.equal(formatLiveAge(1400), '1 s')
  assert.equal(formatLiveAge(125_000), '2 min')
})

/** Horloge et minuteries manuelles + faux WebSocket. */
function harness() {
  let now = 0
  let seq = 0
  const timers = new Map<number, { at: number; fn: () => void }>()
  const sockets: (WsLike & { url: string; closed: boolean })[] = []
  const feed = new LivePriceFeed({
    now: () => now,
    setTimer: (fn, ms) => {
      seq += 1
      timers.set(seq, { at: now + ms, fn })
      return seq
    },
    clearTimer: (h) => {
      timers.delete(h as number)
    },
    wsFactory: (url) => {
      const ws = {
        url,
        closed: false,
        onopen: null,
        onmessage: null,
        onclose: null,
        onerror: null,
        close() {
          ws.closed = true
        },
      } as WsLike & { url: string; closed: boolean }
      sockets.push(ws)
      return ws
    },
  })
  const advance = (ms: number) => {
    const end = now + ms
    for (;;) {
      const next = [...timers.entries()].filter(([, t]) => t.at <= end).sort((a, b) => a[1].at - b[1].at)[0]
      if (!next) break
      timers.delete(next[0])
      now = next[1].at
      next[1].fn()
    }
    now = end
  }
  const send = (ws: WsLike, symbol: string, price: string) =>
    ws.onmessage?.({ data: JSON.stringify({ stream: `${symbol.toLowerCase()}@miniTicker`, data: { E: now, s: symbol, c: price } }) })
  return { feed, sockets, advance, send, getNow: () => now }
}

test('une connexion partagée par cellule, regroupée, libérée avec la dernière cellule', () => {
  const h = harness()
  const r1 = h.feed.acquire('BTCUSDT')
  const r2 = h.feed.acquire('BTCUSDT')
  const r3 = h.feed.acquire('ETHUSDT')
  h.feed.acquire('EURUSD') // hors crypto : ignoré
  h.advance(60)
  assert.equal(h.sockets.length, 1)
  assert.match(h.sockets[0].url, /btcusdt@miniTicker\/ethusdt@miniTicker$/)
  let calls = 0
  h.feed.subscribe(() => {
    calls += 1
  })
  h.send(h.sockets[0], 'BTCUSDT', '100.5')
  assert.equal(h.feed.get('BTCUSDT')?.price, 100.5)
  assert.equal(calls, 1)
  r3()
  h.advance(60)
  assert.equal(h.sockets[0].closed, true)
  assert.match(h.sockets[1].url, /streams=btcusdt@miniTicker$/)
  r1()
  r2()
  h.advance(60)
  assert.equal(h.sockets[1].closed, true)
  assert.equal(h.sockets.length, 2) // plus aucune paire : plus de connexion
})

test('flux figé : fermeture puis reconnexion ; coupure : backoff doublé, remis à zéro par un message', () => {
  const h = harness()
  h.feed.acquire('BTCUSDT')
  h.advance(60)
  const first = h.sockets[0]
  first.onopen?.({})
  h.send(first, 'BTCUSDT', '1')
  h.advance(12_000) // aucun message depuis plus de 10 s
  assert.equal(first.closed, true)
  h.advance(1000) // backoff 1 s
  assert.equal(h.sockets.length, 2)
  assert.equal(h.feed.reconnects, 1)
  const second = h.sockets[1]
  second.onclose?.({}) // coupure immédiate, sans message
  h.advance(1999)
  assert.equal(h.sockets.length, 2) // backoff doublé : 2 s
  h.advance(1)
  assert.equal(h.sockets.length, 3)
  h.send(h.sockets[2], 'BTCUSDT', '2') // le flux parle : backoff remis à 1 s
  h.sockets[2].onclose?.({})
  h.advance(1000)
  assert.equal(h.sockets.length, 4)
  assert.equal(h.feed.get('BTCUSDT')?.price, 2)
  h.feed.close()
})
