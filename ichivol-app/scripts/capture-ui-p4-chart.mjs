/**
 * Capture BTC 1H market chart — defaults + advanced layers, desktop + mobile 390.
 * Writes to docs/ui-p4/ and /opt/cursor/artifacts/ui-p4-chart/
 */
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const require = createRequire(import.meta.url)
const puppeteer = require('puppeteer-core')

const BASE = process.env.SMOKE_BASE || 'http://127.0.0.1:5178'
const EMAIL = process.env.SMOKE_EMAIL
const PASS = process.env.SMOKE_PASS
if (!EMAIL || !PASS) {
  console.error('SMOKE_EMAIL et SMOKE_PASS obligatoires.')
  process.exit(2)
}

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '../..')
const DOCS = path.join(ROOT, 'docs/ui-p4')
const ART = '/opt/cursor/artifacts/ui-p4-chart'
fs.mkdirSync(DOCS, { recursive: true })
fs.mkdirSync(ART, { recursive: true })

const CHROME =
  process.env.CHROME_PATH ||
  ['/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'].find((p) =>
    fs.existsSync(p),
  )

async function login(page) {
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle2', timeout: 60000 })
  if (page.url().includes('/app')) return
  const emailSel =
    (await page.$('input[type="email"]')) ||
    (await page.$('input[name="email"]')) ||
    (await page.$('input[type="text"]'))
  const passSel = await page.$('input[type="password"]')
  if (!emailSel || !passSel) {
    await page
      .waitForFunction(() => location.pathname.startsWith('/app'), { timeout: 10000 })
      .catch(() => null)
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

async function gotoMarketBtc1h(page) {
  await page.goto(`${BASE}/app/market?symbol=BTCUSDT`, {
    waitUntil: 'domcontentloaded',
    timeout: 60000,
  })
  await page.evaluate(() => {
    for (const k of Object.keys(localStorage)) {
      if (k.startsWith('ichivol.market.layers')) localStorage.removeItem(k)
    }
  })
  await page.reload({ waitUntil: 'domcontentloaded' })
  await new Promise((r) => setTimeout(r, 1500))
  // Select 1H timeframe if buttons present
  await page.evaluate(() => {
    const btns = [...document.querySelectorAll('button')]
    const oneH = btns.find((b) => /^(1H|1h)$/.test((b.textContent || '').trim()))
    if (oneH) oneH.click()
  })
  await new Promise((r) => setTimeout(r, 4500))
  // Wait for chart host
  await page.waitForSelector('.chart-host, .mkt-chart-panel canvas', { timeout: 20000 }).catch(() => null)
  await new Promise((r) => setTimeout(r, 2000))
}

async function openLayersAndToggleAdvanced(page, { enableAdvanced }) {
  // Open Calques
  await page.evaluate(() => {
    const btns = [...document.querySelectorAll('button')]
    const calques = btns.find((b) => /Calques/i.test(b.textContent || ''))
    if (calques) calques.click()
  })
  await new Promise((r) => setTimeout(r, 600))

  if (enableAdvanced) {
    await page.evaluate(() => {
      const toggle = document.querySelector('.mkt-layers-advanced-toggle')
      if (toggle && !toggle.classList.contains('is-open')) toggle.click()
    })
    await new Promise((r) => setTimeout(r, 300))
    // Enable all advanced layers
    await page.evaluate(() => {
      const rows = [...document.querySelectorAll('.mkt-layers-advanced .mkt-layer-row')]
      for (const row of rows) {
        if (!row.classList.contains('is-on')) row.click()
      }
      // Also enable S/R primary
      const primary = [...document.querySelectorAll('.mkt-layers-primary .mkt-layer-row')]
      for (const row of primary) {
        if (!row.classList.contains('is-on')) row.click()
      }
    })
    await new Promise((r) => setTimeout(r, 800))
  }

  // Close layers menu/sheet so chart is visible
  await page.evaluate(() => {
    const done = [...document.querySelectorAll('button')].find((b) =>
      /Terminé|Fermer/i.test(b.textContent || ''),
    )
    if (done) done.click()
    // click backdrop
    const bd = document.querySelector('.mkt-search-backdrop, .mkt-layers-sheet .mkt-search-backdrop')
    if (bd) bd.click()
    // escape click outside - press Escape
  })
  await page.keyboard.press('Escape').catch(() => null)
  await new Promise((r) => setTimeout(r, 500))
}

async function shot(page, name) {
  const file = `${name}.png`
  const buf = await page.screenshot({ fullPage: false, type: 'png' })
  fs.writeFileSync(path.join(DOCS, file), buf)
  fs.writeFileSync(path.join(ART, file), buf)
  console.log('wrote', file)
}

async function runViewport(browser, { width, height, prefix }) {
  const page = await browser.newPage()
  await page.setViewport({ width, height, deviceScaleFactor: 1 })
  await login(page)

  // Defaults
  await gotoMarketBtc1h(page)
  // Clear localStorage layers to force v2 defaults if somehow old
  await page.evaluate(() => {
    localStorage.removeItem('ichivol.market.layers')
    // keep v2 if present; if empty, reload for DEFAULT_LAYERS
  })
  await shot(page, `${prefix}-btc-1h-default`)

  // Advanced layers on
  await openLayersAndToggleAdvanced(page, { enableAdvanced: true })
  await shot(page, `${prefix}-btc-1h-advanced`)

  // Layers menu open (advanced expanded) for UX proof
  await page.evaluate(() => {
    const btns = [...document.querySelectorAll('button')]
    const calques = btns.find((b) => /Calques/i.test(b.textContent || ''))
    if (calques) calques.click()
  })
  await new Promise((r) => setTimeout(r, 400))
  await page.evaluate(() => {
    const toggle = document.querySelector('.mkt-layers-advanced-toggle')
    if (toggle && !toggle.classList.contains('is-open')) toggle.click()
  })
  await new Promise((r) => setTimeout(r, 400))
  await shot(page, `${prefix}-calques-menu`)

  await page.close()
}

async function main() {
  if (!CHROME) throw new Error('Chrome not found')
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  })
  try {
    await runViewport(browser, { width: 1440, height: 900, prefix: 'desktop' })
    await runViewport(browser, { width: 390, height: 844, prefix: 'mobile' })
  } finally {
    await browser.close()
  }
  console.log('OK docs=', DOCS)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
