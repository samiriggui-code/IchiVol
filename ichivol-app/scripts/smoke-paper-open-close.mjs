/**
 * Smoke paper open → close with screenshots.
 * Usage: APP_BASE=… SMOKE_EMAIL=… SMOKE_PASS=… node scripts/smoke-paper-open-close.mjs
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import puppeteer from 'puppeteer-core'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const REPO = path.resolve(HERE, '../..')
const OUT = path.join(REPO, 'docs/ui-port/captures')
const APP_BASE = process.env.APP_BASE ?? 'http://127.0.0.1:5180'
const EMAIL = process.env.SMOKE_EMAIL
const PASS = process.env.SMOKE_PASS
const CHROME =
  process.env.CHROME ??
  ['/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'].find((p) =>
    fs.existsSync(p),
  )

if (!EMAIL || !PASS) {
  console.error('SMOKE_EMAIL / SMOKE_PASS required')
  process.exit(2)
}
if (!CHROME) {
  console.error('Chrome not found')
  process.exit(2)
}

fs.mkdirSync(OUT, { recursive: true })

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1440,900'],
})
const page = await browser.newPage()
await page.setViewport({ width: 1440, height: 900 })

const shot = async (name) => {
  const p = path.join(OUT, `paper-${name}.png`)
  await page.screenshot({ path: p, fullPage: false })
  console.log('shot', p)
  return p
}

const report = { ok: false, steps: [], error: null }

try {
  await page.goto(`${APP_BASE}/login`, { waitUntil: 'networkidle2', timeout: 90000 })
  await page.type('input[type=email], input[name=email]', EMAIL, { delay: 10 })
  await page.type('input[type=password], input[name=password]', PASS, { delay: 10 })
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 90000 }).catch(() => null),
    page.click('button[type=submit]'),
  ])
  report.steps.push('login')

  // Prefer BTC for paper smoke (engine fixtures reliable)
  const fullSym = 'BTCUSDT'
  report.steps.push(`symbol=${fullSym}`)

  await page.goto(
    `${APP_BASE}/app/opportunites?symbol=${encodeURIComponent(fullSym)}&open=1`,
    { waitUntil: 'networkidle2', timeout: 90000 },
  )
  await page.waitForSelector('dialog#detail', { timeout: 30000 })
  await page.evaluate(() => {
    const d = document.querySelector('dialog#detail')
    if (d && !d.open) d.showModal()
  })
  // Wait detail load (primary enabled)
  await page.waitForFunction(
    () => {
      const btn = document.querySelector('dialog#detail button.primary')
      return btn && !btn.disabled && /position paper|Déjà ouvert/i.test(btn.textContent || '')
    },
    { timeout: 60000 },
  )
  await shot('01-dialog-open')
  report.steps.push('dialog')

  const openLabel = await page.$eval('dialog#detail button.primary', (el) => el.textContent.trim())
  if (/Déjà ouvert/i.test(openLabel)) {
    report.steps.push('already-open-skip-to-close')
  } else {
    await page.click('dialog#detail button.primary')
    await page.waitForSelector('.paper-confirm-backdrop', { timeout: 45000 })
    await shot('02-confirm-sheet')
    report.steps.push('confirm-sheet')

    await page.waitForFunction(
      () => {
        const btn = document.querySelector('.paper-confirm-actions button')
        return (
          btn &&
          !btn.disabled &&
          /Confirmer l’achat|Confirmer l'achat/i.test(btn.textContent || '')
        )
      },
      { timeout: 60000 },
    )
    await page.evaluate(() => {
      const btn = [...document.querySelectorAll('.paper-confirm-actions button')].find((b) =>
        /Confirmer/i.test(b.textContent || ''),
      )
      btn?.click()
    })
    await page.waitForFunction(
      () => !document.querySelector('.paper-confirm-backdrop'),
      { timeout: 90000 },
    )
    await new Promise((r) => setTimeout(r, 800))
    await shot('03-after-open')
    report.steps.push('opened')
  }

  await page.goto(`${APP_BASE}/app/portefeuille`, { waitUntil: 'networkidle2', timeout: 90000 })
  await page.waitForSelector('.pf-page', { timeout: 30000 })
  await shot('04-portefeuille')

  const closeBtn = await page.$('.pf-close-btn')
  if (!closeBtn) throw new Error('no open position to close (Fermer button missing)')
  await closeBtn.click()
  await page.waitForSelector('.paper-confirm-backdrop', { timeout: 15000 })
  await shot('05-close-confirm')
  report.steps.push('close-confirm')

  await page.waitForFunction(
    () => {
      const btns = [...document.querySelectorAll('.paper-confirm-actions button')]
      return btns.some((b) => /Confirmer la clôture/i.test(b.textContent || '') && !b.disabled)
    },
    { timeout: 15000 },
  )
  await page.evaluate(() => {
    const btn = [...document.querySelectorAll('.paper-confirm-actions button')].find((b) =>
      /Confirmer la clôture/i.test(b.textContent || ''),
    )
    btn?.click()
  })
  await page.waitForFunction(
    () => !document.querySelector('.paper-confirm-backdrop'),
    { timeout: 60000 },
  )
  await page.waitForTimeout?.(1500)
  await new Promise((r) => setTimeout(r, 1500))
  await shot('06-after-close')
  report.steps.push('closed')
  report.ok = true
} catch (e) {
  report.error = e instanceof Error ? e.message : String(e)
  try {
    await shot('FAIL')
  } catch {
    /* ignore */
  }
} finally {
  const outJson = path.join(OUT, 'smoke-paper-open-close.json')
  fs.writeFileSync(outJson, JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report, null, 2))
  await browser.close()
  process.exit(report.ok ? 0 : 1)
}
