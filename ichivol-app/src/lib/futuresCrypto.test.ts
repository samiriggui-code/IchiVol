/**
 * Futures & Crypto : contrats, risque par marché et place restante sous le plafond global.
 */
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { btcModeErrorFr, contractsFor, fullPositionsLeft, marketRisk } from './futuresCrypto.ts'

test('quantité paper → contrats CME', () => {
  assert.equal(contractsFor(10, 5), 2) // YM : 5 $ par point
  assert.equal(contractsFor(-5, 10), 0.5) // MGC : 10 onces, sens ignoré
  assert.equal(contractsFor(null, 5), null)
  assert.equal(contractsFor(1, 0), null)
})

test('risque et exposition d’un seul marché', () => {
  const positions = [
    { symbol: 'YM', status: 'OPEN', qty: 2, current_price: 100, risk_amount: 25 },
    { symbol: 'MGC', status: 'OPEN', qty: 1, market_value: 500, risk_amount: 10 },
    { symbol: 'YM', status: 'CLOSED', qty: 9, current_price: 100, risk_amount: 99 },
  ]
  const ym = marketRisk('YM', positions, 5000, 0.01)
  assert.equal(ym.riskAmount, 25)
  assert.equal(ym.exposure, 200)
  assert.equal(ym.riskPctOfEquity, 0.005)
  assert.equal(ym.shareOfCap, 0.5)
  const btc = marketRisk('BTCUSDT', positions, 5000, 0.01)
  assert.equal(btc.riskAmount, 0)
  assert.equal(marketRisk('YM', positions, null, 0.01).shareOfCap, null)
})

test('plafond global : deux positions pleines, puis plus rien', () => {
  assert.equal(fullPositionsLeft(0, 5000, 0.005, 0.01), 2)
  assert.equal(fullPositionsLeft(25, 5000, 0.005, 0.01), 1)
  assert.equal(fullPositionsLeft(50, 5000, 0.005, 0.01), 0)
  assert.equal(fullPositionsLeft(60, 5000, 0.005, 0.01), 0)
  assert.equal(fullPositionsLeft(0, null, 0.005, 0.01), null)
})

test('refus du moteur traduit', () => {
  assert.match(btcModeErrorFr('btc_position_open: close the open BTCUSDT lot'), /position BTC est ouverte/)
  assert.equal(btcModeErrorFr('autre'), 'autre')
})

test('phrase du dernier verdict', async () => {
  const { signalSentenceFr, verdictLabelFr } = await import('./futuresCrypto.ts')
  const sig = {
    decision: 'SELL', direction: 'SHORT', price: 1, timeframe: '1h', bar_close: null,
    seen_at: '2026-10-07T08:00:00Z', stages: [], action: null,
  }
  assert.match(signalSentenceFr(sig, false), /ne vend pas à découvert/)
  assert.doesNotMatch(signalSentenceFr(sig, true), /découvert/)
  assert.match(signalSentenceFr({ ...sig, decision: 'BUY', action: 'opened' }, false), /position a été ouverte/)
  assert.match(signalSentenceFr(null, false), /prochain passage/)
  assert.equal(verdictLabelFr('NO_TRADE'), 'Pas de trade')
})
