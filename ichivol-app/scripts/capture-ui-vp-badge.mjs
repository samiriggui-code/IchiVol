/**
 * B1 → docs/ui-vp-badge/{light,dark,mobile}.png
 * light : app auth /opportunites si badge visible, sinon harness.
 * dark / mobile : harness (composants réels) — décision + position 390px.
 */
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { createHash } from 'node:crypto'

const require = createRequire(import.meta.url)
const puppeteer = require('puppeteer-core')
const __dirname = path.dirname(fileURLToPath(import.meta.url))
const APP = path.resolve(__dirname, '..')
const OUT = path.resolve(APP, '../docs/ui-vp-badge')
const BASE = process.env.SMOKE_BASE || 'http://127.0.0.1:5174'
const API = process.env.SMOKE_API || 'http://127.0.0.1:8787'

function loadCreds() {
  const raw = fs.readFileSync(path.join(APP, '.env.local'), 'utf8')
  return {
    email: (raw.match(/VITE_DEV_ADMIN_EMAIL=(.*)/) || [])[1]?.trim(),
    pass: (raw.match(/VITE_DEV_ADMIN_PASSWORD=(.*)/) || [])[1]?.trim(),
  }
}

async function loginCookies() {
  const { email, pass } = loadCreds()
  const res = await fetch(`${API}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password: pass }),
  })
  if (!res.ok) throw new Error(`login ${res.status}`)
  return (res.headers.getSetCookie?.() || []).map((h) => {
    const [nv] = h.split(';')
    const i = nv.indexOf('=')
    return { name: nv.slice(0, i), value: nv.slice(i + 1) }
  })
}

const browser = await puppeteer.launch({
  executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  headless: true,
  args: ['--no-sandbox'],
})
const page = await browser.newPage()
try {
  const cookies = await loginCookies().catch(() => [])
  if (cookies.length) {
    await page.setCookie(
      ...cookies.map((c) => ({ ...c, domain: '127.0.0.1', path: '/', httpOnly: true })),
    )
  }
  fs.mkdirSync(OUT, { recursive: true })

  // light — live matrix
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 })
  let lightLive = false
  if (cookies.length) {
    await page.goto(`${BASE}/app/opportunites`, { waitUntil: 'networkidle2', timeout: 180000 })
    await page.evaluate(() => document.documentElement.classList.remove('dark'))
    lightLive = await page
      .waitForFunction(() => document.body.innerText.includes('Signal non valid'), {
        timeout: 120000,
      })
      .then(() => true)
      .catch(() => false)
  }
  if (!lightLive) {
    await page.goto(`${BASE}/capture/vp-badge?view=matrix`, { waitUntil: 'networkidle2' })
    await page.evaluate(() => document.documentElement.classList.remove('dark'))
    await page.waitForFunction(() => document.body.innerText.includes('Signal non valid'))
  }
  await page.screenshot({ path: path.join(OUT, 'light.png'), fullPage: false })
  console.log('light', fs.statSync(path.join(OUT, 'light.png')).size, lightLive ? 'live' : 'harness')

  // dark — decision fiche
  await page.setViewport({ width: 1280, height: 900, deviceScaleFactor: 2 })
  await page.goto(`${BASE}/capture/vp-badge?view=decision`, { waitUntil: 'networkidle2' })
  await page.evaluate(() => document.documentElement.classList.add('dark'))
  await page.waitForFunction(() => document.body.innerText.includes('Signal non valid'))
  const darkBox = await page.evaluate(() => {
    const el = document.querySelector('.dialog-body')
    if (!el) return null
    const r = el.getBoundingClientRect()
    return { x: r.x, y: r.y, width: r.width, height: Math.min(r.height + 24, 800) }
  })
  if (darkBox) {
    await page.screenshot({
      path: path.join(OUT, 'dark.png'),
      clip: {
        x: Math.max(0, darkBox.x - 16),
        y: Math.max(0, darkBox.y - 16),
        width: darkBox.width + 32,
        height: darkBox.height + 32,
      },
    })
  } else {
    await page.screenshot({ path: path.join(OUT, 'dark.png'), fullPage: false })
  }
  console.log('dark', fs.statSync(path.join(OUT, 'dark.png')).size)

  // mobile — position 390
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2 })
  await page.goto(`${BASE}/capture/vp-badge?view=position`, { waitUntil: 'networkidle2' })
  await page.evaluate(() => document.documentElement.classList.remove('dark'))
  await page.waitForFunction(() => document.body.innerText.includes('Signal non valid'))
  const mobBox = await page.evaluate(() => {
    const el = document.querySelector('.pf-fiche')
    if (!el) return null
    const r = el.getBoundingClientRect()
    return {
      x: Math.max(0, r.x - 4),
      y: Math.max(0, r.y - 4),
      width: Math.min(r.width + 8, 382),
      height: Math.min(r.height + 8, 700),
    }
  })
  if (mobBox && mobBox.width > 40) {
    await page.screenshot({ path: path.join(OUT, 'mobile.png'), clip: mobBox })
  } else {
    await page.screenshot({ path: path.join(OUT, 'mobile.png'), fullPage: false })
  }
  console.log('mobile', fs.statSync(path.join(OUT, 'mobile.png')).size)

  const hashes = ['light.png', 'dark.png', 'mobile.png'].map((f) => {
    const b = fs.readFileSync(path.join(OUT, f))
    return { f, sha: createHash('sha256').update(b).digest('hex').slice(0, 16), n: b.length }
  })
  console.log(JSON.stringify(hashes, null, 2))
  if (new Set(hashes.map((h) => h.sha)).size < 3) {
    console.error('FAIL hashes')
    process.exit(1)
  }
} finally {
  await browser.close()
}
