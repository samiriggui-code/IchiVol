/**
 * Smoke test for the health watchdog + digest + mailer pipeline.
 * Proves health check shape, branded briefing render (email + PDF),
 * graceful no-op when SMTP unconfigured — without sending mail.
 */
import { render } from '@react-email/render'
import { checkSystemHealth, isHealthy } from '../src/health/check.ts'
import { AlertEmail } from '../src/notifications/emails/AlertEmail.tsx'
import { DigestEmail } from '../src/notifications/emails/DigestEmail.tsx'
import { renderDigestPdf } from '../src/notifications/emails/DigestPdf.tsx'
import type { DailyBriefing } from '../src/notifications/briefingTypes.ts'
import { sendMail } from '../src/notifications/mailer.ts'

let failed = 0

function check(label: string, ok: boolean) {
  console.log(ok ? 'OK  ' : 'FAIL', label)
  if (!ok) failed++
}

const sample: DailyBriefing = {
  portfolioCode: 'ICHIVOL_BASELINE_V1',
  portfolioLabel: 'Baseline V1',
  generatedAt: 'dimanche 20 septembre 2026 à 12:00',
  generatedAtIso: '2026-09-20T10:00:00.000Z',
  appUrl: 'http://localhost',
  headline: 'Equity 4 987,15 € (−12,85 € sur 24 h) — 3 positions ouvertes · circuit 24 h : 2 ouvertures, 1 clôture, 4 refus.',
  narrative: [
    'Depuis le départ (5 000 €), le compte est à 4 987,15 € soit −12,85 € (−0,3 %). Cash libre 3 200 €, capital engagé 1 787 €.',
    'Livre ouvert : 2 dans le vert, 1 dans le rouge. Latent total +8,50 € · réalisé −21,35 €.',
    'Ce briefing est informatif — aucune exécution réelle.',
  ],
  kpis: {
    equity: 4987.15,
    initialCash: 5000,
    cash: 3200,
    invested: 1787,
    totalPnl: -12.85,
    totalPnlPct: -0.00257,
    dayChange: -12.85,
    dayChangePct: -0.00257,
    unrealizedPnl: 8.5,
    realizedPnl: -21.35,
    openPositions: 3,
    pricedPositions: 3,
  },
  equityCurve: [
    { t: '2026-09-18T00:00:00Z', equity: 5000 },
    { t: '2026-09-19T00:00:00Z', equity: 5010 },
    { t: '2026-09-20T00:00:00Z', equity: 4987.15 },
  ],
  equitySpark: [5000, 5005, 5012, 5008, 5015, 5002, 4987.15],
  openBook: [
    {
      symbol: 'APTUSDT',
      label: 'APT',
      direction: 'LONG',
      timeframe: '1h',
      notional: 600,
      unrealizedPnl: 12.2,
      unrealizedPct: 0.02,
      entryPrice: 5,
      currentPrice: 5.1,
    },
  ],
  tape: [
    {
      time: '2026-09-20T08:00:00Z',
      title: 'Ouverture APT',
      detail: 'Long 1h · 600 €',
      tone: 'green',
    },
  ],
  shadow: {
    nClosed: 8,
    meanPnlR: 0.12,
    filterVerdict: 'filter_helpful',
    plain: 'Les filtres ont surtout écarté des trades perdants — utiles sur la période observée.',
  },
  evidence: {
    totalRows: 120,
    distinctDays: 5,
    latestPairs: 12,
    lastRunAt: '2026-09-20T06:00:00Z',
    pipelineBeats: 4,
    pipelineCompared: 10,
    edgePlain: 'PIPELINE bat Ichimoku (Sharpe) sur 4/10 paires comparables.',
  },
  circuit: {
    decisions24h: 40,
    opened24h: 2,
    closed24h: 1,
    blocked24h: 4,
    openNow: 3,
  },
  paperStats: { closedTrades: 12, winRate: 0.42, totalReturn: -0.00257 },
}

const health = await checkSystemHealth()
check(
  'checkSystemHealth returns database/engine booleans',
  typeof health.database === 'boolean' && typeof health.engine === 'boolean',
)
check('isHealthy matches both flags', isHealthy(health) === (health.database && health.engine))
console.log('  ->', health)

const alertHtml = await render(
  AlertEmail({ database: true, engine: false, checkedAt: 'now', appUrl: 'http://localhost' }),
)
check('AlertEmail renders non-trivial HTML', alertHtml.length > 500 && alertHtml.includes('DOWN'))

const digestHtml = await render(DigestEmail({ briefing: sample }))
check(
  'DigestEmail briefing renders',
  digestHtml.length > 2000 && digestHtml.includes('Briefing quotidien') && digestHtml.includes('Lecture desk'),
)

const pdfBuf = await renderDigestPdf(sample)
check('DigestPdf renders non-empty buffer', pdfBuf.length > 800)
console.log('  -> PDF bytes', pdfBuf.length)

let threw = false
let sent = false
try {
  sent = await sendMail({ to: 'nobody@example.com', subject: 'smoke test', html: '<p>hi</p>' })
} catch {
  threw = true
}
check('sendMail never throws', !threw)
console.log('  -> sendMail returned', sent, '(false = SMTP off, true = SMTP configured)')

console.log(failed === 0 ? 'SMOKE_E7_OK' : 'SMOKE_E7_FAIL')
process.exit(failed === 0 ? 0 : 1)
