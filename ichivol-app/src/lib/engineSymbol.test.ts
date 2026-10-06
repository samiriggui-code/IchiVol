import assert from 'node:assert/strict'
import { test } from 'node:test'
import { toEngineSymbol } from './engineSymbol.ts'

test('crypto courts suffixés USDT, instruments non crypto inchangés', () => {
  assert.equal(toEngineSymbol('btc'), 'BTCUSDT')
  assert.equal(toEngineSymbol('ETHUSDT'), 'ETHUSDT')
  assert.equal(toEngineSymbol('NDX'), 'NDX')
  assert.equal(toEngineSymbol('spx'), 'SPX')
  assert.equal(toEngineSymbol('XAUUSD'), 'XAUUSD')
})
