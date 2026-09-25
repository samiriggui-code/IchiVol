/**
 * Compare automatiquement la maquette (design-reference/ichivol-workspace) et l'app, page par page.
 *
 * Pour chaque page et chaque largeur (1440, 390), relève dans la maquette chaque classe CSS
 * utilisée dans le contenu (<main id="app">), puis vérifie dans l'app :
 *   - que la classe existe (sinon MANQUANT),
 *   - taille / graisse / famille de police identiques,
 *   - hauteur du premier élément à ±4 px (les blocs de données réelles peuvent varier : voir IGNORE_HEIGHT).
 * Écrit docs/ui-port/compare/<page>.json + docs/ui-port/compare/RAPPORT.md.
 * Code de sortie 1 s'il reste un écart. « Conforme » = 0 écart.
 *
 * Usage :
 *   APP_BASE=http://127.0.0.1:5180 SMOKE_EMAIL=… SMOKE_PASS=… node scripts/compare-maquette.mjs [page…]
 *   (sans argument : les 11 pages)
 * Option : CHROME=/chemin/chrome si Chrome n'est pas dans /usr/bin.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import puppeteer from 'puppeteer-core'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const REPO = path.resolve(HERE, '../..')
const MAQ = `file://${path.join(REPO, 'design-reference/ichivol-workspace/index.html')}`
const OUT = path.join(REPO, 'docs/ui-port/compare')
const APP_BASE = process.env.APP_BASE ?? 'http://127.0.0.1:5180'
const CHROME =
  process.env.CHROME ??
  ['/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'].find((p) =>
    fs.existsSync(p),
  )

/** id maquette → route app */
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
const WIDTHS = [1440, 390]
/** Blocs dont la hauteur dépend des données réelles (listes, graphiques, tableaux). */
const IGNORE_HEIGHT = new Set([
  'watchlist', 'chart', 'chart-wrap', 'table-wrap', 'market-layout', 'grid', 'card', 'card-body',
  'analysis-panel', 'desk-overview', 'desk-allocation', 'world-view', 'heatmap', 'chat',
])

/**
 * Classes d'ÉTAT ou de DONNÉES : leur présence dépend des valeurs réelles (hausse/baisse, statut,
 * élément sélectionné…). Pas exigées ; comparées seulement si elles existent dans l'app.
 */
const OPTIONAL = new Set([
  'up', 'down', 'active', 'selected', 'green', 'amber', 'red', 'gray', 'blue', 'teal', 'neutral',
  'strong', 'subtle', 'featured', 'right', 'eth', 'clickable',
  // Graphiques SVG de démonstration remplacés par les vrais graphiques (lightweight-charts) :
  'chart', 'chart-labels', 'candle-chart', 'cloud-layer', 'levels-layer',
])

const COLLECT = (rootSel) => {
  const root = document.querySelector(rootSel)
  if (!root) return null
  const seen = {}
  for (const el of root.querySelectorAll('[class]')) {
    for (const c of el.classList) {
      if (seen[c] || !/^[a-z][a-z0-9-]*$/i.test(c)) continue
      const cs = getComputedStyle(el)
      if (cs.display === 'none') continue
      const r = el.getBoundingClientRect()
      seen[c] = {
        fontSize: parseFloat(cs.fontSize),
        fontWeight: cs.fontWeight,
        fontFamily: cs.fontFamily.split(',')[0].replace(/["']/g, '').trim(),
        height: Math.round(r.height),
      }
    }
  }
  return seen
}

const FIND = (rootSel, classes) => {
  const root = document.querySelector(rootSel) ?? document.body
  const out = {}
  for (const c of classes) {
    const el = [...root.querySelectorAll(`.${CSS.escape(c)}`)].find(
      (e) => getComputedStyle(e).display !== 'none',
    )
    if (!el) {
      out[c] = null
      continue
    }
    const cs = getComputedStyle(el)
    out[c] = {
      fontSize: parseFloat(cs.fontSize),
      fontWeight: cs.fontWeight,
      fontFamily: cs.fontFamily.split(',')[0].replace(/["']/g, '').trim(),
      height: Math.round(el.getBoundingClientRect().height),
    }
  }
  return out
}

async function maquette(browser, id, width) {
  const page = await browser.newPage()
  await page.setViewport({ width, height: 900 })
  await page.goto(`${MAQ}#${id}`, { waitUntil: 'load' })
  await new Promise((r) => setTimeout(r, 400))
  const data = await page.evaluate(COLLECT, '#app')
  await page.close()
  return data
}

async function login(browser) {
  if (!process.env.SMOKE_EMAIL) return
  const page = await browser.newPage()
  await page.goto(`${APP_BASE}/login`, { waitUntil: 'networkidle2' })
  const email = (await page.$('input[type=email]')) || (await page.$('input[type=text]'))
  await email.type(process.env.SMOKE_EMAIL)
  await (await page.$('input[type=password]')).type(process.env.SMOKE_PASS ?? '')
  await Promise.all([
    page.click('button[type=submit]'),
    page.waitForNavigation({ waitUntil: 'networkidle2' }).catch(() => null),
  ])
  await page.close()
}

async function app(browser, route, width, classes) {
  const page = await browser.newPage()
  await page.setViewport({ width, height: 900 })
  await page.goto(`${APP_BASE}${route}`, { waitUntil: 'networkidle2', timeout: 60000 }).catch(() => null)
  await new Promise((r) => setTimeout(r, 3000))
  const data = await page.evaluate(FIND, '.dash-content', classes)
  await page.close()
  return data
}

function compare(maq, got) {
  const ecarts = []
  for (const [c, m] of Object.entries(maq)) {
    const a = got[c]
    if (!a) {
      if (!OPTIONAL.has(c)) ecarts.push({ classe: c, type: 'MANQUANT' })
      continue
    }
    if (Math.abs(a.fontSize - m.fontSize) > 0.5)
      ecarts.push({ classe: c, type: 'taille police', maquette: m.fontSize, app: a.fontSize })
    if (a.fontWeight !== m.fontWeight)
      ecarts.push({ classe: c, type: 'graisse', maquette: m.fontWeight, app: a.fontWeight })
    if (a.fontFamily !== m.fontFamily)
      ecarts.push({ classe: c, type: 'police', maquette: m.fontFamily, app: a.fontFamily })
    if (!IGNORE_HEIGHT.has(c) && Math.abs(a.height - m.height) > 4)
      ecarts.push({ classe: c, type: 'hauteur', maquette: m.height, app: a.height })
  }
  return ecarts
}

const wanted = process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(PAGES)
fs.mkdirSync(OUT, { recursive: true })
const browser = await puppeteer.launch({ executablePath: CHROME, headless: true, args: ['--no-sandbox'] })
await login(browser)

const rapport = ['# Comparaison maquette ↔ app', '', '| Page | 1440 | 390 |', '|---|---|---|']
let total = 0
for (const id of wanted) {
  const res = {}
  for (const w of WIDTHS) {
    const maq = await maquette(browser, id, w)
    if (!maq) throw new Error(`Maquette ${id} introuvable`)
    const got = await app(browser, PAGES[id], w, Object.keys(maq))
    res[w] = compare(maq, got)
    total += res[w].length
  }
  fs.writeFileSync(path.join(OUT, `${id}.json`), JSON.stringify(res, null, 2))
  const cell = (n) => (n === 0 ? '✅ 0' : `❌ ${n}`)
  rapport.push(`| ${id} | ${cell(res[1440].length)} | ${cell(res[390].length)} |`)
  console.log(id, '1440:', res[1440].length, 'écarts · 390:', res[390].length, 'écarts')
}
rapport.push('', `Total écarts : **${total}**. Détail par page : \`docs/ui-port/compare/<page>.json\`.`)
fs.writeFileSync(path.join(OUT, 'RAPPORT.md'), rapport.join('\n') + '\n')
await browser.close()
process.exit(total === 0 ? 0 : 1)
