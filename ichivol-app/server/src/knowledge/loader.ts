import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { KnowledgeChunk } from './types.js'

const DOCS_DIR = join(dirname(fileURLToPath(import.meta.url)), 'docs')
const MIN_CHUNK_WORDS = 40

function parseFrontmatter(raw: string): { meta: Record<string, string>; body: string } {
  const match = raw.match(/^---\n([\s\S]*?)\n---\n?/)
  if (!match) return { meta: {}, body: raw }

  const meta: Record<string, string> = {}
  for (const line of match[1].split('\n')) {
    const idx = line.indexOf(':')
    if (idx === -1) continue
    const key = line.slice(0, idx).trim()
    let value = line.slice(idx + 1).trim()
    if (value.startsWith('"') && value.endsWith('"')) value = value.slice(1, -1)
    meta[key] = value
  }
  return { meta, body: raw.slice(match[0].length) }
}

function parseTags(raw: string | undefined): string[] {
  if (!raw) return []
  return raw
    .replace(/^\[|\]$/g, '')
    .split(',')
    .map((t) => t.trim().replace(/^"|"$/g, ''))
    .filter(Boolean)
}

function splitIntoChunks(body: string): string[] {
  const sections = body.split(/\n(?=##\s)/g)
  const chunks: string[] = []
  let buffer = ''

  for (const section of sections) {
    const wordCount = section.trim().split(/\s+/).length
    if (wordCount < MIN_CHUNK_WORDS && buffer) {
      buffer += '\n' + section
    } else {
      if (buffer) chunks.push(buffer.trim())
      buffer = section
    }
  }
  if (buffer.trim()) chunks.push(buffer.trim())
  return chunks.filter(Boolean)
}

export function loadKnowledgeBase(): KnowledgeChunk[] {
  if (!existsSync(DOCS_DIR)) {
    console.warn(`[knowledge] docs manquants: ${DOCS_DIR} — RAG désactivé`)
    return []
  }

  const files = readdirSync(DOCS_DIR).filter((f) => f.endsWith('.md'))
  const chunks: KnowledgeChunk[] = []

  for (const file of files) {
    const raw = readFileSync(join(DOCS_DIR, file), 'utf8')
    const { meta, body } = parseFrontmatter(raw)
    const docId = file.replace(/\.md$/, '')
    const title = meta.title ?? docId
    const url = meta.url ?? ''
    const tags = parseTags(meta.tags)

    for (const text of splitIntoChunks(body)) {
      chunks.push({ docId, title, url, tags, text })
    }
  }

  return chunks
}
