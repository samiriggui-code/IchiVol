import { db } from '../src/db.ts'
import {
  appendMessage,
  createThread,
  getThreadForUser,
  loadThreadHistory,
  touchThreadSlots,
} from '../src/agent/threads.ts'

const u = await db.user.findFirst({ orderBy: { createdAt: 'asc' } })
if (!u) {
  console.error('No user in DB')
  process.exit(1)
}
console.log('using user', u.email)

const thread = await createThread({
  userId: u.id,
  assumedSymbol: 'NEARUSDT',
  assumedTimeframe: '1h',
  lastMode: 'explain_decision',
  title: 'NEARUSDT · 1h',
})

await appendMessage({
  threadId: thread.id,
  role: 'user',
  content: 'Explique la décision sur NEARUSDT',
  mode: 'explain_decision',
  intent: 'explain_decision',
})
await appendMessage({
  threadId: thread.id,
  role: 'assistant',
  content: 'Verdict BUY…',
  mode: 'explain_decision',
  intent: 'explain_decision',
})
await touchThreadSlots(thread.id, {
  assumedSymbol: 'NEARUSDT',
  assumedTimeframe: '1h',
  pendingIntent: null,
})

const loaded = await getThreadForUser(thread.id, u.id)
const hist = await loadThreadHistory(thread.id)

console.log('thread', loaded?.id, loaded?.assumedSymbol)
console.log('history_len', hist.length)
const ok = loaded?.assumedSymbol === 'NEARUSDT' && hist.length === 2
console.log(ok ? 'SMOKE_E4_OK' : 'SMOKE_E4_FAIL')
process.exit(ok ? 0 : 1)
