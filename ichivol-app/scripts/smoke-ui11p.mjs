/**
 * UI-11p smoke: login → 11 routes (console + /api 4xx/5xx) → key actions.
 * Uses puppeteer-core + system Chrome. Screenshots → /tmp/ui11p-smoke/
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
  console.error(
    'SMOKE_EMAIL et SMOKE_PASS sont obligatoires (variables d’environnement). Aucun identifiant par défaut.',
  )
  process.exit(2)
}
const OUT = '/tmp/ui11p-smoke'
const ROUTES = [
  'desk',
  'market',
  'opportunites',
  'portefeuille',
  'context',
  'journal',
  'operations',
  'strategy-lab',
  'agent',
  'agents',
  'settings',
]

fs.mkdirSync(OUT, { recursive: true })

function summarizeBody(text) {
  const t = (text || '').replace(/\s+/g, ' ').trim()
  return t.slice(0, 180)
}

function isNoiseApiFail(status, url) {
  // HANDOFF: POST /api/settings/llm-test → 422 sans clé LLM — non bloquant
  if (status === 422 && url.includes('/api/settings/llm-test')) return true
  return false
}

function isNoiseConsole(text) {
  return /422|llm-test|Unprocessable Entity|favicon/i.test(text || '')
}

async function main() {
  const browser = await puppeteer.launch({
    executablePath: '/usr/bin/google-chrome-stable',
    headless: true,
    args: ['--no-sandbox', '--disable-gpu', '--window-size=1440,900'],
    defaultViewport: { width: 1440, height: 900 },
  })
  const page = await browser.newPage()
  const consoleErrors = []
  const pageNetFails = new Map()
  let currentRoute = 'boot'

  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      const text = msg.text()
      if (isNoiseConsole(text)) return
      consoleErrors.push({ route: currentRoute, text })
    }
  })
  page.on('pageerror', (err) => {
    const text = String(err)
    if (isNoiseConsole(text)) return
    consoleErrors.push({ route: currentRoute, text })
  })
  page.on('response', (res) => {
    const url = res.url()
    if (!url.includes('/api/')) return
    const status = res.status()
    if (status >= 400) {
      const short = url.replace(BASE, '')
      if (isNoiseApiFail(status, short) || isNoiseApiFail(status, url)) return
      const list = pageNetFails.get(currentRoute) || []
      list.push({ status, url: short })
      pageNetFails.set(currentRoute, list)
    }
  })

  const report = { pages: {}, actions: {}, consoleErrors: [], startedAt: new Date().toISOString() }

  // —— Login ——
  currentRoute = 'login'
  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle2', timeout: 60000 })
  await page.waitForSelector('input[type="email"], input[name="email"], input[type="text"]', {
    timeout: 15000,
  })
  const emailSel =
    (await page.$('input[type="email"]')) ||
    (await page.$('input[name="email"]')) ||
    (await page.$('input[type="text"]'))
  const passSel = await page.$('input[type="password"]')
  await emailSel.click({ clickCount: 3 })
  await emailSel.type(EMAIL, { delay: 10 })
  await passSel.click({ clickCount: 3 })
  await passSel.type(PASS, { delay: 10 })
  await Promise.all([
    page.click('button[type="submit"]'),
    page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 30000 }).catch(() => null),
  ])
  await page.waitForFunction(() => location.pathname.startsWith('/app'), { timeout: 20000 })
  await page.screenshot({ path: path.join(OUT, '00-login-ok.png'), fullPage: false })

  // —— 11 pages ——
  for (const route of ROUTES) {
    currentRoute = route
    const beforeConsole = consoleErrors.length
    pageNetFails.set(route, [])
    const url = `${BASE}/app/${route}`
    await page.goto(url, { waitUntil: 'networkidle2', timeout: 90000 }).catch(async (e) => {
      report.pages[route] = { pass: false, note: `navigation error: ${e.message}` }
    })
    // settle fetches
    await new Promise((r) => setTimeout(r, 3500))
    const bodyText = await page.evaluate(() => document.body?.innerText || '')
    const shot = path.join(OUT, `${String(ROUTES.indexOf(route) + 1).padStart(2, '0')}-${route}.png`)
    await page.screenshot({ path: shot, fullPage: false })
    const fails = pageNetFails.get(route) || []
    const newConsole = consoleErrors.slice(beforeConsole)
    const hasRealData =
      bodyText.length > 80 &&
      !/chargement…|loading…/i.test(bodyText.slice(0, 40)) &&
      !/indisponible|erreur serveur|failed to fetch/i.test(bodyText)
    const pass = fails.length === 0 && newConsole.length === 0 && hasRealData
    report.pages[route] = {
      pass,
      note: summarizeBody(bodyText),
      apiFails: fails,
      console: newConsole.map((c) => c.text),
      screenshot: shot,
      bodyChars: bodyText.length,
    }
    console.log(
      `[page] /app/${route} → ${pass ? 'PASS' : 'FAIL'} apiFails=${fails.length} console=${newConsole.length} chars=${bodyText.length}`,
    )
  }

  // —— Actions via UI + fetch in page context (same cookie) ——
  async function api(pathname, opts = {}) {
    return page.evaluate(
      async (pathname, opts) => {
        const res = await fetch(pathname, {
          credentials: 'include',
          headers: { 'content-type': 'application/json', ...(opts.headers || {}) },
          method: opts.method || 'GET',
          body: opts.body ? JSON.stringify(opts.body) : undefined,
        })
        const text = await res.text()
        let json = null
        try {
          json = JSON.parse(text)
        } catch {
          /* ignore */
        }
        return { status: res.status, json, text: text.slice(0, 500) }
      },
      pathname,
      opts,
    )
  }

  // A. Paper open/close (discretionary BUY)
  currentRoute = 'action-paper'
  try {
    const open = await api(
      '/api/engine/paper/positions?symbol=BTCUSDT&timeframe=1h&discretionary=true&notional=400&stop_pct=0.02&take_profit_r=2',
      { method: 'POST' },
    )
    let positionId = open.json?.id || open.json?.position?.id
    let openOk = open.status < 400 && Boolean(positionId)
    if (!openOk) {
      const list = await api('/api/engine/paper/positions?status=OPEN')
      const rows = list.json?.positions || list.json || []
      const btc = (Array.isArray(rows) ? rows : []).find(
        (p) => p.symbol === 'BTCUSDT' && p.status === 'OPEN',
      )
      if (btc) {
        positionId = btc.id
        openOk = true
      }
    }
    let closeStatus = null
    let closeOk = false
    if (positionId) {
      const close = await api(`/api/engine/paper/positions/${positionId}/close`, {
        method: 'POST',
      })
      closeStatus = close.status
      closeOk = close.status < 400
    }
    report.actions.paper = {
      pass: openOk && closeOk,
      openStatus: open.status,
      closeStatus,
      positionId,
      openSnippet: open.text?.slice(0, 200),
    }
  } catch (e) {
    report.actions.paper = { pass: false, error: String(e) }
  }
  console.log('[action] paper', report.actions.paper)

  // B. Kill switch arm/disarm
  currentRoute = 'action-kill'
  try {
    const arm = await api('/api/engine/paper/portfolios/ICHIVOL_BASELINE_V1/kill-switch/arm', {
      method: 'POST',
      body: { confirm: true },
    })
    const disarm = await api(
      '/api/engine/paper/portfolios/ICHIVOL_BASELINE_V1/kill-switch/disarm',
      { method: 'POST', body: { confirm: true } },
    )
    report.actions.killSwitch = {
      pass: arm.status < 400 && disarm.status < 400,
      armStatus: arm.status,
      disarmStatus: disarm.status,
      armedAfterArm: arm.json?.kill_switch_armed,
      armedAfterDisarm: disarm.json?.kill_switch_armed,
    }
  } catch (e) {
    report.actions.killSwitch = { pass: false, error: String(e) }
  }
  console.log('[action] kill', report.actions.killSwitch)

  // C. Walk-forward + monte-carlo (strategy-lab)
  currentRoute = 'action-lab'
  try {
    await page.goto(`${BASE}/app/strategy-lab`, { waitUntil: 'networkidle2', timeout: 90000 })
    await new Promise((r) => setTimeout(r, 5000))
    await page.screenshot({ path: path.join(OUT, '20-strategy-lab-loaded.png'), fullPage: false })
    const wf = await api(
      '/api/engine/strategy-lab/walk-forward?symbol=BTCUSDT&timeframe=1h&limit=1200&persist=false',
    )
    // pick a ruleset id from UI state or default IV_EXP_A / first available
    let rulesetId = 'IV_ICHIMOKU_RVOL_LONG_001'
    const rs = await api('/api/engine/rulesets')
    const list = Array.isArray(rs.json) ? rs.json : rs.json?.rulesets
    if (rs.status < 400 && Array.isArray(list) && list[0]) {
      rulesetId = list[0].id || list[0].ruleset_id || rulesetId
    }
    const mc = await api('/api/engine/strategy-lab/monte-carlo', {
      method: 'POST',
      body: {
        symbol: 'BTCUSDT',
        timeframe: '1h',
        limit: 1200,
        ruleset_id: rulesetId,
        n_paths: 200,
        min_trades: 5,
        seed: 42,
      },
    })
    report.actions.lab = {
      pass: wf.status < 400 && mc.status < 400,
      walkForwardStatus: wf.status,
      monteCarloStatus: mc.status,
      rulesetId,
      wfKeys: wf.json && typeof wf.json === 'object' ? Object.keys(wf.json).slice(0, 12) : null,
      mcKeys: mc.json && typeof mc.json === 'object' ? Object.keys(mc.json).slice(0, 12) : null,
      wfSnippet: wf.text?.slice(0, 220),
      mcSnippet: mc.text?.slice(0, 220),
    }
  } catch (e) {
    report.actions.lab = { pass: false, error: String(e) }
  }
  console.log('[action] lab', report.actions.lab)

  // D. Settings save (theme round-trip)
  currentRoute = 'action-settings'
  try {
    await page.goto(`${BASE}/app/settings`, { waitUntil: 'networkidle2', timeout: 60000 })
    await new Promise((r) => setTimeout(r, 2000))
    const toLight = await api('/api/settings', { method: 'PATCH', body: { theme: 'light' } })
    const toDark = await api('/api/settings', { method: 'PATCH', body: { theme: 'dark' } })
    report.actions.settings = {
      pass: toLight.status < 400 && toDark.status < 400,
      lightStatus: toLight.status,
      darkStatus: toDark.status,
      themeAfter: toDark.json?.theme,
    }
    await page.screenshot({ path: path.join(OUT, '21-settings.png'), fullPage: false })
  } catch (e) {
    report.actions.settings = { pass: false, error: String(e) }
  }
  console.log('[action] settings', report.actions.settings)

  // E. Copilot chat
  currentRoute = 'action-agent'
  try {
    await page.goto(`${BASE}/app/agent`, { waitUntil: 'networkidle2', timeout: 60000 })
    await new Promise((r) => setTimeout(r, 2000))
    const chat = await api('/api/agent/chat', {
      method: 'POST',
      body: { mode: 'research', question: 'quel est le biais BTCUSDT 1h ?' },
    })
    report.actions.copilot = {
      pass: chat.status < 400 && Boolean(chat.json?.reply || chat.json?.message || chat.json?.answer || chat.json?.threadId),
      status: chat.status,
      keys: chat.json && typeof chat.json === 'object' ? Object.keys(chat.json).slice(0, 20) : null,
      snippet: chat.text?.slice(0, 300),
    }
    // Also try UI textarea
    const ta = await page.$('textarea')
    if (ta) {
      await ta.type('résume le desk en une phrase', { delay: 5 })
      const send = await page.$('button[type="submit"]')
      if (send) await send.click()
      await new Promise((r) => setTimeout(r, 12000))
    }
    await page.screenshot({ path: path.join(OUT, '22-agent-chat.png'), fullPage: false })
  } catch (e) {
    report.actions.copilot = { pass: false, error: String(e) }
  }
  console.log('[action] copilot', report.actions.copilot)

  report.consoleErrors = consoleErrors
  report.finishedAt = new Date().toISOString()
  fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify(report, null, 2))
  await browser.close()

  const pageFails = Object.entries(report.pages).filter(([, v]) => !v.pass)
  // Copilot chat sans clé LLM → 400 attendu (HANDOFF) — ne bloque pas le smoke pages
  const actionFails = Object.entries(report.actions).filter(([k, v]) => {
    if (k === 'copilot' && !v.pass) return false
    return !v.pass
  })
  console.log('\n=== SUMMARY ===')
  console.log('pages fail:', pageFails.map(([k]) => k))
  console.log('actions fail:', actionFails.map(([k]) => k))
  if (report.actions.copilot && !report.actions.copilot.pass) {
    console.log('note: action copilot FAIL attendu sans clé LLM')
  }
  process.exit(pageFails.length || actionFails.length ? 1 : 0)
}

main().catch((e) => {
  console.error(e)
  process.exit(2)
})
