import { copyFileSync, mkdirSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

const src = join('src', 'knowledge', 'docs')
const dest = join('dist', 'knowledge', 'docs')

mkdirSync(dest, { recursive: true })
for (const file of readdirSync(src)) {
  if (file.endsWith('.md')) {
    copyFileSync(join(src, file), join(dest, file))
  }
}
