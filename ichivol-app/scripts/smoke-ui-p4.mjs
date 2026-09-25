/**
 * UI-P4 smoke — Marché, Lab, Contexte, Copilot, Agents, Paramètres
 * desktop 1440 + mobile 390. Requires SMOKE_EMAIL + SMOKE_PASS.
 */
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const puppeteer = require('puppeteer-core')

const BASE = process.env.SMOKE_BASE || 'http://127.0.0.1:5178'
const EMAIL = process.env.SMOKE_EMAIL
const PASS = process.env.SMOKE_PASS
if (!EMAIL || !PASS) {
  console.error('SMOKE_EMAIL et SMOKE_PASS obligatoires.')
  process.exit(2)
}
const OUT = '/tmp/ui-p4'
fs.mkdirSync(OUT, { recursive: true })

const P4_ROUTES = [
  ['market', 'Marché', ['Marché']],
  ['strategy-lab', 'Strategy Lab', ['Strategy Lab']],
  ['context', 'Contexte', ['Contexte']],
  ['agent', 'Copilot', ['Copilot']],
  ['agents', 'Agents', ['Agents']],
  ['settings', 'Paramètres', ['Paramètres', 'Parametres']],
]

const ALL_11 = [
  'desk',
  'market',
  'opportunites',
  'portefeuille',
  'strategy-lab',
  'journal',
  'context',
  'agent',
  'agents',
  'operations',
  'settings',
]

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
    if (/422|llm-test|Unprocessable Entity|favicon/i.test(t)) return
    consoleErrors.push(t.slice(0, 200))
  }
  page.on('response', onRes)
  page.on('console', onConsole)
  await page.goto(`${BASE}/app/${route}`, { waitUntil: 'domcontentloaded', timeout: 60000 })
  await new Promise((r) => setTimeout(r, 3500))
  const meta = await page.evaluate(() => {
    const doc = document.documentElement
    const overflow = {
      scrollWidth: Math.max(doc.scrollWidth, document.body.scrollWidth),
      clientWidth: doc.clientWidth,
    }
    const titles = [...document.querySelectorAll('h1, h2')]
      .map((el) => (el.textContent || '').trim())
      .slice(0, 40)
    const bodyText = document.body.innerText.slice(0, 8000)
    const paperPill = Boolean(document.querySelector('.dash-paper-pill'))
    const paperText = (document.querySelector('.dash-paper-pill')?.textContent || '').trim()
    return { overflow, titles, bodyText, paperPill, paperText }
  })
  page.off('response', onRes)
  page.off('console', onConsole)
  const pass =
    apiErrors.length === 0 &&
    consoleErrors.length === 0 &&
    meta.overflow.scrollWidth <= meta.overflow.clientWidth + 1
  await page.screenshot({ path: path.join(OUT, `${label}.png`), fullPage: false })
  return { route, pass, apiErrors, consoleErrors, ...meta }
}

async function main() {
  const browser = await puppeteer.launch({
    executablePath: '/usr/bin/google-chrome-stable',
    headless: true,
    args: ['--no-sandbox', '--disable-gpu'],
  })
  const report = { pass: true, pages: {}, paperPill: null, global11: {} }
  const page = await browser.newPage()
  await page.setViewport({ width: 1440, height: 900 })
  await login(page)

  for (const [route, name, needles] of P4_ROUTES) {
    const file = `desktop-${route}`
    const r = await collectPage(page, route, file)
    const text = `${r.titles.join(' ')} ${r.bodyText}`
    const has = needles.some((n) => text.includes(n))
    r.hasNeedles = has
    if (!r.pass || !has) report.pass = false
    if (!r.paperPill || r.paperText !== 'PAPER') report.pass = false
    report.pages[file] = { pass: r.pass && has, paperPill: r.paperPill, paperText: r.paperText, titles: r.titles.slice(0, 8), apiErrors: r.apiErrors, consoleErrors: r.consoleErrors, overflow: r.overflow }
    console.log(`[${file}]`, r.pass && has ? 'PASS' : 'FAIL', r.paperText, r.apiErrors)
  }
  report.paperPill = report.pages['desktop-market']?.paperText

  await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true })
  for (const [route] of P4_ROUTES) {
    const file = `mobile390-${route}`
    const r = await collectPage(page, route, file)
    if (!r.pass) report.pass = false
    report.pages[file] = { pass: r.pass, overflow: r.overflow, apiErrors: r.apiErrors, consoleErrors: r.consoleErrors, paperPill: r.paperPill }
    console.log(`[${file}]`, r.pass ? 'PASS' : 'FAIL', r.overflow, r.apiErrors)
  }

  // Global 11 + Plus panel
  await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true })
  for (const route of ALL_11) {
    const r = await collectPage(page, route, `global-${route}`)
    report.global11[route] = { pass: r.pass, api: r.apiErrors.length, console: r.consoleErrors.length }
    if (!r.pass) report.pass = false
    console.log(`[global ${route}]`, r.pass ? 'PASS' : 'FAIL', r.apiErrors)
  }
  // Ensure we are on a mobile shell page with tabbar
  await page.goto(`${BASE}/app/desk`, { waitUntil: 'domcontentloaded', timeout: 60000 })
  await new Promise((r) => setTimeout(r, 1500))
  const plusOk = await page.evaluate(() => {
    const btn = [...document.querySelectorAll('button.dash-mobile-tab, a.dash-mobile-tab')].find((el) =>
      (el.textContent || '').includes('Plus'),
    )
    if (!btn) return { open: false, error: 'no Plus tab', links: [] }
    btn.click()
    const links = [...document.querySelectorAll('.dash-mobile-more a, .dash-mobile-more-link')]
      .map((a) => (a.textContent || '').trim())
      .filter(Boolean)
    return { open: links.length >= 3, links: links.slice(0, 12) }
  })
  report.plus = plusOk
  if (!plusOk.open) report.pass = false
  await page.screenshot({ path: path.join(OUT, 'mobile-plus-panel.png'), fullPage: false })

  fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify(report, null, 2))
  await browser.close()
  console.log('\n=== UI-P4 SUMMARY ===', report.pass ? 'PASS' : 'FAIL')
  process.exit(report.pass ? 0 : 1)
}

main().catch((e) => {
  console.error(e)
  process.exit(2)
})
