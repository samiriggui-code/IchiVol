import { formatDecisionContext, sortStagesByImpact } from '../src/agent/context.ts'

const stages = sortStagesByImpact([
  { id: 'location', status: 'pass', summary: 'above VAH' },
  { id: 'participation', status: 'watch', summary: 'RVOL 1.42' },
  { id: 'direction', status: 'pass', summary: 'above kumo' },
  { id: 'structure', status: 'fail', summary: 'broken HL' },
])

console.log('ORDER:', stages.map((s) => `${s.id}:${s.status}`).join(' | '))

const block = formatDecisionContext({
  symbol: 'NEARUSDT',
  timeframe: '1h',
  price: 2.466,
  combiner: 'BUY',
  direction: 'LONG',
  gateDecision: 'BUY',
  confidence: 0.4,
  rvol: 1.42,
  reasons: ['price_above_kumo'],
  risks: ['low_participation'],
  invalidation: ['close_back_inside_kumo'],
  stages,
})

console.log(block)
const ok =
  block != null &&
  block.includes('=== DRIVERS') &&
  block.includes('- structure: fail') &&
  block.indexOf('- structure:') < block.indexOf('- location:') &&
  block.includes('freins portes: structure=fail, participation=watch')
console.log(ok ? 'SMOKE_OK' : 'SMOKE_FAIL')
process.exit(ok ? 0 : 1)
