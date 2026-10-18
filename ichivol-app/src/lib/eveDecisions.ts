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
  /** Qui a tranché : Ève (d'accord avec le moteur, audit favorable), le moteur contre Ève, ou l'audit. */
  decided_by?: 'eve' | 'engine_over_eve' | 'audit' | null
  audit?: { verdict: 'allow' | 'block'; reason: string; choice?: string | null; score?: number | null } | null
  /** Résultat du vrai trade (position) ou du trade rejoué sans argent (refus d'avant le changement, blocage de l'audit). */
  result?: TradeResult | null
}

export type TradeResult = {
  kind: 'position' | 'shadow'
  status: 'OPEN' | 'CLOSED' | string | null
  exit_reason: string | null
  pnl_r: number | null
  pnl_pct?: number | null
}

export type Judge = 'analyst' | 'challenger' | 'guardian' | 'audit'

export type Opinion = {
  who: Judge
  action: string | null
  stance: 'pour' | 'contre' | 'neutre'
  details: string[]
}

export const JUDGE_LABEL: Record<Judge, string> = {
  analyst: 'Analyste',
  challenger: 'Contradicteur',
  guardian: 'Gardien du risque',
  audit: 'Audit indépendant',
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
  /** Pourquoi Ève a répondu ça, en une phrase. */
  why?: string | null
  /** Avis de chacun des juges d'Ève, pour ou contre la proposition du moteur. */
  opinions?: Opinion[]
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

export type ProposalVerdict = 'executed' | 'engine_over_eve' | 'blocked_by_audit' | 'refused_by_eve' | 'blocked_after' | 'pending'

/** Ce qui est arrivé à une proposition. Depuis que le moteur trade contre l'avis d'Ève, un refus d'Ève n'empêche plus
 * le trade ; « refused_by_eve » ne reste que pour les jugements plus anciens. */
export function proposalVerdict(p: EngineProposalOutcome): ProposalVerdict {
  if (p.decided_by === 'audit') return 'blocked_by_audit'
  if (p.decided_by === 'engine_over_eve') return p.executed ? 'engine_over_eve' : 'blocked_after'
  if (p.executed) return 'executed'
  if (!p.eve_accepts) return 'refused_by_eve'
  if (p.status) return 'blocked_after'
  return 'pending'
}

export type Rightness = { tone: 'ok' | 'ko' | 'wait'; text: string }

function fmtR(v: number): string {
  return `${v > 0 ? '+' : ''}${v.toFixed(1).replace('.', ',')} R`
}

/** Ève (ou l'audit) avait-elle raison ? Se lit sur le résultat du trade : vrai trade du moteur contre Ève, ou trade
 * rejoué sans argent quand un trade n'a pas eu lieu. */
export function rightness(p: EngineProposalOutcome): Rightness | null {
  const r = p.result
  if (!r) return null
  const who = p.decided_by === 'audit' ? 'L’audit' : 'Ève'
  if (r.status !== 'CLOSED') {
    return {
      tone: 'wait',
      text: r.kind === 'shadow' ? 'Trade rejoué sans argent en cours.' : 'Trade en cours, pas encore de verdict.',
    }
  }
  const pnl = r.pnl_r ?? (r.pnl_pct != null ? Math.sign(r.pnl_pct) : null)
  if (pnl == null) return null
  const res = r.pnl_r != null ? ` (${fmtR(r.pnl_r)})` : ''
  const won = pnl > 0
  if (p.decided_by === 'eve' || (p.executed && p.eve_accepts)) {
    return won
      ? { tone: 'ok', text: `Trade gagnant${res} : Ève a eu raison d’accepter.` }
      : { tone: 'ko', text: `Trade perdant${res} : Ève a eu tort d’accepter.` }
  }
  const traded = r.kind === 'position' ? 'Le moteur a tradé contre Ève' : 'Rejoué sans argent, ce trade'
  return won
    ? { tone: 'ko', text: `${traded} : gagnant${res}. ${who} a eu tort de refuser.` }
    : { tone: 'ok', text: `${traded} : perdant${res}. ${who} avait raison de refuser.` }
}

const STATUS_FR: Record<string, string> = {
  refused_by_eve: 'Ève a refusé',
  blocked_by_audit: 'Bloqué par l’audit indépendant',
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
