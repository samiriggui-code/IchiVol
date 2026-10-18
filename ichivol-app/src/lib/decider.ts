/**
 * Qui a décidé un trade paper : le moteur seul, Ève (avec JEV), le moteur contre l'avis d'Ève, ou une personne.
 * Quand Ève refuse une proposition, le moteur la trade quand même au nom de `engine_over_eve`
 * (`entry_signal.decided_by`) : le résultat dit si Ève avait raison de refuser.
 * Le moteur marque ses lots `auto_watchlist` ; Ève ouvre les siens au nom de `eve_intelligence`
 * avec son dossier dans `entry_signal.eve_dossier_id` (engine/app/eve/paper_submit.py).
 */

import type { PaperPosition } from './paper'

export type Decider = 'engine' | 'eve' | 'engine_over_eve' | 'manual'

export const EVE_USER_ID = 'eve_intelligence'

export const DECIDERS: Decider[] = ['eve', 'engine_over_eve', 'engine', 'manual']

export const DECIDER_LABEL: Record<Decider, string> = {
  engine: 'Moteur seul',
  eve: 'Ève',
  engine_over_eve: 'Moteur contre Ève',
  manual: 'Manuel',
}

export const DECIDER_EXPLAIN: Record<Decider, string> = {
  engine: 'Ouvert directement par le signal du moteur, sans avis d’Ève.',
  eve: 'Proposé par le moteur, accepté par Ève (avec JEV) et par l’audit indépendant, validé par le Risk Kernel.',
  engine_over_eve: 'Ève a refusé, le moteur a tradé quand même (Risk Kernel compris). Un trade perdant ici veut dire qu’Ève avait raison.',
  manual: 'Ouvert à la main depuis l’application.',
}

type DeciderInput = Pick<PaperPosition, 'source' | 'user_id'> & { entry_signal?: Record<string, unknown> | null }

export function deciderOf(p: DeciderInput): Decider {
  if (p.entry_signal && p.entry_signal.decided_by === 'engine_over_eve') return 'engine_over_eve'
  if (p.user_id === EVE_USER_ID || (p.entry_signal && p.entry_signal.eve_dossier_id)) return 'eve'
  if (p.source === 'auto_watchlist') return 'engine'
  return 'manual'
}

/** Dossier Ève à l'origine du lot, s'il y en a un. */
export function eveDossierId(p: DeciderInput): string | null {
  const id = p.entry_signal?.eve_dossier_id
  return typeof id === 'string' && id ? id : null
}

export type DeciderScore = {
  decider: Decider
  trades: number
  wins: number
  losses: number
  winRate: number | null
  net: number
  avgWin: number | null
  avgLoss: number | null
  fees: number
  open: number
}

/** Bilan des trades clôturés par décideur (résultat net de frais, tel que le moteur l'a enregistré). */
export function scoreByDecider(positions: Array<PaperPosition>): Record<Decider, DeciderScore> {
  const out = Object.fromEntries(
    DECIDERS.map((d) => [
      d,
      { decider: d, trades: 0, wins: 0, losses: 0, winRate: null, net: 0, avgWin: null, avgLoss: null, fees: 0, open: 0 },
    ]),
  ) as Record<Decider, DeciderScore>
  const sums = Object.fromEntries(DECIDERS.map((d) => [d, { win: 0, loss: 0 }])) as Record<
    Decider,
    { win: number; loss: number }
  >
  for (const p of positions) {
    const d = deciderOf(p)
    const s = out[d]
    if (p.status === 'OPEN') {
      s.open += 1
      continue
    }
    if (p.status !== 'CLOSED' || p.realized_pnl == null || !Number.isFinite(p.realized_pnl)) continue
    s.trades += 1
    s.net += p.realized_pnl
    s.fees += (p.entry_fee ?? 0) + (p.exit_fee ?? 0)
    if (p.realized_pnl > 0) {
      s.wins += 1
      sums[d].win += p.realized_pnl
    } else {
      s.losses += 1
      sums[d].loss += p.realized_pnl
    }
  }
  for (const d of DECIDERS) {
    const s = out[d]
    s.winRate = s.trades > 0 ? s.wins / s.trades : null
    s.avgWin = s.wins > 0 ? sums[d].win / s.wins : null
    s.avgLoss = s.losses > 0 ? sums[d].loss / s.losses : null
  }
  return out
}
