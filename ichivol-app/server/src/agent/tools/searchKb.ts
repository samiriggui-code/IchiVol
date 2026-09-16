import { search } from '../../knowledge/retriever.js'
import type { ToolResult } from './types.js'

export interface KbHit {
  title: string
  url: string
  score: number
  excerpt: string
}

/**
 * Recherche KB Academy — même retriever TF-IDF, sortie JSON (pas de prose).
 */
export function searchKbTool(
  query: string,
  k = 4,
): ToolResult<{ hits: KbHit[] }> {
  const tool = 'search_kb'
  const q = query.trim()
  if (!q) return { ok: false, tool, error: 'query vide' }
  try {
    const chunks = search(q, k)
    return {
      ok: true,
      tool,
      data: {
        hits: chunks.map((c) => ({
          title: c.title,
          url: c.url,
          score: c.score,
          excerpt: c.text.slice(0, 280),
        })),
      },
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : 'kb search failed'
    return { ok: false, tool, error: message }
  }
}
