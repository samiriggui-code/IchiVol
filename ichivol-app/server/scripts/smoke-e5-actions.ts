import { db } from '../src/db.ts'
import { writeAuditLog } from '../src/audit/log.ts'

const u = await db.user.findFirst({ orderBy: { createdAt: 'asc' } })
if (!u) {
  console.error('No user')
  process.exit(1)
}

const pin = await db.watchlistItem.upsert({
  where: { userId_symbol: { userId: u.id, symbol: 'BTCUSDT' } },
  create: { userId: u.id, symbol: 'BTCUSDT' },
  update: { updatedAt: new Date() },
})

const action = await db.agentAction.create({
  data: {
    userId: u.id,
    kind: 'pin_symbol',
    status: 'confirmed',
    symbol: 'BTCUSDT',
    timeframe: '1h',
    result: { watchlistId: pin.id },
  },
})

await writeAuditLog({
  userId: u.id,
  action: 'agent.action.confirm',
  meta: { actionId: action.id, intent: 'pin_symbol', symbol: 'BTCUSDT' },
})

const logs = await db.auditLog.count({
  where: { userId: u.id, action: 'agent.action.confirm' },
})

console.log('pin', pin.symbol, 'action', action.status, 'audit_count', logs)
console.log(pin.symbol === 'BTCUSDT' && action.status === 'confirmed' && logs > 0 ? 'SMOKE_E5_OK' : 'SMOKE_E5_FAIL')
process.exit(pin.symbol === 'BTCUSDT' && action.status === 'confirmed' && logs > 0 ? 0 : 1)
