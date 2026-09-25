/**
 * Mobile smoke @ 390×844 — tab bar, Plus sheet, no horizontal overflow.
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
const OUT = '/tmp/ui11p-mobile'
const W = 390
const H = 844
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
const EXPECTED_TABS = ['Desk', 'Opportunités', 'Portefeuille', 'Copilot', 'Plus']

fs.mkdirSync(OUT, { recursive: true })

async function main() {
  const browser = await puppeteer.launch({
    executablePath: '/usr/bin/google-chrome-stable',
    headless: true,
    args: [`--window-size=${W},${H}`, '--no-sandbox', '--disable-gpu'],
    defaultViewport: { width: W, height: H, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
  })
  const page = await browser.newPage()
  const report = {
    viewport: { width: W, height: H },
    tabbar: null,
    plus: null,
    pages: {},
    pass: true,
  }

  await page.goto(`${BASE}/login`, { waitUntil: 'networkidle2', timeout: 60000 })
  const emailSel =
    (await page.$('input[type="email"]')) ||
    (await page.$('input[name="email"]')) ||
    (await page.$('input[type="text"]'))
  const passSel = await page.$('input[type="password"]')
  await emailSel.click({ clickCount: 3 })
  await emailSel.type(EMAIL, { delay: 5 })
  await passSel.click({ clickCount: 3 })
  await passSel.type(PASS, { delay: 5 })
  await Promise.all([
    page.click('button[type="submit"]'),
    page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 30000 }).catch(() => null),
  ])
  await page.waitForFunction(() => location.pathname.startsWith('/app'), { timeout: 20000 })
  await page.goto(`${BASE}/app/desk`, { waitUntil: 'networkidle2', timeout: 60000 })
  await new Promise((r) => setTimeout(r, 2000))

  // —— Tab bar ——
  const tabInfo = await page.evaluate(() => {
    const bar = document.querySelector('.dash-mobile-tabbar')
    if (!bar) return { present: false }
    const style = getComputedStyle(bar)
    const tabs = [...bar.querySelectorAll('.dash-mobile-tab, a, button')].map((el) => ({
      text: (el.textContent || '').replace(/\s+/g, ' ').trim(),
      tag: el.tagName,
    }))
    // Prefer span labels inside tabs
    const labels = [...bar.querySelectorAll('.dash-mobile-tab span, .dash-mobile-tab')]
      .map((el) => {
        if (el.tagName === 'SPAN') return (el.textContent || '').trim()
        const span = el.querySelector('span')
        return span ? (span.textContent || '').trim() : (el.textContent || '').replace(/\s+/g, ' ').trim()
      })
      .filter(Boolean)
    // unique preserving order of primary labels
    const uniq = []
    for (const t of labels) {
      if (!uniq.includes(t) && ['Desk', 'Opportunités', 'Portefeuille', 'Copilot', 'Plus'].includes(t)) {
        uniq.push(t)
      }
    }
    return {
      present: true,
      display: style.display,
      labels: uniq.length ? uniq : labels.slice(0, 8),
      rawTabs: tabs.slice(0, 8),
      rect: bar.getBoundingClientRect().toJSON(),
    }
  })
  const tabsOk =
    tabInfo.present &&
    tabInfo.display !== 'none' &&
    EXPECTED_TABS.every((t) => (tabInfo.labels || []).includes(t))
  report.tabbar = { ...tabInfo, pass: tabsOk, expected: EXPECTED_TABS }
  await page.screenshot({ path: path.join(OUT, '00-tabbar-desk.png') })
  console.log('[tabbar]', report.tabbar)

  // —— Plus open/close ——
  const plusBtn = await page.evaluateHandle(() => {
    const tabs = [...document.querySelectorAll('.dash-mobile-tab')]
    return tabs.find((t) => /Plus/i.test(t.textContent || '')) || null
  })
  let plusOpen = false
  let plusClose = false
  let plusLinks = []
  if (plusBtn && plusBtn.asElement()) {
    await plusBtn.asElement().click()
    await new Promise((r) => setTimeout(r, 600))
    const openState = await page.evaluate(() => {
      const sheet = document.querySelector('.dash-mobile-more')
      const backdrop = document.querySelector('.dash-mobile-more-backdrop')
      const sheetStyle = sheet ? getComputedStyle(sheet) : null
      const links = sheet
        ? [...sheet.querySelectorAll('a')].map((a) => ({
            href: a.getAttribute('href'),
            text: (a.textContent || '').replace(/\s+/g, ' ').trim(),
          }))
        : []
      return {
        sheetExists: Boolean(sheet),
        sheetDisplay: sheetStyle?.display,
        sheetVisibility: sheetStyle?.visibility,
        sheetOpacity: sheetStyle?.opacity,
        backdropExists: Boolean(backdrop),
        openClass: document.querySelector('.dash-shell')?.className || '',
        links,
      }
    })
    plusOpen =
      openState.sheetExists &&
      openState.sheetDisplay !== 'none' &&
      openState.sheetVisibility !== 'hidden'
    plusLinks = openState.links
    await page.screenshot({ path: path.join(OUT, '01-plus-open.png') })
    console.log('[plus open]', openState)

    // Close via backdrop or Plus toggle or close button
    const closed = await page.evaluate(() => {
      const backdrop = document.querySelector('.dash-mobile-more-backdrop')
      if (backdrop) {
        backdrop.click()
        return 'backdrop'
      }
      const closeBtn = [...document.querySelectorAll('button')].find((b) =>
        /fermer|close/i.test(b.textContent || ''),
      )
      if (closeBtn) {
        closeBtn.click()
        return 'close-btn'
      }
      const plus = [...document.querySelectorAll('.dash-mobile-tab')].find((t) =>
        /Plus/i.test(t.textContent || ''),
      )
      if (plus) {
        plus.click()
        return 'plus-toggle'
      }
      return null
    })
    await new Promise((r) => setTimeout(r, 500))
    const afterClose = await page.evaluate(() => {
      const sheet = document.querySelector('.dash-mobile-more')
      if (!sheet) return { closed: true, reason: 'no-sheet' }
      const s = getComputedStyle(sheet)
      const hidden =
        s.display === 'none' ||
        s.visibility === 'hidden' ||
        s.opacity === '0' ||
        sheet.getAttribute('aria-hidden') === 'true' ||
        !document.querySelector('.dash-mobile-more-backdrop')
      // also check if more panel has is-open class removed
      const open =
        sheet.classList.contains('is-open') ||
        document.querySelector('.dash-shell.is-more-open') ||
        document.body.classList.contains('more-open')
      return {
        closed: hidden || !open,
        display: s.display,
        visibility: s.visibility,
        opacity: s.opacity,
        className: sheet.className,
        shell: document.querySelector('.dash-shell')?.className,
      }
    })
    // If still visible, try clicking Plus again
    if (!afterClose.closed) {
      await plusBtn.asElement().click()
      await new Promise((r) => setTimeout(r, 400))
    }
    const afterClose2 = await page.evaluate(() => {
      const sheet = document.querySelector('.dash-mobile-more')
      if (!sheet) return { closed: true }
      const s = getComputedStyle(sheet)
      const openAttr = sheet.classList.contains('is-open')
      const shellOpen = document.querySelector('.dash-shell.is-more-open')
      return {
        closed: s.display === 'none' || (!openAttr && !shellOpen && s.visibility !== 'visible'),
        display: s.display,
        className: sheet.className,
        shell: document.querySelector('.dash-shell')?.className,
      }
    })
    plusClose = afterClose.closed || afterClose2.closed
    await page.screenshot({ path: path.join(OUT, '02-plus-closed.png') })
    report.plus = {
      pass: plusOpen && plusClose,
      opened: plusOpen,
      closed: plusClose,
      closeMethod: closed,
      links: plusLinks,
      afterClose,
      afterClose2,
    }
  } else {
    report.plus = { pass: false, error: 'Plus button not found' }
  }
  console.log('[plus]', report.plus)

  // —— Overflow check on all routes ——
  for (const route of ROUTES) {
    await page.goto(`${BASE}/app/${route}`, { waitUntil: 'networkidle2', timeout: 90000 })
    await new Promise((r) => setTimeout(r, 2500))
    // ensure Plus closed
    await page.evaluate(() => {
      const shell = document.querySelector('.dash-shell')
      shell?.classList.remove('is-more-open')
      const sheet = document.querySelector('.dash-mobile-more')
      sheet?.classList.remove('is-open')
    })
    const overflow = await page.evaluate((vw) => {
      const doc = document.documentElement
      const body = document.body
      const scrollW = Math.max(doc.scrollWidth, body.scrollWidth)
      const clientW = doc.clientWidth
      const offenders = []
      for (const el of document.querySelectorAll('body *')) {
        if (!(el instanceof HTMLElement)) continue
        const r = el.getBoundingClientRect()
        if (r.width < 1 || r.height < 1) continue
        // ignore intentionally scrollable sub-areas that stay within viewport width
        if (r.right > vw + 1 || r.left < -1) {
          const cs = getComputedStyle(el)
          if (cs.position === 'fixed' && (cs.bottom === '0px' || el.classList.contains('dash-mobile-tabbar'))) {
            // tabbar should fit
            if (r.right > vw + 1 || r.left < -1) {
              offenders.push({
                tag: el.tagName,
                cls: el.className?.toString?.().slice(0, 80),
                left: Math.round(r.left),
                right: Math.round(r.right),
              })
            }
            continue
          }
          // skip elements inside overflow-x auto containers that don't expand page
          let p = el.parentElement
          let inScrollX = false
          while (p) {
            const pcs = getComputedStyle(p)
            if (/(auto|scroll)/.test(pcs.overflowX) && p.getBoundingClientRect().width <= vw + 1) {
              inScrollX = true
              break
            }
            p = p.parentElement
          }
          if (inScrollX) continue
          if (offenders.length < 12) {
            offenders.push({
              tag: el.tagName,
              cls: el.className?.toString?.().slice(0, 80),
              left: Math.round(r.left),
              right: Math.round(r.right),
              w: Math.round(r.width),
            })
          }
        }
      }
      return {
        scrollWidth: scrollW,
        clientWidth: clientW,
        overflowsPage: scrollW > clientW + 1,
        offenders,
      }
    }, W)
    const pass = !overflow.overflowsPage && overflow.offenders.length === 0
    report.pages[route] = { pass, ...overflow }
    if (!pass) report.pass = false
    await page.screenshot({
      path: path.join(OUT, `${String(ROUTES.indexOf(route) + 1).padStart(2, '0')}-${route}.png`),
    })
    console.log(
      `[overflow] /app/${route} → ${pass ? 'PASS' : 'FAIL'} scrollW=${overflow.scrollWidth} offenders=${overflow.offenders.length}`,
      overflow.offenders.slice(0, 3),
    )
  }

  if (!report.tabbar.pass || !report.plus.pass) report.pass = false
  fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify(report, null, 2))
  await browser.close()
  console.log('\n=== MOBILE SUMMARY ===', report.pass ? 'PASS' : 'FAIL')
  process.exit(report.pass ? 0 : 1)
}

main().catch((e) => {
  console.error(e)
  process.exit(2)
})
