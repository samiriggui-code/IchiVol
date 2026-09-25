import { copyFileSync, mkdirSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

function copyMd(srcDir, destDir) {
  mkdirSync(destDir, { recursive: true })
  for (const file of readdirSync(srcDir)) {
    if (file.endsWith('.md')) {
      copyFileSync(join(srcDir, file), join(destDir, file))
    }
  }
}

copyMd(join('src', 'knowledge', 'docs'), join('dist', 'knowledge', 'docs'))
// E1 — Eve skills markdown (on-demand prompt procedures)
copyMd(join('src', 'agent', 'skills'), join('dist', 'agent', 'skills'))
