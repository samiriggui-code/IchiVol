import assert from 'node:assert/strict'
import { test } from 'node:test'
import { ablationVerdict, layerLabel, num, pct, regimeLabel } from './labFormat.ts'

test('formats lisibles', () => {
  assert.equal(pct(0.1234), '12,3 %')
  assert.equal(pct(0.004, 2, true), '+0,40 %')
  assert.equal(pct(null), '—')
  assert.equal(num(1.456), '1,46')
})

test('libellés des couches et régimes', () => {
  assert.equal(layerLabel('B_RVOL'), 'B · + Volume relatif ≥ 1,5')
  assert.equal(layerLabel('A_ICHIMOKU+B_RVOL'), 'B · + Volume relatif ≥ 1,5')
  assert.equal(layerLabel('X_NEW'), 'X NEW')
  assert.equal(regimeLabel('GLOBAL'), 'Tous les signaux')
})

test('verdict ablation', () => {
  assert.equal(ablationVerdict(true, true).text, 'AMÉLIORE')
  assert.equal(ablationVerdict(true, false).text, 'MITIGÉ')
  assert.equal(ablationVerdict(false, false).text, 'DÉGRADE')
  assert.equal(ablationVerdict(null, null).text, 'PAS ASSEZ DE TRADES')
})
