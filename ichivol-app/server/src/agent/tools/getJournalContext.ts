import { db } from '../../db.js'
import type { ToolResult } from './types.js'

export interface JournalContextRow {
  symbol: string
  interval: string
  bias: string
  signalKind: string | null
  gateDecision: string | null
  confidence: number | null
  rvol: number
  status: string
  note: string | null
  updatedAt: string
}

/**
 * N dernières décisions user (journal) — read-only Prisma.
 */
export async function getJournalContextTool(
  userId: string,
  symbol?: string,
  limit = 8,
): Promise<ToolResult<{ rows: JournalContextRow[] }>> {
  const tool = 'get_journal_context'
  try {
    const rows = await db.decision.findMany({
      where: {
        userId,
        ...(symbol?.trim()
          ? { symbol: symbol.trim().toUpperCase() }
          : {}),
      },
      orderBy: { updatedAt: 'desc' },
      take: Math.min(Math.max(limit, 1), 20),
      select: {
        symbol: true,
        interval: true,
        bias: true,
        signalKind: true,
        gateDecision: true,
        confidence: true,
        rvol: true,
        status: true,
        note: true,
        updatedAt: true,
      },
    })
    return {
      ok: true,
      tool,
      data: {
        rows: rows.map((r) => ({
          symbol: r.symbol,
          interval: r.interval,
          bias: r.bias,
          signalKind: r.signalKind,
          gateDecision: r.gateDecision,
          confidence: r.confidence,
          rvol: r.rvol,
          status: r.status,
          note: r.note,
          updatedAt: r.updatedAt.toISOString(),
        })),
      },
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : 'journal query failed'
    return { ok: false, tool, error: message }
  }
}
