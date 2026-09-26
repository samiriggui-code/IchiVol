/**
 * Non-régression packs + repli largeur overlay (CI-T1 / CI-T2).
 */
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { intelligenceLayerOf, type IntelligenceObject } from './chartIntelligence.js'
import { LAYER_PACKS, countVisibleForPack } from './chartIntelligenceBriefing.js'
import { plotWidthPx } from '../components/chart-intelligence/IntelligenceChart.js'

function fake(layer: string): IntelligenceObject {
  return {
    id: `${layer}-1`,
    lineage_key: `${layer}-1`,
    type: 'zone',
    layer,
    timeframe: '1h',
    points: [],
    confidence: 0.5,
    origin: { kind: 'zone' },
  } as IntelligenceObject
}

/**
 * Fixture dérivée à la main de LAYER_PACKS + intelligenceLayerOf :
 * - breaks → market_structure
 * - support_resistance, fibonacci, fvg, liquidity → homonymes
 *
 * Attendu :
 *   calm (MS)           → 1
 *   structure (MS+SR)   → 2
 *   setup (MS+Fib+FVG)  → 3
 *   liquidity (MS+SR+L) → 3
 *   full                → 5
 */
const FIXTURE: IntelligenceObject[] = [
  fake('breaks'),
  fake('fvg'),
  fake('fibonacci'),
  fake('liquidity'),
  fake('support_resistance'),
]

const EXPECTED_BY_PACK: Record<string, number> = {
  calm: 1,
  structure: 2,
  setup: 3,
  liquidity: 3,
  full: 5,
}

test('countVisibleForPack : nombres figés dérivés de LAYER_PACKS', () => {
  for (const pack of LAYER_PACKS) {
    const n = countVisibleForPack(FIXTURE, pack.id, intelligenceLayerOf)
    assert.equal(n, EXPECTED_BY_PACK[pack.id], `pack ${pack.id}`)
  }
})

test('plotWidthPx : scale>0 inchangé ; scale=0 → hôte − échelle droite', () => {
  assert.equal(plotWidthPx(640, 700, 55), 640)
  assert.equal(plotWidthPx(0, 700, 55), 645)
  assert.equal(plotWidthPx(0, 100, 120), 0)
})
