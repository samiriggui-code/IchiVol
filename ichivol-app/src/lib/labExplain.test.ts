import assert from 'node:assert/strict'
import { test } from 'node:test'
import { conditionText, foldVerdict, performanceVerdict } from './labExplain.ts'

test('conditionText traduit les conditions de règle', () => {
  assert.match(conditionText('rvol_min', 1.5), /1,5 fois le volume/)
  assert.match(conditionText('tk_cross_age_max', 3), /3 bougies/)
  assert.equal(conditionText('inconnu_x', true), 'inconnu x = true')
})

test('performanceVerdict tient compte de l’échantillon', () => {
  assert.equal(performanceVerdict({ trades: 0, expectancy: null, pf: null }).text, 'AUCUN TRADE')
  assert.equal(performanceVerdict({ trades: 10, expectancy: 0.01, pf: 2 }).tone, 'amber')
  assert.equal(performanceVerdict({ trades: 50, expectancy: 0.01, pf: 1.3 }).text, 'RENTABLE')
  assert.equal(performanceVerdict({ trades: 50, expectancy: -0.01, pf: 0.8 }).text, 'PERDANT')
})

test('foldVerdict : tient si PF testé > 1', () => {
  const m = (n: number, pf: number | null) =>
    ({ num_trades: n, profit_factor: pf }) as Parameters<typeof foldVerdict>[0]
  assert.equal(foldVerdict(null).text, 'AUCUN TRADE')
  assert.equal(foldVerdict(m(3, 1.4)).text, 'TIENT')
  assert.equal(foldVerdict(m(3, 0.7)).text, 'NE TIENT PAS')
})
