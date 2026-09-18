import nodemailer, { type Transporter } from 'nodemailer'
import { config } from '../config.js'

let transporter: Transporter | null = null
let warnedMissingConfig = false

/** Lazy singleton -- SMTP settings may not be configured (dev, or before
 * the operator fills deploy/vps/.env), in which case sendMail() below just
 * logs and returns false instead of throwing. */
function getTransporter(): Transporter | null {
  if (!config.smtp.host || !config.smtp.user || !config.smtp.password) {
    if (!warnedMissingConfig) {
      console.warn('[mailer] SMTP_HOST/SMTP_USER/SMTP_PASSWORD non configurés -- emails désactivés.')
      warnedMissingConfig = true
    }
    return null
  }
  if (!transporter) {
    transporter = nodemailer.createTransport({
      host: config.smtp.host,
      port: config.smtp.port,
      secure: config.smtp.secure,
      auth: { user: config.smtp.user, pass: config.smtp.password },
    })
  }
  return transporter
}

/** Never throws -- a failed/missing SMTP config must not crash the
 * watchdog/digest job that's trying to report a problem in the first
 * place. Returns whether the mail was actually sent. */
export async function sendMail(input: { to: string; subject: string; html: string }): Promise<boolean> {
  const t = getTransporter()
  if (!t) return false
  try {
    await t.sendMail({ from: config.smtp.from, to: input.to, subject: input.subject, html: input.html })
    return true
  } catch (err) {
    console.error('[mailer] envoi échoué:', err instanceof Error ? err.message : err)
    return false
  }
}
