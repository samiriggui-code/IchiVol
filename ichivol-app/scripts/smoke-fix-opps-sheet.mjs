/**
 * Fix Opportunités sheet mobile 390 — open 3 symbols, scroll, close via
 * Retour / history.back / re-tap tab. Captures → /tmp/fix-opps-sheet/
 */
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const puppeteer = require('puppeteer-core')

const BASE = process.env.SMOKE_BASE || 'http://127.0.0.1:5177'
const EMAIL = process.env.SMOKE_EMAIL
const PASS = process.env.SMOKE_PASS
if (!EMAIL || !PASS) {
  console.error('SMOKE_EMAIL et SMOKE_PASS obligatoires.')
  process.exit(2)
}
const OUT = '/tmp/fix-opps-sheet'
fs.mkdirSync(OUT, { recursive: true })

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

async function openFirstRows(page, n) {
  await page.goto(`${BASE}/app/opportunites`, { waitUntil: 'networkidle2', timeout: 90000 })
  await new Promise((r) => setTimeout(r, 2500))
  const symbols = await page.evaluate((count) => {
    const rows = [...document.querySelectorAll('.decisions-table tbody tr, .gate-matrix tbody tr')]
    const out = []
    for (const tr of rows) {
      const t = (tr.textContent || '').trim()
      const m = t.match(/[A-Z0-9]{3,15}/)
      if (m) out.push(m[0])
      if (out.length >= count) break
    }
    return out
  }, n)
  return symbols
}

async function sheetState(page) {
  return page.evaluate(() => {
    const pageEl = document.querySelector('.decisions-page')
    const sheet = document.querySelector('.decision-sheet')
    const chrome = document.querySelector('.decisions-chrome')
    const retour = document.querySelector('.decision-sheet-close')
    const ribbon = document.querySelector('.opp-ribbon')
    const url = location.href
    const sheetOpen = pageEl?.classList.contains('is-sheet-open') ?? false
    let chromeHidden = true
    if (chrome) {
      const cs = getComputedStyle(chrome)
      chromeHidden = cs.display === 'none' || cs.visibility === 'hidden'
    }
    let ribbonHidden = true
    if (ribbon) {
      const cs = getComputedStyle(ribbon)
      ribbonHidden = cs.display === 'none' || !ribbon.offsetParent
    }
    let scrollOk = false
    const scroll = document.querySelector('.decision-sheet-scroll')
    if (scroll) {
      scroll.scrollTop = scroll.scrollHeight
      scrollOk = scroll.scrollTop > 0 || scroll.scrollHeight <= scroll.clientHeight + 2
    }
    const retourVisible = Boolean(retour && retour.getBoundingClientRect().bottom > 0 && retour.getBoundingClientRect().top < innerHeight)
    return {
      sheetOpen,
      hasSheet: Boolean(sheet),
      chromeHidden,
      ribbonHidden,
      scrollOk,
      retourVisible,
      retourLabel: (retour?.textContent || '').trim(),
      url,
      hasSymbolQ: new URL(url).searchParams.has('symbol'),
    }
  })
}

async function main() {
  const browser = await puppeteer.launch({
    executablePath: '/usr/bin/google-chrome-stable',
    headless: true,
    args: ['--no-sandbox', '--disable-gpu'],
  })
  const report = { pass: true, closes: {}, symbols: [] }
  const page = await browser.newPage()
  await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true })
  await login(page)

  // BEFORE capture of list
  await page.goto(`${BASE}/app/opportunites`, { waitUntil: 'networkidle2', timeout: 90000 })
  await new Promise((r) => setTimeout(r, 2200))
  await page.screenshot({ path: path.join(OUT, '00-list-before.png'), fullPage: true })

  const symbols = await openFirstRows(page, 3)
  report.symbols = symbols
  if (symbols.length < 1) {
    report.pass = false
    report.error = 'no symbols in table'
    fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify(report, null, 2))
    await browser.close()
    process.exit(1)
  }

  // Close path 1: ← Retour
  const sym1 = symbols[0]
  await page.goto(`${BASE}/app/opportunites`, { waitUntil: 'networkidle2', timeout: 90000 })
  await new Promise((r) => setTimeout(r, 1500))
  await page.evaluate((sym) => {
    const rows = [...document.querySelectorAll('.decisions-table tbody tr')]
    const hit = rows.find((tr) => (tr.textContent || '').includes(sym))
    if (hit) hit.click()
  }, sym1)
  await new Promise((r) => setTimeout(r, 2800))
  let st = await sheetState(page)
  report.closes.retour_open = st
  await page.screenshot({ path: path.join(OUT, '01-sheet-open.png'), fullPage: false })
  if (!st.sheetOpen || !st.chromeHidden || !st.retourVisible || !st.hasSymbolQ) report.pass = false
  await page.click('.decision-sheet-close')
  await new Promise((r) => setTimeout(r, 800))
  st = await sheetState(page)
  report.closes.retour_closed = st
  if (st.sheetOpen || st.hasSymbolQ) report.pass = false
  await page.screenshot({ path: path.join(OUT, '02-after-retour.png'), fullPage: false })

  // Close path 2: history.back
  const sym2 = symbols[1] || symbols[0]
  await page.evaluate((sym) => {
    const rows = [...document.querySelectorAll('.decisions-table tbody tr')]
    const hit = rows.find((tr) => (tr.textContent || '').includes(sym))
    if (hit) hit.click()
  }, sym2)
  await new Promise((r) => setTimeout(r, 2500))
  st = await sheetState(page)
  report.closes.back_open = st
  if (!st.sheetOpen || !st.hasSymbolQ) report.pass = false
  await page.goBack({ waitUntil: 'networkidle2' }).catch(() => null)
  await new Promise((r) => setTimeout(r, 1000))
  st = await sheetState(page)
  report.closes.back_closed = st
  if (st.sheetOpen || st.hasSymbolQ) report.pass = false
  await page.screenshot({ path: path.join(OUT, '03-after-history-back.png'), fullPage: false })

  // Close path 3: re-tap Opportunités tab
  const sym3 = symbols[2] || symbols[0]
  await page.goto(`${BASE}/app/opportunites`, { waitUntil: 'networkidle2', timeout: 90000 })
  await new Promise((r) => setTimeout(r, 1500))
  await page.evaluate((sym) => {
    const rows = [...document.querySelectorAll('.decisions-table tbody tr')]
    const hit = rows.find((tr) => (tr.textContent || '').includes(sym))
    if (hit) hit.click()
  }, sym3)
  await new Promise((r) => setTimeout(r, 2500))
  st = await sheetState(page)
  report.closes.retap_open = st
  if (!st.sheetOpen || !st.hasSymbolQ) report.pass = false
  await page.evaluate(() => {
    const tab = [...document.querySelectorAll('.dash-mobile-tab')].find((el) =>
      (el.textContent || '').includes('Opportunités'),
    )
    if (tab) tab.click()
  })
  await new Promise((r) => setTimeout(r, 1000))
  st = await sheetState(page)
  report.closes.retap_closed = st
  if (st.sheetOpen || st.hasSymbolQ) report.pass = false
  await page.screenshot({ path: path.join(OUT, '04-after-retap.png'), fullPage: false })

  // List intact
  const listOk = await page.evaluate(() => {
    const rows = document.querySelectorAll('.decisions-table tbody tr')
    const chrome = document.querySelector('.decisions-chrome')
    const sheet = document.querySelector('.decision-sheet')
    return {
      rows: rows.length,
      chromeVisible: chrome ? getComputedStyle(chrome).display !== 'none' : false,
      noSheet: !sheet,
    }
  })
  report.listAfter = listOk
  if (listOk.rows < 1 || !listOk.chromeVisible || !listOk.noSheet) report.pass = false
  await page.screenshot({ path: path.join(OUT, '05-list-after.png'), fullPage: true })

  fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify(report, null, 2))
  await browser.close()
  console.log(JSON.stringify(report, null, 2))
  console.log('\n=== FIX-OPPS-SHEET ===', report.pass ? 'PASS' : 'FAIL')
  process.exit(report.pass ? 0 : 1)
}

main().catch((e) => {
  console.error(e)
  process.exit(2)
})
