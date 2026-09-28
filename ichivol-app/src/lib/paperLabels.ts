/** Libellés FR pour codes moteur paper (refus risque / sorties) — jamais le snake_case brut. */

const RISK_REFUSAL_FR: Record<string, string> = {
  short_not_allowed: 'Vente à découvert non autorisée',
  stale_data: 'Données trop anciennes',
  no_atr_stop: 'Stop ATR indisponible',
  position_already_open: 'Position déjà ouverte',
  signal_already_processed: 'Signal déjà traité',
  max_positions: 'Plafond de positions',
  open_risk_cap: 'Risque ouvert au plafond',
  symbol_exposure_cap: 'Exposition symbole au plafond',
  daily_loss_halt: 'Perte du jour au plafond',
  kill_switch: "Arrêt d'urgence",
  insufficient_cash_or_size: 'Cash insuffisant',
  order_not_executed: 'Ordre non exécuté',
}

const ORDER_REASON_FR: Record<string, string> = {
  open: 'Ouverture',
  manual_close: 'Clôture manuelle',
  partial_tp: 'Prise partielle',
  reinforce: 'Renfort',
  direction_flipped: 'Sens inversé',
  pipeline_flipped: 'Signal inversé',
  pipeline_downgraded: 'Signal dégradé',
  stop: 'Stop touché',
  stop_hit: 'Stop touché',
  stop_loss: 'Stop touché',
  take_profit: 'Objectif atteint',
  take_profit_hit: 'Objectif atteint',
  time_stop: 'Sortie temps',
  horizon_end: "Fin d'horizon",
  window_end: 'Fin de fenêtre',
  exposure_off: 'Exposition coupée',
}

/** Refus Risk Kernel / SIGNAL_REJECTED — jamais le code Python brut. */
export function labelRiskRefusal(reason: string | undefined | null): string {
  if (!reason) return 'Refusé'
  return RISK_REFUSAL_FR[reason] ?? 'Refusé par le risque'
}

/** Motif d'ordre paper (ouverture / clôture) — chaîne vide si inconnu. */
export function labelPaperOrderReason(reason: string | null | undefined): string {
  if (!reason) return ''
  return ORDER_REASON_FR[reason] ?? ''
}
