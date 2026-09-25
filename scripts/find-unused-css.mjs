#!/usr/bin/env node
/** List class selectors in CSS files that never appear in src TSX/TS/CSS imports. Heuristic. */
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve('ichivol-app/src')
const cssFiles = []
const walk = (d) => {
  for (const f of fs.readdirSync(d)) {
    const p = path.join(d, f)
    if (fs.statSync(p).isDirectory()) walk(p)
    else if (f.endsWith('.css')) cssFiles.push(p)
  }
}
walk(root)
const code = []
const walkCode = (d) => {
  for (const f of fs.readdirSync(d)) {
    const p = path.join(d, f)
    if (fs.statSync(p).isDirectory()) walkCode(p)
    else if (/\.(tsx?|jsx?|html)$/.test(f)) code.push(fs.readFileSync(p, 'utf8'))
  }
}
walkCode(root)
const blob = code.join('\n')
const unused = []
for (const file of cssFiles) {
  const text = fs.readFileSync(file, 'utf8')
  const classes = new Set()
  for (const m of text.matchAll(/\.([a-zA-Z_][a-zA-Z0-9_-]*)/g)) {
    const name = m[1]
    if (name === 'up' || name === 'down' || name === 'active' || name === 'primary') continue
    classes.add(name)
  }
  for (const name of classes) {
    if (!blob.includes(name) && !blob.includes(`'${name}'`) && !blob.includes(`"${name}"`)) {
      unused.push(`${path.relative(root, file)} :: .${name}`)
    }
  }
}
console.log(`css_files=${cssFiles.length} unused_heuristic=${unused.length}`)
for (const u of unused.slice(0, 80)) console.log(u)
if (unused.length > 80) console.log(`… +${unused.length - 80} more`)
