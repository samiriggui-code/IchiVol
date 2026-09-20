/**
 * Periodic desk briefing (CDC notifications) — daily by default.
 * Fetches paper overview + activity + shadow + evidence, renders a branded
 * React Email + PDF attachment. Informational only; never decides trades.
 */
import { render } from '@react-email/render'
import { config } from '../config.js'
import { db } from '../db.js'
import { buildDailyBriefing } from './buildBriefing.js'
import { DigestEmail } from './emails/DigestEmail.js'
import { renderDigestPdf } from './emails/DigestPdf.js'
import { sendMail } from './mailer.js'

let timer: NodeJS.Timeout | null = null

async function runDigestCycle(): Promise<void> {
  let briefing
  try {
    briefing = await buildDailyBriefing()
  } catch (err) {
    console.error('[digest] buildDailyBriefing failed:', err instanceof Error ? err.message : err)
    return
  }

  const edgeSummary = briefing.evidence
    ? `${briefing.evidence.pipelineBeats}/${briefing.evidence.pipelineCompared}`
    : 'n/a'
  const notifBody = `${briefing.headline} Edge PIPELINE vs Ichimoku : ${edgeSummary}.`

  try {
    const users = await db.user.findMany({ select: { id: true } })
    await Promise.all(
      users.map((u) =>
        db.notification.create({
          data: {
            userId: u.id,
            kind: 'system_digest',
            title: 'Briefing quotidien',
            body: notifBody.slice(0, 480),
          },
        }),
      ),
    )
  } catch (err) {
    console.error('[digest] notification create failed:', err instanceof Error ? err.message : err)
  }

  if (!config.alertEmailTo) return

  try {
    const html = await render(DigestEmail({ briefing }))
    let pdfBuf: Buffer | null = null
    try {
      pdfBuf = await renderDigestPdf(briefing)
    } catch (err) {
      console.error('[digest] PDF render failed (email sans PJ):', err instanceof Error ? err.message : err)
    }

    const day = briefing.generatedAtIso.slice(0, 10)
    const subject = `IchiVol Briefing — ${day} · equity ${briefing.kpis.equity.toFixed(0)} €`
    await sendMail({
      to: config.alertEmailTo,
      subject,
      html,
      attachments: pdfBuf
        ? [
            {
              filename: `IchiVol-Briefing-${day}.pdf`,
              content: pdfBuf,
              contentType: 'application/pdf',
            },
          ]
        : undefined,
    })
  } catch (err) {
    console.error('[digest] email failed:', err instanceof Error ? err.message : err)
  }
}

export function startDigestJob(): void {
  if (timer) return
  // Premier envoi ~2 min après boot (sinon un redémarrage remettait le
  // compteur à 24 h et on ne voyait plus de mails / notifs digest).
  const BOOT_DELAY_MS = 120_000
  setTimeout(() => void runDigestCycle(), BOOT_DELAY_MS)
  timer = setInterval(() => void runDigestCycle(), config.digestIntervalMs)
}

export function stopDigestJob(): void {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

/** Manual / smoke trigger. */
export { runDigestCycle }
