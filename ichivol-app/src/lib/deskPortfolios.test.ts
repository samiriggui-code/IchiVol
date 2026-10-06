import assert from 'node:assert/strict'
import { test } from 'node:test'
import type { PaperOverview } from './paper.ts'
import { concentrationBySymbol, drawdownOf, sumAccounts, sumCurves, sumRisk } from './deskPortfolios.ts'

function ov(equity: number, cash: number, day: number | null, risk?: Partial<NonNullable<PaperOverview['risk']>>): PaperOverview {
  return {
    account: { initial_cash: 5000, cash, invested: equity - cash, equity, day_change: day, open_positions: 1 },
    positions: [],
    equity_curve: [],
    risk: risk ? { capital: equity, open_risk_amount: 0, max_open_risk_pct: 0.06, open_positions: 1, max_open_positions: 10, ...risk } : undefined,
  } as unknown as PaperOverview
}

test('le capital du Desk additionne les portefeuilles qui répondent', () => {
  const a = sumAccounts([ov(4800, 4300, -10), ov(5100, 5100, null), null])!
  assert.equal(a.equity, 9900)
  assert.equal(a.cash, 9400)
  assert.equal(a.initial_cash, 10000)
  assert.equal(a.day_change, -10)
  assert.equal(a.portfolios, 2)
  assert.equal(sumAccounts([null, null]), null)
})

test('le risque ouvert est rapporté au capital total', () => {
  const r = sumRisk([ov(5000, 0, 0, { open_risk_amount: 50 }), ov(5000, 0, 0, { open_risk_amount: 100, max_open_risk_pct: 0.04 })])!
  assert.equal(r.open_risk_pct, 150 / 10000)
  assert.equal(r.max_open_risk_pct, 0.04)
  assert.equal(r.max_open_positions, 20)
})

test('la courbe totale démarre quand toutes les courbes existent et garde la dernière valeur', () => {
  const total = sumCurves([
    [{ ms: 0, equity: 100 }, { ms: 10, equity: 110 }, { ms: 30, equity: 90 }],
    [{ ms: 10, equity: 200 }, { ms: 20, equity: 210 }],
  ])
  assert.deepEqual(total, [
    { ms: 10, equity: 310 },
    { ms: 20, equity: 320 },
    { ms: 30, equity: 300 },
  ])
  assert.equal(drawdownOf(total), (300 - 320) / 320)
})

test('un même actif dans deux portefeuilles compte une seule fois dans la concentration', () => {
  const c = concentrationBySymbol([
    { symbol: 'AVAXUSDT', market_value: 300 },
    { symbol: 'AVAXUSDT', market_value: 100 },
    { symbol: 'NDX', market_value: 400 },
    { symbol: 'NEARUSDT', market_value: null, current_price: null },
  ] as never)
  assert.deepEqual(c, [
    { symbol: 'AVAX', pct: 50 },
    { symbol: 'NDX', pct: 50 },
  ])
})
