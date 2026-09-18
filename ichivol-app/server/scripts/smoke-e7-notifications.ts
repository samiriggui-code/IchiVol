/**
 * Smoke test for the health watchdog + digest + mailer pipeline
 * (2026-09-17 "notifications/alertes"). Doesn't require real SMTP creds --
 * proves the pipeline itself (health check shape, template rendering,
 * graceful no-op when unconfigured) without actually sending mail.
 */
import { render } from '@react-email/render'
import { checkSystemHealth, isHealthy } from '../src/health/check.ts'
import { AlertEmail } from '../src/notifications/emails/AlertEmail.tsx'
import { DigestEmail } from '../src/notifications/emails/DigestEmail.tsx'
import { sendMail } from '../src/notifications/mailer.ts'

let failed = 0

function check(label: string, ok: boolean) {
  console.log(ok ? 'OK  ' : 'FAIL', label)
  if (!ok) failed++
}

const health = await checkSystemHealth()
check('checkSystemHealth returns database/engine booleans', typeof health.database === 'boolean' && typeof health.engine === 'boolean')
check('isHealthy matches both flags', isHealthy(health) === (health.database && health.engine))
console.log('  ->', health)

const alertHtml = await render(
  AlertEmail({ database: true, engine: false, checkedAt: 'now', appUrl: 'http://localhost' }),
)
check('AlertEmail renders non-trivial HTML', alertHtml.length > 500 && alertHtml.includes('DOWN'))

const digestHtml = await render(
  DigestEmail({
    appUrl: 'http://localhost',
    generatedAt: 'now',
    paper: { numOpenPositions: 1, numClosedTrades: 2, totalReturn: 0.01, winRate: 0.5 },
    evidence: {
      totalRows: 10, distinctDays: 1, latestPairs: 2, lastRunAt: null,
      pipelineBeatsIchimokuSharpe: { beats: 1, compared: 2 },
    },
  }),
)
check('DigestEmail renders non-trivial HTML', digestHtml.length > 500 && digestHtml.includes('1/2'))

// No SMTP configured in this dev environment -- must degrade to `false`,
// never throw (a watchdog/digest tick must survive a missing/broken SMTP
// config, since it's often reporting exactly that kind of misconfiguration).
const sent = await sendMail({ to: 'nobody@example.com', subject: 'smoke test', html: '<p>hi</p>' })
check('sendMail degrades to false without SMTP config (no throw)', sent === false)

console.log(failed === 0 ? 'SMOKE_E7_OK' : 'SMOKE_E7_FAIL')
process.exit(failed === 0 ? 0 : 1)
