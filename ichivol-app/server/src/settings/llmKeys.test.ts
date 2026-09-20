import assert from 'node:assert/strict'
import { test } from 'node:test'
import { effectiveEncKeys, keySource, parseKeys, withKey } from './llmKeys.js'

test("parseKeys ignore tout ce qui n'est pas fournisseur connu -> texte", () => {
  assert.deepEqual(parseKeys({ anthropic: 'enc-a', bogus: 'x', openai: 42, openrouter: '' }), {
    anthropic: 'enc-a',
  })
  assert.deepEqual(parseKeys(null), {})
  assert.deepEqual(parseKeys(['anthropic']), {})
})

test("l'ancienne clé unique compte pour le fournisseur qui était actif", () => {
  const keys = effectiveEncKeys({
    llmProvider: 'openrouter',
    llmApiKeyEnc: 'enc-legacy',
    llmKeysEnc: null,
  })
  assert.deepEqual(keys, { openrouter: 'enc-legacy' })
})

test("le JSON gagne sur l'ancienne clé quand les deux visent le même fournisseur", () => {
  const keys = effectiveEncKeys({
    llmProvider: 'openrouter',
    llmApiKeyEnc: 'enc-legacy',
    llmKeysEnc: { openrouter: 'enc-new' },
  })
  assert.equal(keys.openrouter, 'enc-new')
})

test('ajouter la clé Anthropic garde celle OpenRouter (pas de remplacement)', () => {
  const before = effectiveEncKeys({
    llmProvider: 'openrouter',
    llmApiKeyEnc: 'enc-or',
    llmKeysEnc: null,
  })
  const after = withKey(before, 'anthropic', 'enc-an')
  assert.deepEqual(after, { openrouter: 'enc-or', anthropic: 'enc-an' })
  assert.deepEqual(before, { openrouter: 'enc-or' }, 'ne mute pas la valeur précédente')
})

test("effacer une clé n'efface que celle-là", () => {
  const after = withKey({ openrouter: 'a', anthropic: 'b' }, 'anthropic', null)
  assert.deepEqual(after, { openrouter: 'a' })
})

test('keySource combine clé personnelle et clé serveur', () => {
  assert.equal(keySource(true, true), 'both')
  assert.equal(keySource(true, false), 'ui')
  assert.equal(keySource(false, true), 'env')
  assert.equal(keySource(false, false), 'none')
})
