/**
 * MTF-1 — helpers d'affichage (le calcul est côté moteur).
 */
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { agreementCount, directionTone, fmtUtc, stateTone, storedMatrix, unavailableReasonLabel } from './mtf.js'

test('tons : direction et état des données', () => {
  assert.equal(directionTone('LONG'), 'green')
  assert.equal(directionTone('SHORT'), 'red')
  assert.equal(directionTone(null), 'gray')
  assert.equal(stateTone('CONFIRMED'), 'green')
  assert.equal(stateTone('LATE'), 'amber')
  assert.equal(stateTone('STALE'), 'red')
  assert.equal(stateTone('UNAVAILABLE'), 'gray')
})

test('heure de clôture affichée en UTC', () => {
  assert.equal(fmtUtc(Date.UTC(2026, 8, 21, 14, 0) / 1000), '21/09 14:00 UTC')
  assert.equal(fmtUtc(null), '—')
})

test('décompte au lieu d’un score', () => {
  const s = {
    decision_tf: '1h', decision_direction: 'LONG' as const, parent_tf: '4h', parent_relation: 'opposed',
    aligned: ['1w'], opposed: ['4h', '1d'], neutral: [], unknown: [], n_available: 4, n_horizons: 4,
  }
  assert.equal(agreementCount(s), '1 aligné · 2 opposés (sur 3 autres horizons)')
})

test('matrice enregistrée : absente pour une position antérieure', () => {
  assert.equal(storedMatrix(null), null)
  assert.equal(storedMatrix({ rvol: 1 }), null)
  const m = { horizons: [], summary: { aligned: [] } }
  assert.deepEqual(storedMatrix({ mtf_matrix: m }), m)
  assert.equal(unavailableReasonLabel('provider_no_timeframe'), 'horizon non servi par la source')
})
