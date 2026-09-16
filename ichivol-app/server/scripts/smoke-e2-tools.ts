import { searchKbTool } from '../src/agent/tools/searchKb.ts'
import { mapEngineToDecisionPayload } from '../src/agent/tools/getDecisionDetail.ts'
import { getDecisionDetailTool } from '../src/agent/tools/getDecisionDetail.ts'
import {
  canResolveDecisionViaTools,
  hasFullClientDecision,
  resolveSymbolTimeframe,
} from '../src/agent/validate.ts'

const mapped = mapEngineToDecisionPayload(
  {
    symbol: 'NEARUSDT',
    timeframe: '1h',
    price: 2.46,
    decision: 'BUY',
    direction: 'LONG',
    confidence: 0.4,
    rvol: 1.42,
    reasons: ['price_above_kumo'],
    risks: ['low_participation'],
    invalidation: ['close_back_inside_kumo'],
    pipeline: {
      decision: 'BUY',
      stages: [
        { id: 'direction', status: 'pass', summary: 'above kumo' },
        { id: 'participation', status: 'watch', summary: 'RVOL 1.42' },
      ],
    },
  },
  { symbol: 'NEARUSDT', timeframe: '1h' },
)

const kb = searchKbTool('ichimoku cloud tenkan', 2)
const resolved = resolveSymbolTimeframe({
  mode: 'explain_decision',
  question: '',
  symbol: 'btcusdt',
  timeframe: '4h',
})

console.log('mapped_ok', mapped?.combiner === 'BUY' && mapped.stages.length === 2)
console.log('kb_ok', kb.ok && kb.data.hits.length >= 0)
console.log('resolve', resolved)
console.log(
  'via_tools',
  canResolveDecisionViaTools({ mode: 'explain_decision', question: '', symbol: 'ETHUSDT' }),
)
console.log(
  'full_client',
  hasFullClientDecision({
    mode: 'explain_decision',
    question: '',
    decision: mapped!,
  }),
)

const engine = await getDecisionDetailTool('BTCUSDT', '1h')
console.log('engine_tool', engine.ok ? `OK ${engine.data.combiner}` : `ERR ${engine.error}`)

const ok =
  mapped != null &&
  kb.ok &&
  resolved.symbol === 'BTCUSDT' &&
  resolved.timeframe === '4h'
console.log(ok ? 'SMOKE_E2_OK' : 'SMOKE_E2_FAIL')
process.exit(ok ? 0 : 1)
