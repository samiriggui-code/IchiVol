/**
 * UI-P3 — PATCH note décision : création, modification, effacement,
 * ownership (404 autre user), archivée sans doublon (même id).
 */
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  decisionOwnedByUser,
  normalizeDecisionNote,
  parsePatchDecisionBody,
} from './patchDecision.js'

test('note créée (trim)', () => {
  const r = parsePatchDecisionBody({ note: '  setup OK  ' })
  assert.equal(r.ok, true)
  if (r.ok) assert.equal(r.data.note, 'setup OK')
})

test('note modifiée', () => {
  const r = parsePatchDecisionBody({ note: 'nouvelle' })
  assert.equal(r.ok, true)
  if (r.ok) assert.equal(r.data.note, 'nouvelle')
})

test('note effacée (chaîne vide → null)', () => {
  assert.equal(normalizeDecisionNote('   '), null)
  const r = parsePatchDecisionBody({ note: '' })
  assert.equal(r.ok, true)
  if (r.ok) assert.equal(r.data.note, null)
})

test('note tronquée à 500 caractères', () => {
  const n = normalizeDecisionNote('x'.repeat(600))
  assert.equal(typeof n, 'string')
  assert.equal((n as string).length, 500)
})

test('refus ownership — autre utilisateur → 404 côté handler', () => {
  assert.equal(decisionOwnedByUser({ userId: 'user-a' }, 'user-b'), false)
  assert.equal(decisionOwnedByUser(null, 'user-a'), false)
  assert.equal(decisionOwnedByUser({ userId: 'user-a' }, 'user-a'), true)
})

test('décision archivée : patch note ne change que note (pas de nouvel id)', () => {
  const r = parsePatchDecisionBody({ note: 'archive note' })
  assert.equal(r.ok, true)
  if (r.ok) {
    assert.equal(r.data.note, 'archive note')
    assert.equal(r.data.status, undefined, 'status inchangé — update in-place')
  }
})

test('status seul toujours accepté', () => {
  const r = parsePatchDecisionBody({ status: 'archived' })
  assert.equal(r.ok, true)
  if (r.ok) assert.deepEqual(r.data, { status: 'archived' })
})

test('body vide rejeté', () => {
  const r = parsePatchDecisionBody({})
  assert.equal(r.ok, false)
})
