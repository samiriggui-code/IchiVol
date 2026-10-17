/** Appels au moteur pour la page Ève : état du pilote automatique et évaluation à la demande. */

type PaperAutonomy = { autonomy_enabled?: boolean }

export type EveEvaluation = {
  dossier_id?: string | null
  synthesis?: { action?: string | null } | null
  verdict?: { action?: string | null } | null
  degradation?: { level?: string | null; reasons?: string[] } | null
}

/** LA source de l'état du pilote automatique d'Ève (`EVE_PAPER_AUTONOMY`). */
export async function getPaperAutonomy(): Promise<boolean | null> {
  const r = await fetch('/api/engine/eve/paper-autonomy', { credentials: 'include' })
  if (!r.ok) return null
  const data = (await r.json()) as PaperAutonomy
  return typeof data.autonomy_enabled === 'boolean' ? data.autonomy_enabled : null
}

/**
 * Demande à Ève d'évaluer un instrument maintenant. Crée un dossier (modes, JEV, Risk Kernel en essai à blanc)
 * sans rien ouvrir : `paper_dry_run=true`.
 */
export async function evaluateWithEve(symbol: string, timeframe = '1h'): Promise<EveEvaluation> {
  const sym = symbol.trim().toUpperCase()
  const r = await fetch(
    `/api/engine/eve/evaluate/${encodeURIComponent(sym)}?timeframe=${encodeURIComponent(timeframe)}&paper_dry_run=true`,
    { method: 'POST', credentials: 'include' },
  )
  const data = (await r.json().catch(() => ({}))) as EveEvaluation & { detail?: string }
  if (!r.ok) throw new Error(data.detail || `Évaluation refusée (${r.status})`)
  return data
}
