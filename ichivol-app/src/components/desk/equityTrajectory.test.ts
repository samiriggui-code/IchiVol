/**
 * Trajectoire des portefeuilles : % depuis le départ, repères de trades, maintien.
 */
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { bookColors, buildPctSeries, buildTrades, heldAt, pctAxis, type TradeOrder } from './equityTrajectory'

test('chaque livre garde sa couleur, quel que soit l’ordre', () => {
  const a = bookColors(['ICHIVOL_WIDE_V1', 'ICHIVOL_BASELINE_V1', 'X'])
  const b = bookColors(['ICHIVOL_BASELINE_V1', 'X'])
  assert.equal(a.ICHIVOL_BASELINE_V1, b.ICHIVOL_BASELINE_V1)
  assert.notEqual(a.X, a.ICHIVOL_BASELINE_V1)
  assert.notEqual(a.X, a.ICHIVOL_WIDE_V1)
})

test('courbe en % du capital de départ, ouverte par la dernière valeur avant la période', () => {
  const s = buildPctSeries(
    [
      { t: '2026-10-01T00:00:00Z', equity: 5100 },
      { t: '2026-10-10T00:00:00Z', equity: 4950 },
    ],
    5000,
    Date.parse('2026-10-05T00:00:00Z'),
  )
  assert.equal(s.length, 2)
  assert.equal(s[0]!.ms, Date.parse('2026-10-05T00:00:00Z'))
  assert.ok(Math.abs(s[0]!.pct - 0.02) < 1e-9)
  assert.ok(Math.abs(s[1]!.pct + 0.01) < 1e-9)
})

const order = (o: Partial<TradeOrder>): TradeOrder => ({
  id: o.id ?? Math.random().toString(36),
  position_id: 'p1',
  time: '2026-10-10T10:00:00Z',
  symbol: 'BTCUSDT',
  side: 'BUY',
  filled_price: 100,
  qty: 2,
  notional: 200,
  fee: 0.1,
  reason: 'open',
  book_code: 'B',
  book_label: 'Livre B',
  ...o,
})

test('achat puis revente : repères, résultat brut et maintien', () => {
  const { marks, positions } = buildTrades([
    order({ id: '1' }),
    order({ id: '2', time: '2026-10-11T10:00:00Z', side: 'SELL', filled_price: 110, reason: 'take_profit_hit' }),
  ])
  assert.deepEqual(marks.map((m) => m.kind), ['entry_long', 'exit'])
  assert.equal(marks[1]!.grossPnl, 20)
  assert.equal(heldAt(positions, 'B', Date.parse('2026-10-10T12:00:00Z')).length, 1)
  assert.equal(heldAt(positions, 'B', Date.parse('2026-10-12T00:00:00Z')).length, 0)
})

test('vente à découvert puis rachat : gain quand le prix baisse', () => {
  const { marks } = buildTrades([
    order({ id: '1', side: 'SELL' }),
    order({ id: '2', time: '2026-10-11T10:00:00Z', side: 'BUY', filled_price: 90, reason: 'stop_hit' }),
  ])
  assert.deepEqual(marks.map((m) => m.kind), ['entry_short', 'exit'])
  assert.equal(marks[1]!.closedSide, 'short')
  assert.equal(marks[1]!.grossPnl, 20)
})

test('une position encore ouverte reste tenue après une sortie partielle', () => {
  const { positions } = buildTrades(
    [order({ id: '1' }), order({ id: '2', time: '2026-10-11T10:00:00Z', side: 'SELL', reason: 'partial_tp' })],
    [{ bookCode: 'B', symbol: 'BTCUSDT' }],
  )
  assert.equal(heldAt(positions, 'B', Date.parse('2026-10-15T00:00:00Z')).length, 1)
})

test('l’axe contient toujours 0 %', () => {
  const ax = pctAxis(0.01, 0.03)
  assert.ok(ax.min <= 0 && ax.max >= 0.03)
  assert.ok(ax.ticks.includes(0))
})
