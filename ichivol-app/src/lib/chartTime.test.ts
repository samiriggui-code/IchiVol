import assert from 'node:assert/strict'
import { test } from 'node:test'
import type { UTCTimestamp } from 'lightweight-charts'
import { parisTickMarkFormatter, parisTimeFormatter } from './chartTime'

const at = (iso: string) => (Date.parse(iso) / 1000) as UTCTimestamp

test('heure de Paris en hiver : UTC + 1 h', () => {
  assert.equal(parisTickMarkFormatter(at('2026-10-27T19:00:00Z'), 3), '20:00')
  assert.match(parisTimeFormatter(at('2026-10-27T19:00:00Z')), /20:00/)
})

test('heure de Paris en été : UTC + 2 h', () => {
  assert.equal(parisTickMarkFormatter(at('2026-07-01T19:00:00Z'), 3), '21:00')
})

test('graduation du jour à minuit de Paris', () => {
  assert.match(parisTickMarkFormatter(at('2026-10-27T23:00:00Z'), 2), /28/)
})
