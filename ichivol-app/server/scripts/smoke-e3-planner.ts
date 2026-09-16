import {
  extractSymbolFromText,
  extractTimeframeFromText,
  planIntent,
  type AgentIntent,
} from '../src/agent/planner.ts'

const cases: Array<{
  q: string
  ui: 'explain_decision' | 'explain_signal' | 'research' | 'trade_idea'
  expect: AgentIntent
  symbol?: string
  tf?: string
}> = [
  {
    q: 'Explique la décision sur NEARUSDT',
    ui: 'research',
    expect: 'explain_decision',
    symbol: 'NEARUSDT',
  },
  {
    q: 'pourquoi ce BUY',
    ui: 'research',
    expect: 'explain_decision',
  },
  {
    q: 'explique le signal BTC 4h',
    ui: 'research',
    expect: 'explain_signal',
    symbol: 'BTCUSDT',
    tf: '4h',
  },
  {
    q: "c'est quoi le kumo",
    ui: 'explain_signal',
    expect: 'research',
  },
  {
    q: 'quelles paires sont confirmées sur le screener',
    ui: 'research',
    expect: 'trade_idea',
  },
  {
    q: 'sauve cette décision dans le journal',
    ui: 'explain_decision',
    expect: 'save_decision',
  },
  {
    q: 'ajoute BTC à la watchlist',
    ui: 'research',
    expect: 'pin_symbol',
    symbol: 'BTCUSDT',
  },
  {
    q: 'ouvre une position papier sur NEARUSDT',
    ui: 'research',
    expect: 'open_paper_position',
    symbol: 'NEARUSDT',
  },
  {
    q: 'achète en papier sur BTC',
    ui: 'research',
    expect: 'open_paper_position',
    symbol: 'BTCUSDT',
  },
  {
    q: '',
    ui: 'explain_decision',
    expect: 'explain_decision',
  },
  {
    q: '',
    ui: 'research',
    expect: 'fallback',
  },
]

let failed = 0
for (const c of cases) {
  const plan = planIntent({
    question: c.q,
    uiMode: c.ui,
    knownSymbol: undefined,
    knownTimeframe: undefined,
  })
  const okIntent = plan.intent === c.expect
  const okSym = c.symbol ? plan.params.symbol === c.symbol : true
  const okTf = c.tf ? plan.params.timeframe === c.tf : true
  const ok = okIntent && okSym && okTf
  if (!ok) {
    failed++
    console.log('FAIL', c.q || '(empty)', '→', plan.intent, plan.params, 'expected', c.expect)
  } else {
    console.log('OK  ', JSON.stringify(c.q), '→', plan.intent)
  }
}

console.log('extract', extractSymbolFromText('near 1h'), extractTimeframeFromText('near 1h'))
const extractOk =
  extractSymbolFromText('near 1h') === 'NEARUSDT' &&
  extractTimeframeFromText('near 1h') === '1h'

console.log(failed === 0 && extractOk ? 'SMOKE_E3_OK' : 'SMOKE_E3_FAIL')
process.exit(failed === 0 && extractOk ? 0 : 1)
