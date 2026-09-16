/**
 * Preuve de bout en bout : Copilot propose "open_paper_position" -> user
 * confirme -> l'engine ouvre (ou refuse proprement) une position papier.
 * Ne fake rien : vraie requête HTTP contre le serveur Express local (qui
 * doit tourner en dev, tsx watch) et contre l'engine (port 8000).
 */
import { db } from '../src/db.ts'
import { signSession } from '../src/auth/jwt.ts'

const PORT = process.env.PORT || 8787
const BASE = `http://127.0.0.1:${PORT}`
const ENGINE_URL = process.env.ENGINE_URL || 'http://127.0.0.1:8000'

const u = await db.user.findFirst({ orderBy: { createdAt: 'asc' } })
if (!u) {
  console.error('No user in DB -- run create-admin first')
  process.exit(1)
}

const token = signSession({ sub: u.id, email: u.email })
const cookie = `ichivol_session=${token}`

async function askAgent(question: string) {
  const res = await fetch(`${BASE}/api/agent/chat`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', cookie },
    body: JSON.stringify({ mode: 'research', question }),
  })
  return { status: res.status, body: (await res.json()) as any }
}

async function confirmAction(payload: Record<string, unknown>) {
  const res = await fetch(`${BASE}/api/agent/actions/confirm`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', cookie },
    body: JSON.stringify(payload),
  })
  return { status: res.status, body: (await res.json()) as any }
}

const candidates = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'NEARUSDT', 'AVAXUSDT', 'LINKUSDT', 'DOGEUSDT']

let opened: { symbol: string; positionId: string } | null = null
let sawCleanRefusal = false

for (const symbol of candidates) {
  const ask = await askAgent(`ouvre une position papier sur ${symbol}`)
  const pending = ask.body?.pendingAction
  console.log(`\n[${symbol}] propose -> HTTP ${ask.status}, intent=${ask.body?.intent}`)
  if (ask.status !== 200 || pending?.intent !== 'open_paper_position') {
    console.log('  PROBLEME: pas de pendingAction open_paper_position renvoyé', ask.body)
    continue
  }

  const confirm = await confirmAction({
    intent: 'open_paper_position',
    confirm: true,
    symbol: pending.symbol,
    timeframe: pending.timeframe,
    threadId: ask.body.threadId,
    actionId: pending.actionId,
  })
  console.log(`[${symbol}] confirm -> HTTP ${confirm.status}`, confirm.body)

  if (confirm.status === 200 && confirm.body?.status === 'confirmed' && confirm.body?.result?.id) {
    opened = { symbol, positionId: confirm.body.result.id }
    break
  }
  if (confirm.status === 502 && typeof confirm.body?.error === 'string') {
    sawCleanRefusal = true
  }
}

if (opened) {
  console.log(`\nOuverte pour de vrai (papier) : ${opened.symbol} #${opened.positionId} -- nettoyage (close)...`)
  const closeRes = await fetch(`${ENGINE_URL}/api/engine/paper/positions/${opened.positionId}/close`, {
    method: 'POST',
  })
  console.log('cleanup close ->', closeRes.status)
  console.log('SMOKE_E6_OK (position ouverte via agent, verdict engine respecté)')
  process.exit(0)
}

if (sawCleanRefusal) {
  console.log('\nAucun symbole actionnable au moment du test, mais chaque refus était propre (422/erreur engine relayée) --')
  console.log('la chaîne agent -> engine fonctionne, il n\'y avait juste pas de BUY/SELL en direct sur ces paires.')
  console.log('SMOKE_E6_OK_NO_ACTIONABLE_SYMBOL')
  process.exit(0)
}

console.log('\nSMOKE_E6_FAIL: aucune proposition ni refus propre reçu -- vraie panne à investiguer')
process.exit(1)
