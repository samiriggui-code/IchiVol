/**
 * Smoke thème : dark puis light — shell + première .card doivent partager
 * la même « famille » (pas de carte crème sur fond sombre).
 * Usage : APP_BASE=http://127.0.0.1:5181 node scripts/smoke-theme-switch.mjs
 */
import fs from 'node:fs'
import puppeteer from 'puppeteer-core'

const APP = process.env.APP_BASE ?? 'http://127.0.0.1:5181'
const EMAIL = process.env.SMOKE_EMAIL ?? 'ui11p-smoke@ichivol.local'
const PASS = process.env.SMOKE_PASS ?? ''
const CHROME =
  process.env.CHROME ??
  ['/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'].find((p) =>
    fs.existsSync(p),
  )

function lum(hex) {
  const h = hex.replace('#', '')
  const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h
  const n = parseInt(full.slice(0, 6), 16)
  const r = (n >> 16) & 255
  const g = (n >> 8) & 255
  const b = n & 255
  return (0.299 * r + 0.587 * g + 0.114 * b) / 255
}

function rgbToHex(rgb) {
  const m = String(rgb).match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
  if (!m) return '#000000'
  return (
    '#' +
    [m[1], m[2], m[3]]
      .map((x) => Number(x).toString(16).padStart(2, '0'))
      .join('')
  )
}

async function login(page) {
  await page.goto(`${APP}/login`, { waitUntil: 'networkidle2', timeout: 60000 })
  const email = await page.$('input[type="email"], input[name="email"]')
  if (!email) return
  if (!PASS) {
    console.warn('SMOKE_PASS empty — skip login, try public routes')
    return
  }
  await page.type('input[type="email"], input[name="email"]', EMAIL, { delay: 10 })
  await page.type('input[type="password"], input[name="password"]', PASS, { delay: 10 })
  await Promise.all([
    page.click('button[type="submit"]'),
    page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 30000 }).catch(() => null),
  ])
}

async function measure(page) {
  return page.evaluate(() => {
    const shell = document.querySelector('.dash-shell') || document.body
    const card = document.querySelector('.card')
    const cs = (el) => getComputedStyle(el)
    return {
      darkClass: document.documentElement.classList.contains('dark'),
      shellBg: cs(shell).backgroundColor,
      cardBg: card ? cs(card).backgroundColor : null,
      ink: card ? cs(card).color : cs(shell).color,
    }
  })
}

async function setTheme(page, mode) {
  await page.evaluate((m) => {
    document.documentElement.classList.toggle('dark', m === 'dark')
    localStorage.setItem('ichivol_theme', m)
    window.dispatchEvent(new Event('ichivol:theme'))
  }, mode)
  await new Promise((r) => setTimeout(r, 200))
}

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: true,
  args: ['--no-sandbox', '--disable-setuid-sandbox'],
})
const page = await browser.newPage()
await page.setViewport({ width: 390, height: 844 })
await login(page)
await page.goto(`${APP}/app/operations`, { waitUntil: 'networkidle2', timeout: 60000 }).catch(async () => {
  await page.goto(`${APP}/app/desk`, { waitUntil: 'networkidle2', timeout: 60000 })
})

const fails = []
for (const mode of ['dark', 'light']) {
  await setTheme(page, mode)
  const m = await measure(page)
  const shellL = lum(rgbToHex(m.shellBg))
  const cardL = m.cardBg ? lum(rgbToHex(m.cardBg)) : shellL
  const sameFamily = Math.abs(shellL - cardL) < 0.35
  const expectDark = mode === 'dark'
  const shellOk = expectDark ? shellL < 0.45 : shellL > 0.55
  const cardOk = expectDark ? cardL < 0.45 : cardL > 0.55
  console.log(JSON.stringify({ mode, shellL, cardL, sameFamily, shellOk, cardOk, ...m }))
  if (!sameFamily || !shellOk || !cardOk) {
    fails.push({ mode, shellL, cardL, sameFamily, shellOk, cardOk })
  }
}

await browser.close()
if (fails.length) {
  console.error('THEME_SMOKE_FAIL', fails)
  process.exit(1)
}
console.log('THEME_SMOKE_PASS')
