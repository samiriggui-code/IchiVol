/**
 * Planner intent — « Pourquoi BTC attend-il ? » doit charger la décision moteur,
 * pas tomber en research théorique.
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { extractSymbolFromText, planIntent } from './planner.js'

describe('planIntent — wait / attend → explain_decision', () => {
  it('Pourquoi BTC attend-il ? → explain_decision + BTCUSDT', () => {
    const r = planIntent({
      question: 'Pourquoi BTC attend-il ?',
      uiMode: 'research',
    })
    assert.equal(r.intent, 'explain_decision')
    assert.equal(r.params.symbol, 'BTCUSDT')
    assert.equal(r.source, 'rules')
  })

  it('why is ETH waiting → explain_decision', () => {
    const r = planIntent({
      question: 'why is ETH waiting?',
      uiMode: 'research',
    })
    assert.equal(r.intent, 'explain_decision')
    assert.equal(r.params.symbol, 'ETHUSDT')
  })

  it('extractSymbol BTC → BTCUSDT', () => {
    assert.equal(extractSymbolFromText('BTC'), 'BTCUSDT')
    assert.equal(extractSymbolFromText('btcusdt 1h'), 'BTCUSDT')
  })

  it('pure theory stays research', () => {
    const r = planIntent({
      question: "C'est quoi le Tenkan ?",
      uiMode: 'research',
    })
    assert.equal(r.intent, 'research')
  })
})
