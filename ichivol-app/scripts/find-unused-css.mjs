#!/usr/bin/env node
/**
 * List class selectors defined in src/index.css that are not referenced in
 * any src/ file matching .{tsx,ts,css} (except index.css itself).
 *
 * Usage:
 *   node scripts/find-unused-css.mjs
 *   node scripts/find-unused-css.mjs --out ../docs/ui-clean/unused-css-index.txt
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const appRoot = path.resolve(__dirname, '..')
const srcRoot = path.join(appRoot, 'src')
const indexCssPath = path.join(srcRoot, 'index.css')

const outArg = process.argv.indexOf('--out')
const outPath =
  outArg >= 0 && process.argv[outArg + 1]
    ? path.resolve(process.cwd(), process.argv[outArg + 1])
    : null

function walk(dir, exts, acc = []) {
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, ent.name)
    if (ent.isDirectory()) {
      if (ent.name === 'node_modules' || ent.name === 'dist') continue
      walk(full, exts, acc)
    } else if (exts.some((e) => ent.name.endsWith(e))) {
      acc.push(full)
    }
  }
  return acc
}

/** Extract simple class names from CSS selectors (ignores :root, @keyframes, etc.). */
function extractClassSelectors(css) {
  const classes = new Set()
  // Strip comments
  const cleaned = css.replace(/\/\*[\s\S]*?\*\//g, '')
  // Roughly split into rule blocks; also catch selectors in @media
  const selectorChunks = cleaned.replace(/\{[^{}]*\}/g, ' ')
  // Match .classname (allow BEM -- and __ and digits)
  const re = /\.([A-Za-z_][\w-]*)/g
  let m
  while ((m = re.exec(selectorChunks))) {
    classes.add(m[1])
  }
  return classes
}

function fileReferencesClass(content, className) {
  // Match className as a whole token in strings / class lists / CSS
  const re = new RegExp(
    `(?:^|[^A-Za-z0-9_-])${className.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?:[^A-Za-z0-9_-]|$)`,
  )
  return re.test(content)
}

const indexCss = fs.readFileSync(indexCssPath, 'utf8')
const defined = extractClassSelectors(indexCss)

const refFiles = walk(srcRoot, ['.tsx', '.ts', '.css']).filter(
  (f) => path.resolve(f) !== path.resolve(indexCssPath),
)

const contents = refFiles.map((f) => ({
  file: f,
  text: fs.readFileSync(f, 'utf8'),
}))

const unused = [...defined].sort().filter((cls) => {
  return !contents.some(({ text }) => fileReferencesClass(text, cls))
})

const report = unused.join('\n') + (unused.length ? '\n' : '')

if (outPath) {
  fs.mkdirSync(path.dirname(outPath), { recursive: true })
  fs.writeFileSync(outPath, report, 'utf8')
  console.error(
    `Wrote ${unused.length} unused class names → ${path.relative(process.cwd(), outPath)}`,
  )
} else {
  process.stdout.write(report)
}

console.error(
  `index.css classes: ${defined.size}; unused (no ref outside index.css): ${unused.length}`,
)
