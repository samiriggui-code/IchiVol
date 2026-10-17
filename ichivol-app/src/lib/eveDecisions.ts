/**
 * Jugements d'Ève sur les propositions du moteur (GET /api/engine/eve/decisions).
 * Un jugement = un symbole à une clôture de bougie ; chaque livre dont le moteur voulait agir y a sa ligne.
 */

export type EngineProposalOutcome = {
  portfolio_code: string
  engine_action: 'OPEN' | 'CLOSE' | string
  engine_direction?: 'LONG' | 'SHORT' | string | null
  engine_decision?: string | null
  eve_action: string
  eve_accepts: boolean
  status?: string | null
  executed?: boolean
  risk_authorization?: string | null
}

export type EveDecision = {
  id: string
  created_at: string | null
  symbol: string
  timeframe: string
  baseline_decision: string | null
  eve_action: string | null
  execution_status: string
  degradation: string | null
  entry_gate: { decision: string | null; reason: string | null } | null
  coherence: number | null
  reasoning: string | null
  engine_proposals: EngineProposalOutcome[]
}

export async function getEveDecisions(limit = 200): Promise<{ autonomy_enabled: boolean; results: EveDecision[] }> {
  const res = await fetch(`/api/engine/eve/decisions?limit=${limit}`, { credentials: 'include' })
  if (!res.ok) throw new Error(`Erreur ${res.status}`)
  return res.json() as Promise<{ autonomy_enabled: boolean; results: EveDecision[] }>
}

export const EVE_ACTION_FR: Record<string, string> = {
  LONG: 'Acheter',
  SHORT: 'Vendre à découvert',
  CLOSE: 'Clôturer',
  HOLD: 'Garder',
  ABSTAIN: 'S’abstenir',
}

export function eveActionFr(a: string | null | undefined): string {
  return (a && EVE_ACTION_FR[a.toUpperCase()]) || '—'
}

export function engineProposalFr(p: Pick<EngineProposalOutcome, 'engine_action' | 'engine_direction'>): string {
  if (p.engine_action === 'CLOSE') return 'Clôturer'
  return p.engine_direction === 'SHORT' ? 'Vendre à découvert' : 'Acheter'
}

export type ProposalVerdict = 'executed' | 'refused_by_eve' | 'blocked_after' | 'pending'

/** Ce qui est arrivé à une proposition : exécutée, refusée par Ève, ou acceptée par Ève puis bloquée ensuite. */
export function proposalVerdict(p: EngineProposalOutcome): ProposalVerdict {
  if (p.executed) return 'executed'
  if (!p.eve_accepts) return 'refused_by_eve'
  if (p.status) return 'blocked_after'
  return 'pending'
}

const STATUS_FR: Record<string, string> = {
  refused_by_eve: 'Ève a refusé',
  no_dossier: 'Pas de dossier Ève',
  gate_rejected: 'Bloqué par la porte d’entrée de JEV',
  risk_kernel_refused: 'Refusé par le Risk Kernel',
  open_refused: 'Ouverture impossible',
  close_refused: 'Clôture impossible',
  close_no_position: 'Plus de position à fermer',
  opened: 'Ouvert',
  closed: 'Clôturé',
  dry_run_autonomy_off: 'Simulation (autonomie coupée)',
  dry_run_close: 'Simulation (autonomie coupée)',
  skipped_abstain: 'Ève s’abstient',
  skipped_hold: 'Ève garde la position',
  skipped_non_directional: 'Pas d’ordre à passer',
  skipped_symbol: 'Ce livre ne trade pas ce marché',
  missing_price: 'Prix manquant',
  refused: 'Refusé (données manquantes)',
}

export function proposalStatusFr(p: EngineProposalOutcome): string {
  if (p.executed) return p.engine_action === 'CLOSE' ? 'Clôturé' : 'Ouvert'
  return (p.status && STATUS_FR[p.status]) || (p.status ? p.status.replace(/_/g, ' ') : '—')
}
