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
const MAQ = 'http://127.0.0.1:8766'
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
      await new Promise((r) => setTimeout(r, 50))
    }
    window.scrollTo(0, 0)
    if (content.scrollTo) content.scrollTo(0, 0)
  })
  await new Promise((r) => setTimeout(r, 400))
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
  await page.goto(MAQ + '/', { waitUntil: 'networkidle2' })
  await page.evaluate(() => {
    location.hash = 'marche'
  })
  await new Promise((r) => setTimeout(r, 1200))
  await expandScroll(page)
  const bufM = await page.screenshot({ fullPage: true, type: 'png' })
  fs.writeFileSync(`${OUT}/maquette-${tag}.png`, bufM)
  fs.writeFileSync(`${ART}/maquette-${tag}.png`, bufM)
  console.log('maq', tag, bufM.length)
  await page.close()
}

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
  await page.waitForSelector('.market-layout .analysis-panel', { timeout: 20000 })
  await page.waitForSelector('.lecture-synthesis', { timeout: 15000 }).catch(() => null)
  await new Promise((r) => setTimeout(r, 5500))
  await expandScroll(page)
  // Force full height capture by expanding body to content height
  await page.evaluate(() => {
    // Capture pleine page : les éléments fixes du shell (barre d'onglets, feuille Plus)
    // se retrouveraient au milieu de l'image → masqués pour la capture uniquement.
    document
      .querySelectorAll('.dash-mobile-tabbar, .dash-mobile-more, .dash-mobile-more-backdrop')
      .forEach((el) => {
        el.style.display = 'none'
      })
    const mp = document.querySelector('.market-page')
    const dc = document.querySelector('.dash-content')
    if (dc) {
      dc.style.overflow = 'visible'
      dc.style.height = 'auto'
      dc.style.maxHeight = 'none'
    }
    if (mp) {
      const h = mp.getBoundingClientRect().bottom + window.scrollY + 40
      document.body.style.height = `${Math.ceil(h)}px`
    }
  })
  const has = await page.evaluate(() => ({
    layout: !!document.querySelector('.market-layout'),
    analysisH: document.querySelector('.analysis-panel')?.getBoundingClientRect().height,
    synthesis: document.querySelector('.lecture-synthesis')?.textContent?.slice(0, 80),
    h1: getComputedStyle(document.querySelector('.market-page h1')).fontSize,
    srChecked: document.querySelectorAll('.checkrow input')[1]?.checked,
    chgSample: [...document.querySelectorAll('.watchlist button span')]
      .slice(0, 3)
      .map((s) => s.textContent),
    pageH: document.body.scrollHeight,
  }))
  console.log(tag, has)
  const buf = await page.screenshot({ fullPage: true, type: 'png' })
  fs.writeFileSync(`${OUT}/app-${tag}.png`, buf)
  fs.writeFileSync(`${ART}/app-${tag}.png`, buf)
  console.log('app', tag, buf.length)
  await page.close()
}

await browser.close()
console.log('captures ok')
