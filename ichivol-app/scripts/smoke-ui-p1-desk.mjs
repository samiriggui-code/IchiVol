/**
 * UI-P1 Desk smoke — desktop + mobile 390px.
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
const OUT = '/tmp/ui-p1-desk'
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
  await new Promise((r) => setTimeout(r, 2800))
  const overflow = await page.evaluate(() => {
    const doc = document.documentElement
    return {
      scrollWidth: Math.max(doc.scrollWidth, document.body.scrollWidth),
      clientWidth: doc.clientWidth,
    }
  })
  const titles = await page.evaluate(() =>
    [...document.querySelectorAll('h1, h2')].map((el) => (el.textContent || '').trim()).slice(0, 30),
  )
  const bodyText = await page.evaluate(() => document.body.innerText.slice(0, 8000))
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

  const deskPage = await browser.newPage()
  await deskPage.setViewport({ width: 1440, height: 900 })
  await login(deskPage)
  const deskDesktop = await collectPage(deskPage, 'desk', '01-desk-desktop')
  report.pages.deskDesktop = deskDesktop
  if (!deskDesktop.pass) report.pass = false
  console.log('[desk desktop]', deskDesktop.pass ? 'PASS' : 'FAIL', deskDesktop.titles.slice(0, 14), deskDesktop.apiErrors)

  const p1b = await deskPage.evaluate(() => {
    const text = document.body.innerText
    const statusEls = [...document.querySelectorAll('.session-status')]
    const statusClasses = statusEls.map((el) => el.className)
    const hours = document.querySelector('#desk-session-detail .mono')?.textContent || ''
    const links = [...document.querySelectorAll('.desk-workspace a.link')].map((a) =>
      getComputedStyle(a).color,
    )
    return {
      hasCap: /Capitalisation crypto 24h/.test(text),
      hasFakeVol: /Volatilité \(mcap/.test(text),
      statusClasses,
      hours,
      linkColors: links.slice(0, 3),
      hasCommaPct: /\d+,\d+\s*%/.test(text),
    }
  })
  const p1bOk =
    p1b.hasCap &&
    !p1b.hasFakeVol &&
    p1b.statusClasses.some((c) => /is-(open|closed|upcoming)/.test(c)) &&
    !/[AP]M/.test(p1b.hours)
  if (!p1bOk) report.pass = false
  report.pages.p1bChecks = p1b
  console.log('[desk p1b]', p1bOk ? 'PASS' : 'FAIL', p1b)

  await deskPage.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true })
  const deskMobile = await collectPage(deskPage, 'desk', '02-desk-mobile-390')
  report.pages.deskMobile = deskMobile
  if (!deskMobile.pass) report.pass = false
  console.log('[desk mobile]', deskMobile.pass ? 'PASS' : 'FAIL', deskMobile.overflow, deskMobile.apiErrors)

  await deskPage.setViewport({ width: 1280, height: 900, isMobile: false, hasTouch: false })
  for (const [route, file, needle] of [
    ['opportunites', '03-opportunites-pulse', 'Market pulse'],
    ['operations', '04-operations-relocated', 'Pipeline health'],
    ['portefeuille', '05-portefeuille-labs', 'Labs paper'],
  ]) {
    const r = await collectPage(deskPage, route, file)
    const has =
      r.titles.some((t) => t.toLowerCase().includes(needle.toLowerCase())) ||
      r.bodyText.toLowerCase().includes(needle.toLowerCase())
    r.relocatedVisible = has
    if (!r.pass || !has) report.pass = false
    report.pages[route] = r
    console.log(`[${route}]`, r.pass && has ? 'PASS' : 'FAIL', 'visible=', has, r.apiErrors)
  }

  fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify(report, null, 2))
  await browser.close()
  console.log('\n=== UI-P1 DESK SUMMARY ===', report.pass ? 'PASS' : 'FAIL')
  process.exit(report.pass ? 0 : 1)
}

main().catch((e) => {
  console.error(e)
  process.exit(2)
})
