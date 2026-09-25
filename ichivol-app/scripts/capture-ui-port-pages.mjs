/**
 * Captures pleine page 1440 + 390 pour les 11 pages (tabbar / Plus masqués).
 * Usage: APP_BASE=… SMOKE_EMAIL=… SMOKE_PASS=… node scripts/capture-ui-port-pages.mjs
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import puppeteer from 'puppeteer-core'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const REPO = path.resolve(HERE, '../..')
const OUT = path.join(REPO, 'docs/ui-port/captures')
const ART = '/opt/cursor/artifacts/ui-port-pages'
const APP_BASE = process.env.APP_BASE ?? 'http://127.0.0.1:5180'
const CHROME =
  process.env.CHROME ??
  ['/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'].find((p) =>
    fs.existsSync(p),
  )

const PAGES = {
  desk: '/app/desk',
  marche: '/app/market',
  opportunites: '/app/opportunites',
  portefeuille: '/app/portefeuille',
  lab: '/app/strategy-lab',
  journal: '/app/journal',
  contexte: '/app/context',
  copilot: '/app/agent',
  agents: '/app/agents',
  operations: '/app/operations',
  parametres: '/app/settings',
}

fs.mkdirSync(OUT, { recursive: true })
fs.mkdirSync(ART, { recursive: true })

async function login(browser) {
  if (!process.env.SMOKE_EMAIL) throw new Error('SMOKE_EMAIL required')
  const page = await browser.newPage()
  await page.goto(`${APP_BASE}/login`, { waitUntil: 'networkidle2', timeout: 60000 })
  const email = (await page.$('input[type=email]')) || (await page.$('input[type=text]'))
  await email.type(process.env.SMOKE_EMAIL)
  await (await page.$('input[type=password]')).type(process.env.SMOKE_PASS ?? '')
  await Promise.all([
    page.click('button[type=submit]'),
    page.waitForNavigation({ waitUntil: 'networkidle2' }).catch(() => null),
  ])
  await page.close()
}

async function hideChrome(page) {
  await page.addStyleTag({
    content: `
      .dash-tabbar, .dash-plus, .mobile-tabbar, [data-tabbar],
      .fab-plus, .dash-shell .tabbar, nav.tabbar { display: none !important; visibility: hidden !important; }
    `,
  })
}

async function expandScroll(page) {
  await page.evaluate(async () => {
    const content = document.querySelector('.dash-content') || document.documentElement
    content.scrollTop = 0
    const total = Math.max(
      document.body.scrollHeight,
      document.documentElement.scrollHeight,
      content.scrollHeight || 0,
    )
    for (let y = 0; y < total; y += 400) {
      window.scrollTo(0, y)
      if (content.scrollTo) content.scrollTo(0, y)
      await new Promise((r) => setTimeout(r, 40))
    }
    window.scrollTo(0, 0)
    if (content.scrollTo) content.scrollTo(0, 0)
  })
  await new Promise((r) => setTimeout(r, 300))
}

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ['--no-sandbox'],
})
await login(browser)

for (const [id, route] of Object.entries(PAGES)) {
  for (const [w, h, tag] of [
    [1440, 900, '1440'],
    [390, 844, '390'],
  ]) {
    const page = await browser.newPage()
    await page.setViewport({ width: w, height: h, deviceScaleFactor: 1 })
    await page.goto(`${APP_BASE}${route}`, { waitUntil: 'networkidle2', timeout: 60000 }).catch(() => null)
    await new Promise((r) => setTimeout(r, 2000))
    await hideChrome(page)
    await expandScroll(page)
    const buf = await page.screenshot({ fullPage: true, type: 'png' })
    const name = `${id}-${tag}.png`
    fs.writeFileSync(path.join(OUT, name), buf)
    fs.writeFileSync(path.join(ART, name), buf)
    console.log('ok', name, buf.length)
    await page.close()
  }
}

await browser.close()
console.log('captures →', OUT)
