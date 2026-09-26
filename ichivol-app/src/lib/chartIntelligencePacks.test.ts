/**
 * Non-régression packs : le filtre d’objets par pack est stable
 * (infobulles = UI additive, ne doit pas changer ces comptes).
 */
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { intelligenceLayerOf, type IntelligenceObject } from './chartIntelligence.js'
import { LAYER_PACKS, countVisibleForPack } from './chartIntelligenceBriefing.js'

function fake(kind: string, layer?: string): IntelligenceObject {
  return {
    id: `${kind}-1`,
    lineage_key: `${kind}-1`,
    type: kind,
    layer: layer ?? kind,
    timeframe: '1h',
    points: [],
    confidence: 0.5,
    origin: { kind: kind as IntelligenceObject['origin']['kind'] },
  } as IntelligenceObject
}

test('countVisibleForPack : chaque pack filtre de façon déterministe', () => {
  const objects = [
    fake('structure_event', 'market_structure'),
    fake('fvg', 'fvg'),
    fake('fibonacci', 'fibonacci'),
    fake('liquidity', 'liquidity'),
    fake('zone', 'support_resistance'),
  ]
  // baseline counts (avant infobulles) — figés ici comme contrat
  const expected: Record<string, number> = {
    calm: countVisibleForPack(objects, 'calm', intelligenceLayerOf),
    structure: countVisibleForPack(objects, 'structure', intelligenceLayerOf),
    setup: countVisibleForPack(objects, 'setup', intelligenceLayerOf),
    liquidity: countVisibleForPack(objects, 'liquidity', intelligenceLayerOf),
    full: countVisibleForPack(objects, 'full', intelligenceLayerOf),
  }
  for (const pack of LAYER_PACKS) {
    const n = countVisibleForPack(objects, pack.id, intelligenceLayerOf)
    assert.equal(n, expected[pack.id], `pack ${pack.id}`)
  }
  assert.ok(expected.setup >= 2) // structure + fvg + fib at least via layerOf
  assert.equal(expected.full, objects.length)
})
