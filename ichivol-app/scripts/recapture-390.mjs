import fs from 'node:fs'
import { createRequire } from 'node:module'
const require = createRequire('/tmp/wt-chart/ichivol-app/package.json')
const puppeteer = require('puppeteer-core')
const CHROME = ['/usr/bin/google-chrome', '/usr/bin/chromium'].find((p) => fs.existsSync(p))
const BASE = 'http://127.0.0.1:5180'
const OUT = '/tmp/wt-port-marche/docs/ui-port/marche'
const ART = '/opt/cursor/artifacts/ui-port-marche'

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ['--no-sandbox'],
})
const page = await browser.newPage()
await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 1 })
await page.goto(`${BASE}/login`, { waitUntil: 'networkidle2' })
const email = (await page.$('input[type=email]')) || (await page.$('input[type=text]'))
const pass = await page.$('input[type=password]')
await email.type(process.env.SMOKE_EMAIL, { delay: 2 })
await pass.type(process.env.SMOKE_PASS, { delay: 2 })
await Promise.all([
  page.click('button[type=submit]'),
  page.waitForNavigation({ waitUntil: 'networkidle2' }).catch(() => null),
])
await page.goto(`${BASE}/app/market?symbol=BTCUSDT`, { waitUntil: 'domcontentloaded' })
await page.waitForSelector('.analysis-panel', { timeout: 20000 })
await new Promise((r) => setTimeout(r, 5000))
await page.keyboard.press('Escape')
await page.evaluate(() => {
  document.querySelectorAll('.plus-sheet, .dash-plus-panel, .mobile-more-sheet, .dash-more').forEach((el) => {
    el.remove()
  })
  const dc = document.querySelector('.dash-content')
  if (dc) {
    dc.style.overflow = 'visible'
    dc.style.height = 'auto'
    dc.style.maxHeight = 'none'
  }
  const mp = document.querySelector('.market-page')
  if (mp) {
    document.body.style.height = `${Math.ceil(mp.getBoundingClientRect().bottom + window.scrollY + 80)}px`
  }
})
await new Promise((r) => setTimeout(r, 300))
const info = await page.evaluate(() => ({
  h: document.body.scrollHeight,
  gates: [...document.querySelectorAll('.analysis-panel .statline')].map((s) => s.textContent.trim()),
  synthesis: document.querySelector('.lecture-synthesis')?.textContent,
}))
console.log(info)
const buf = await page.screenshot({ fullPage: true, type: 'png' })
fs.writeFileSync(`${OUT}/app-390.png`, buf)
fs.writeFileSync(`${ART}/app-390.png`, buf)
console.log('saved', buf.length)
await browser.close()
