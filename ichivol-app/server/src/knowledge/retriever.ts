import { loadKnowledgeBase } from './loader.js'
import type { KnowledgeChunk, ScoredChunk } from './types.js'

const STOPWORDS = new Set([
  'the', 'a', 'an', 'is', 'are', 'of', 'to', 'in', 'on', 'for', 'and', 'or', 'as',
  'it', 'this', 'that', 'be', 'with', 'by', 'can', 'may', 'when', 'what', 'how',
  'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'et', 'ou', 'est', 'sont',
  'que', 'qui', 'pour', 'dans', 'sur', 'avec', 'ce', 'cette', 'quoi', 'comment',
])

function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter((t) => t.length > 1 && !STOPWORDS.has(t))
}

interface IndexedChunk extends KnowledgeChunk {
  termFreq: Map<string, number>
}

let index: IndexedChunk[] | null = null
let idf: Map<string, number> | null = null

function buildIndex(): void {
  const chunks = loadKnowledgeBase()
  const docFreq = new Map<string, number>()

  const indexed: IndexedChunk[] = chunks.map((chunk) => {
    const tokens = tokenize(chunk.text)
    const termFreq = new Map<string, number>()
    for (const t of tokens) termFreq.set(t, (termFreq.get(t) ?? 0) + 1)
    for (const t of termFreq.keys()) docFreq.set(t, (docFreq.get(t) ?? 0) + 1)
    return { ...chunk, termFreq }
  })

  const n = indexed.length || 1
  const computedIdf = new Map<string, number>()
  for (const [term, df] of docFreq) {
    computedIdf.set(term, Math.log(1 + n / df))
  }

  index = indexed
  idf = computedIdf
}

export function search(query: string, k = 4): ScoredChunk[] {
  if (!index || !idf) buildIndex()
  const queryTerms = tokenize(query)
  if (queryTerms.length === 0 || !index || !idf) return []

  const scored = index.map((chunk) => {
    let score = 0
    for (const term of queryTerms) {
      const tf = chunk.termFreq.get(term) ?? 0
      if (tf === 0) continue
      score += tf * (idf!.get(term) ?? 0)
    }
    return { chunk, score }
  })

  return scored
    .filter((s) => s.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, k)
    .map(({ chunk, score }) => ({
      docId: chunk.docId,
      title: chunk.title,
      url: chunk.url,
      score,
      text: chunk.text,
    }))
}

export function reloadKnowledgeBase(): void {
  index = null
  idf = null
  buildIndex()
}
