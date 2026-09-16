import { engineAgentBatch, engineAgentCommand, engineAgentTools } from '../src/agent/engineAgentChannel.ts'
import { getDecisionDetailTool } from '../src/agent/tools/getDecisionDetail.ts'

const tools = await engineAgentTools()
console.log(
  'tools',
  tools.ok ? tools.tools.map((t) => t.name).join(',') : tools.error,
)

const cmd = await engineAgentCommand({
  cmd: 'detect_signal',
  args: { symbol: 'BTCUSDT', timeframe: '1h' },
})
if (cmd.ok) {
  const d = cmd.data as { decision?: string; direction?: string }
  console.log('detect', JSON.stringify({ decision: d.decision, direction: d.direction }))
} else {
  console.log('detect', cmd.error)
}

const detail = await getDecisionDetailTool('BTCUSDT', '1h')
console.log(
  'context',
  detail.ok
    ? [detail.tool, detail.data.combiner, detail.data.direction].join(' ')
    : detail.error,
)

const batch = await engineAgentBatch([
  {
    cmd: 'get_symbol_context',
    args: { symbol: 'BTCUSDT', timeframe: '1h', persist: false },
  },
  {
    cmd: 'compare_timeframes',
    args: { symbol: 'BTCUSDT', timeframes: ['1h', '4h'] },
  },
])
console.log(
  'batch',
  batch.ok
    ? batch.results
        .map((r) => (r.ok ? `${r.cmd}:ok` : `${r.cmd}:${r.error}`))
        .join(' | ')
    : batch.error,
)

const ok =
  tools.ok &&
  cmd.ok &&
  detail.ok &&
  batch.ok &&
  batch.results.every((r) => r.ok)
console.log(ok ? 'SMOKE_AGENT_CHANNEL_OK' : 'SMOKE_AGENT_CHANNEL_FAIL')
process.exit(ok ? 0 : 1)
