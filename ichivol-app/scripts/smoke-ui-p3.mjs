/**
 * UI-P3 smoke — Journal + Opérations, desktop + mobile 390.
 * Requires SMOKE_EMAIL + SMOKE_PASS.
 */
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const puppeteer = require('puppeteer-core')

const BASE = process.env.SMOKE_BASE || 'http://127.0.0.1:5173'
const EMAIL = process.env.SMOKE_EMAIL
const PASS = process.env.SMOKE_PASS
if (!EMAIL || !PASS) {
  console.error('SMOKE_EMAIL et SMOKE_PASS obligatoires.')
  process.exit(2)
}
const OUT = '/tmp/ui-p3'
fs.mkdirSync(OUT, { recursive: true })

function isIgnorableApi(url, status) {
  if (status === 422 && url.includes('/api/settings/llm-test')) return true
  return false
}

async function login(page) {
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle2', timeout: 60000 })
  if (page.url().includes('/app')) return
  const emailSel =
    (await page.$('input[type="email"]')) ||
    (await page.$('input[name="email"]')) ||
    (await page.$('input[type="text"]'))
  const passSel = await page.$('input[type="password"]')
  if (!emailSel || !passSel) {
    await page.waitForFunction(() => location.pathname.startsWith('/app'), { timeout: 10000 }).catch(() => null)
    if (page.url().includes('/app')) return
    throw new Error('login form not found')
  }
  await emailSel.click({ clickCount: 3 })
  await emailSel.type(EMAIL, { delay: 5 })
  await passSel.click({ clickCount: 3 })
  await passSel.type(PASS, { delay: 5 })
  await Promise.all([
    page.click('button[type="submit"]'),
    page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 30000 }).catch(() => null),
  ])
  await page.waitForFunction(() => location.pathname.startsWith('/app'), { timeout: 20000 })
}

async function collectPage(page, route, label) {
  const apiErrors = []
  const consoleErrors = []
  const onRes = (res) => {
    const u = res.url()
    if (!u.includes('/api/')) return
    if (res.status() >= 400 && !isIgnorableApi(u, res.status())) {
      apiErrors.push({ status: res.status(), url: u.slice(0, 140) })
    }
  }
  const onConsole = (msg) => {
    if (msg.type() !== 'error') return
    const t = msg.text()
    if (/422|llm-test|Unprocessable Entity/i.test(t)) return
    consoleErrors.push(t.slice(0, 200))
  }
  page.on('response', onRes)
  page.on('console', onConsole)
  await page.goto(`${BASE}/app/${route}`, { waitUntil: 'networkidle2', timeout: 90000 })
  await new Promise((r) => setTimeout(r, 3200))
  const overflow = await page.evaluate(() => {
    const doc = document.documentElement
    return {
      scrollWidth: Math.max(doc.scrollWidth, document.body.scrollWidth),
      clientWidth: doc.clientWidth,
    }
  })
  const titles = await page.evaluate(() =>
    [...document.querySelectorAll('h1, h2')].map((el) => (el.textContent || '').trim()).slice(0, 40),
  )
  const bodyText = await page.evaluate(() => document.body.innerText.slice(0, 12000))
  page.off('response', onRes)
  page.off('console', onConsole)
  const pass =
    apiErrors.length === 0 &&
    consoleErrors.length === 0 &&
    overflow.scrollWidth <= overflow.clientWidth + 1
  await page.screenshot({ path: path.join(OUT, `${label}.png`), fullPage: true })
  return { route, pass, apiErrors, consoleErrors, overflow, titles, bodyText }
}

async function main() {
  const browser = await puppeteer.launch({
    executablePath: '/usr/bin/google-chrome-stable',
    headless: true,
    args: ['--no-sandbox', '--disable-gpu'],
  })
  const report = { pass: true, pages: {} }
  const page = await browser.newPage()
  await page.setViewport({ width: 1440, height: 900 })
  await login(page)

  for (const [route, file, needles] of [
    ['journal', '01-journal-desktop', ['Trades', 'Décisions', 'Journal']],
    [
      'operations',
      '02-operations-desktop',
      ['Journal d’audit', "Journal d'audit", 'Qualité des données', 'Ce que la trace explique'],
    ],
  ]) {
    const r = await collectPage(page, route, file)
    const text = `${r.titles.join(' ')} ${r.bodyText}`
    const has = needles.some((n) => text.includes(n))
    r.hasNeedles = has
    if (!r.pass || !has) report.pass = false
    report.pages[file] = r
    console.log(`[${file}]`, r.pass && has ? 'PASS' : 'FAIL', r.titles.slice(0, 10), r.apiErrors)
  }

  const p3 = await page.evaluate(() => {
    const text = document.body.innerText
    return {
      hasAudit: /Journal d.audit/.test(text),
      hasQuality: /Qualité des données/.test(text),
      hasTrace: /Ce que la trace explique/.test(text),
      hasLevels: /PASSE|PRUDENCE|REFUS/.test(text),
      hasDemoArmed: /\bARMED\b|\bTRIGGERED\b/.test(text),
    }
  })
  const p3Ok = p3.hasAudit && p3.hasQuality && p3.hasTrace && !p3.hasDemoArmed
  if (!p3Ok) report.pass = false
  report.pages.p3Checks = p3
  console.log('[p3 checks]', p3Ok ? 'PASS' : 'FAIL', p3)

  await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true })
  for (const [route, file] of [
    ['journal', '03-journal-mobile-390'],
    ['operations', '04-operations-mobile-390'],
  ]) {
    const r = await collectPage(page, route, file)
    if (!r.pass) report.pass = false
    report.pages[file] = r
    console.log(`[${file}]`, r.pass ? 'PASS' : 'FAIL', r.overflow, r.apiErrors)
  }

  fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify(report, null, 2))
  await browser.close()
  console.log('\n=== UI-P3 SUMMARY ===', report.pass ? 'PASS' : 'FAIL')
  process.exit(report.pass ? 0 : 1)
}

main().catch((e) => {
  console.error(e)
  process.exit(2)
})
