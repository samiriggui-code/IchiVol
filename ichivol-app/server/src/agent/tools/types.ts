/** Résultat tool read-only — jamais de prose. */
export type ToolResult<T = unknown> =
  | { ok: true; tool: string; data: T }
  | { ok: false; tool: string; error: string }

export interface ToolRunContext {
  userId: string
  mode: string
  question: string
  /** Symbole résolu (decision / live / hint). */
  symbol?: string
  timeframe?: string
}

export const READ_ONLY_TOOLS = [
  'get_symbol_context',
  'compare_timeframes',
  'detect_signal',
  'get_decision_detail',
  'get_live_snapshot',
  'get_journal_context',
  'search_kb',
] as const

export type ReadOnlyToolName = (typeof READ_ONLY_TOOLS)[number]
