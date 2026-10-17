import { engineAgentCommand } from '../engineAgentChannel.js'
import type { ToolResult } from './types.js'

/** Lecture d'un Dossier IchiVol — jamais d'exécution. */
export async function getEveDossierTool(dossierId: string): Promise<ToolResult<unknown>> {
  const id = dossierId.trim()
  if (!id) return { ok: false, tool: 'get_eve_dossier', error: 'dossier_id_required' }
  const res = await engineAgentCommand({ cmd: 'get_eve_dossier', args: { dossier_id: id } })
  if (!res.ok) return { ok: false, tool: 'get_eve_dossier', error: res.error }
  return { ok: true, tool: 'get_eve_dossier', data: res.data }
}

export async function listEveDossiersTool(opts?: {
  symbol?: string
  limit?: number
}): Promise<ToolResult<unknown>> {
  const res = await engineAgentCommand({
    cmd: 'list_eve_dossiers',
    args: {
      symbol: opts?.symbol,
      limit: opts?.limit ?? 10,
    },
  })
  if (!res.ok) return { ok: false, tool: 'list_eve_dossiers', error: res.error }
  return { ok: true, tool: 'list_eve_dossiers', data: res.data }
}

export async function getEveContextTool(
  symbol: string,
  timeframe = '1h',
): Promise<ToolResult<unknown>> {
  const sym = symbol.trim().toUpperCase()
  if (!sym) return { ok: false, tool: 'get_eve_context', error: 'symbol_required' }
  const res = await engineAgentCommand({
    cmd: 'get_eve_context',
    args: { symbol: sym, timeframe },
  })
  if (!res.ok) return { ok: false, tool: 'get_eve_context', error: res.error }
  return { ok: true, tool: 'get_eve_context', data: res.data }
}
