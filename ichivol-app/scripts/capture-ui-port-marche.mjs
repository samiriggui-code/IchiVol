import fs from 'node:fs'
import { createRequire } from 'node:module'
const require = createRequire('/tmp/wt-chart/ichivol-app/package.json')
const puppeteer = require('puppeteer-core')
const CHROME = ['/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'].find(
  (p) => fs.existsSync(p),
)
const EMAIL = process.env.SMOKE_EMAIL
const PASS = process.env.SMOKE_PASS
const OUT = '/tmp/wt-port-marche/docs/ui-port/marche'
const ART = '/opt/cursor/artifacts/ui-port-marche'
const BASE = 'http://127.0.0.1:5180'
fs.mkdirSync(OUT, { recursive: true })
fs.mkdirSync(ART, { recursive: true })

async function login(page) {
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle2', timeout: 60000 })
  if (page.url().includes('/app')) return
  const email = (await page.$('input[type="email"]')) || (await page.$('input[type="text"]'))
  const pass = await page.$('input[type="password"]')
  await email.click({ clickCount: 3 })
  await email.type(EMAIL, { delay: 5 })
  await pass.click({ clickCount: 3 })
  await pass.type(PASS, { delay: 5 })
  await Promise.all([
    page.click('button[type="submit"]'),
    page.waitForNavigation({ waitUntil: 'networkidle2' }).catch(() => null),
  ])
  await page.waitForFunction(() => location.pathname.startsWith('/app'), { timeout: 20000 })
}

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ['--no-sandbox', '--disable-setuid-sandbox'],
})

for (const [w, h, tag] of [
  [1440, 900, '1440'],
  [390, 844, '390'],
]) {
  const page = await browser.newPage()
  await page.setViewport({ width: w, height: h, deviceScaleFactor: 1 })
  await login(page)
  await page.goto(`${BASE}/app/market?symbol=BTCUSDT`, {
    waitUntil: 'domcontentloaded',
    timeout: 60000,
  })
  await new Promise((r) => setTimeout(r, 5500))
  const has = await page.evaluate(() => ({
    layout: !!document.querySelector('.market-layout'),
    eyebrow: document.querySelector('.eyebrow')?.textContent,
    lecture: !!document.querySelector('.analysis-panel'),
    calques: [...document.querySelectorAll('button')].some((b) =>
      /Calques/.test(b.textContent || ''),
    ),
  }))
  console.log(tag, has)
  const buf = await page.screenshot({ fullPage: true, type: 'png' })
  fs.writeFileSync(`${OUT}/app-${tag}.png`, buf)
  fs.writeFileSync(`${ART}/app-${tag}.png`, buf)
  await page.close()
}
await browser.close()
console.log('captures ok')
