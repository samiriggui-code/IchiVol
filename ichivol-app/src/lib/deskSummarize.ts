import type { DecisionLabel, ScreenerDecisionRow } from '../lib/decisions'
import { asGate } from '../lib/verdict'

function isBuy(d: DecisionLabel): boolean {
  return d === 'BUY' || d === 'STRONG_BUY'
}
function isSell(d: DecisionLabel): boolean {
  return d === 'SELL' || d === 'STRONG_SELL'
}
function isWatch(d: DecisionLabel): boolean {
  return d === 'WATCH' || d === 'WAIT'
}

export function verdictBucket(r: ScreenerDecisionRow): 'buy' | 'sell' | 'watch' | 'none' {
  const gate = asGate(r.pipeline?.decision as string | undefined)
  if (gate) {
    if (gate === 'BUY') return 'buy'
    if (gate === 'SELL') return 'sell'
    if (gate === 'WATCH') return 'watch'
    return 'none'
  }
  if (isBuy(r.decision)) return 'buy'
  if (isSell(r.decision)) return 'sell'
  if (isWatch(r.decision)) return 'watch'
  return 'none'
}

export function summarizeScreener(rows: ScreenerDecisionRow[]) {
  let buy = 0
  let sell = 0
  let watch = 0
  const stagePass: Record<string, number> = {
    direction: 0,
    participation: 0,
    structure: 0,
    location: 0,
    regime: 0,
  }
  for (const r of rows) {
    const bucket = verdictBucket(r)
    if (bucket === 'buy') buy += 1
    else if (bucket === 'sell') sell += 1
    else if (bucket === 'watch') watch += 1
    const stages = r.pipeline?.stages
    if (Array.isArray(stages)) {
      for (const s of stages) {
        if (s.id in stagePass && s.status === 'pass') stagePass[s.id] += 1
      }
    }
  }
  const none = Math.max(0, rows.length - buy - sell - watch)
  return { buy, sell, watch, none, total: rows.length, stagePass }
}
