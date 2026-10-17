/**
 * Qui a décidé un trade : moteur seul, Ève ou manuel, et bilan par décideur.
 */
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { deciderOf, eveDossierId, scoreByDecider } from './decider'
import type { PaperPosition } from './paper'

const pos = (o: Partial<PaperPosition>): PaperPosition =>
  ({
    id: Math.random().toString(36),
    symbol: 'BTCUSDT',
    timeframe: '1h',
    source: 'auto_watchlist',
    user_id: null,
    direction: 'LONG',
    status: 'CLOSED',
    entry_time: '2026-10-10T10:00:00Z',
    entry_price: 100,
    entry_decision: 'BUY',
    exit_time: null,
    exit_price: null,
    exit_reason: null,
    pnl_pct: null,
    ...o,
  }) as PaperPosition

test('le moteur, Ève et une personne sont reconnus', () => {
  assert.equal(deciderOf(pos({})), 'engine')
  assert.equal(deciderOf(pos({ source: 'user_confirmed', user_id: 'eve_intelligence' })), 'eve')
  assert.equal(deciderOf(pos({ source: 'user_confirmed', user_id: 'u-1', entry_signal: { eve_dossier_id: 'd1' } })), 'eve')
  assert.equal(deciderOf(pos({ source: 'user_confirmed', user_id: 'u-1' })), 'manual')
  assert.equal(eveDossierId(pos({ entry_signal: { eve_dossier_id: 'd1' } })), 'd1')
})

test('bilan net de frais par décideur, positions ouvertes comptées à part', () => {
  const s = scoreByDecider([
    pos({ realized_pnl: 12, entry_fee: 0.5, exit_fee: 0.5 }),
    pos({ realized_pnl: -4 }),
    pos({ source: 'user_confirmed', user_id: 'eve_intelligence', realized_pnl: 6 }),
    pos({ source: 'user_confirmed', user_id: 'eve_intelligence', status: 'OPEN' }),
  ])
  assert.equal(s.engine.trades, 2)
  assert.equal(s.engine.net, 8)
  assert.equal(s.engine.winRate, 0.5)
  assert.equal(s.engine.fees, 1)
  assert.equal(s.engine.avgLoss, -4)
  assert.equal(s.eve.trades, 1)
  assert.equal(s.eve.open, 1)
  assert.equal(s.manual.trades, 0)
  assert.equal(s.manual.winRate, null)
})
