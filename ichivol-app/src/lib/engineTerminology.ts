/**
 * Terminologie technique moteur → français (front).
 *
 * Règle : aucun code snake_case ne doit apparaître tel quel dans l’UI.
 * Ajouter ici chaque nouveau code renvoyé par le moteur (raisons, risques,
 * invalidation, stages pipeline, refus paper, motifs de sortie).
 *
 * Usage unique recommandé : `labelEngineCode(code)`.
 */

/** Tokens techniques fréquents — utilisés aussi pour humaniser un code inconnu. */
const TOKEN_FR: Record<string, string> = {
  adx: 'ADX',
  atr: 'ATR',
  avwap: 'AVWAP',
  bos: 'BOS',
  choch: 'CHoCH',
  chikou: 'Chikou',
  cmf: 'CMF',
  cvd: 'CVD',
  fvg: 'FVG',
  hvn: 'HVN',
  kijun: 'Kijun',
  kumo: 'nuage',
  lvn: 'LVN',
  mtf: 'multi-timeframe',
  oi: 'open interest',
  rvol: 'volume relatif',
  rsi: 'RSI',
  senkou: 'Senkou',
  tenkan: 'Tenkan',
  tk: 'Tenkan/Kijun',
  va: 'value area',
  vwap: 'VWAP',
  above: 'au-dessus',
  below: 'sous',
  back: 'retour',
  inside: 'dans',
  outside: 'hors',
  beyond: 'au-delà',
  break: 'cassure',
  breakout: 'cassure',
  bullish: 'haussier',
  bearish: 'baissier',
  long: 'long',
  short: 'short',
  aligned: 'aligné',
  opposed: 'opposé',
  confirms: 'confirme',
  invalidates: 'invalide',
  close: 'clôture',
  price: 'prix',
  volume: 'volume',
  trend: 'tendance',
  regime: 'régime',
  structure: 'structure',
  direction: 'direction',
  insufficient: 'insuffisant',
  confluence: 'confluence',
  confirmation: 'confirmation',
  participation: 'participation',
  anomaly: 'anomalie',
  accelerating: 'en accélération',
  strong: 'fort',
  significant: 'significatif',
  normal: 'normal',
  low: 'faible',
  high: 'élevé',
  dead: 'mort',
  extreme: 'extrême',
  developing: 'en formation',
  trending: 'en tendance',
  no: 'pas de',
  not: 'non',
  allowed: 'autorisé',
  blocked: 'bloqué',
  fail: 'échec',
  pass: 'ok',
  hit: 'touché',
  stop: 'stop',
  target: 'objectif',
  take: 'prise',
  profit: 'profit',
  manual: 'manuel',
  flipped: 'inversé',
  downgraded: 'dégradé',
  pipeline: 'pipeline',
  horizon: 'horizon',
  end: 'fin',
  window: 'fenêtre',
  exposure: 'exposition',
  risk: 'risque',
  cap: 'plafond',
  max: 'maximum',
  open: 'ouvert',
  closed: 'fermé',
  stale: 'périmé',
  data: 'données',
  cash: 'cash',
  size: 'taille',
  kill: 'arrêt',
  switch: 'urgence',
  daily: 'quotidien',
  loss: 'perte',
  halt: 'arrêt',
  symbol: 'symbole',
  positions: 'positions',
  already: 'déjà',
  processed: 'traité',
  signal: 'signal',
  order: 'ordre',
  executed: 'exécuté',
  reinforce: 'renfort',
  partial: 'partiel',
  tp: 'TP',
  time: 'temps',
  force: 'forcé',
  flat: 'à plat',
  buy: 'achat',
  sell: 'vente',
  pressure: 'pression',
  balanced: 'équilibré',
  rising: 'en hausse',
  falling: 'en baisse',
  funding: 'funding',
  crowded: 'encombré',
  congestion: 'congestion',
  thin: 'fin',
  liquidity: 'liquidité',
  wrong: 'mauvais',
  side: 'côté',
  value: 'valeur',
  area: 'zone',
  future: 'futur',
  cross: 'croisement',
  clear: 'clair',
  bias: 'biais',
  unresolved: 'non résolu',
  unfavorable: 'défavorable',
  historical: 'historique',
  evidence: 'preuve',
  expectancy: 'espérance',
  poor: 'faible',
  confirmed: 'confirmé',
  semantics: 'sémantique',
  neutral: 'neutre',
  history: 'historique',
  bars: 'barres',
  candles: 'bougies',
  zone: 'zone',
  retest: 'retest',
  swings: 'swings',
  detectors: 'détecteurs',
  ledger: 'ledger',
  mark: 'marque',
  longer: 'plus',
  without: 'sans',
  locked: 'verrouillé',
  armed: 'armé',
  gap: 'écart',
  distance: 'distance',
  weak: 'faible',
  too: 'trop',
  small: 'petit',
}

/**
 * Glossaire des codes moteur affichés à l’utilisateur.
 * Clés = codes exacts (snake_case) renvoyés par le moteur.
 */
export const ENGINE_TERM_FR: Record<string, string> = {
  // ── Ichimoku — bullish ──────────────────────────────────────────
  price_above_kumo: 'Prix au-dessus du nuage (kumo)',
  bullish_tk_cross: 'Croisement Tenkan/Kijun haussier',
  bullish_future_kumo: 'Nuage futur haussier (Senkou A > B)',
  chikou_confirmation: 'Chikou confirme (espace libre)',
  kumo_breakout_bullish: 'Cassure haussière du nuage',
  bullish_trend: 'Tendance haussière',
  bullish_unconfirmed: 'Hausse non confirmée',
  best_cloud_bullish: 'Meilleur nuage haussier',
  best_cloud_cross_bullish: 'Croisement du meilleur nuage haussier',
  structure_bullish: 'Structure haussière',
  structure_break_bullish: 'Cassure structurelle haussière',
  structure_bias_bullish: 'Biais structurel haussier',
  bos_bullish: 'BOS haussier',
  choch_bullish: 'CHoCH haussier',
  fvg_bullish: 'FVG haussier',
  fvg_active_bullish: 'FVG haussier actif',
  impulse_bullish: 'Impulsion haussière',
  fib_impulse_up: 'Impulsion Fibonacci haussière',

  // ── Ichimoku — bearish ──────────────────────────────────────────
  price_below_kumo: 'Prix sous le nuage (kumo)',
  bearish_tk_cross: 'Croisement Tenkan/Kijun baissier',
  bearish_future_kumo: 'Nuage futur baissier (Senkou A < B)',
  kumo_breakout_bearish: 'Cassure baissière du nuage',
  bearish_trend: 'Tendance baissière',
  best_cloud_bearish: 'Meilleur nuage baissier',
  best_cloud_cross_bearish: 'Croisement du meilleur nuage baissier',
  structure_bearish: 'Structure baissière',
  structure_break_bearish: 'Cassure structurelle baissière',
  structure_bias_bearish: 'Biais structurel baissier',
  bos_bearish: 'BOS baissier',
  choch_bearish: 'CHoCH baissier',
  fvg_bearish: 'FVG baissier',
  fvg_active_bearish: 'FVG baissier actif',
  impulse_bearish: 'Impulsion baissière',
  fib_impulse_down: 'Impulsion Fibonacci baissière',

  // ── Ichimoku — neutre / data ────────────────────────────────────
  insufficient_confluence: 'Pas assez de confluence Ichimoku',
  incomplete_ichimoku_confluence: 'Confluence Ichimoku incomplète',
  insufficient_history: 'Historique insuffisant',
  insufficient_bars: 'Pas assez de barres',
  insufficient_candles: 'Pas assez de bougies',
  no_clear_ichimoku_bias: 'Pas de biais Ichimoku clair',
  no_clear_structural_bias: 'Pas de biais structurel clair',
  ichimoku_neutral: 'Ichimoku neutre',
  ichimoku_direction_long: 'Ichimoku haussier',
  ichimoku_direction_short: 'Ichimoku baissier',
  best_cloud_inside: 'Prix dans le meilleur nuage',
  best_cloud_trend: 'Tendance du meilleur nuage',
  direction_unresolved: 'Direction non résolue',

  // ── Invalidation ────────────────────────────────────────────────
  close_back_inside_kumo: 'Clôture de retour dans le nuage',
  close_below_kijun: 'Clôture sous la Kijun',
  close_above_kijun: 'Clôture au-dessus de la Kijun',
  close_beyond_zone: 'Clôture hors de la zone',
  close_confirmation: 'Confirmation de clôture',
  invalidation_hit: 'Invalidation touchée',

  // ── RVOL / participation ────────────────────────────────────────
  volume_anomaly: 'Volume anormalement élevé (anomalie)',
  strong_relative_volume: 'Volume relatif très fort',
  significant_relative_volume: 'Volume relatif significatif',
  volume_accelerating: 'Volume en accélération',
  low_participation: 'Faible participation (volume faible)',
  normal_participation: 'Participation normale',
  high_relative_volume: 'Volume relatif élevé',
  low_relative_volume_participation: 'Participation volume faible — signal peu confirmé',
  rvol_insufficient: 'Volume relatif insuffisant',
  rvol_confirmed: 'Volume relatif confirmé',
  rvol_weak: 'Volume relatif trop faible',
  low_volume_bullish: 'Volume faible sur hausse',

  // ── Structure / MTF / BOS ───────────────────────────────────────
  structure_aligned: 'Structure prix alignée avec la direction',
  structure_opposed: 'Structure prix opposée à la direction',
  structure_opposed_to_long: 'Structure opposée à un long',
  structure_opposed_to_short: 'Structure opposée à un short',
  structure_blocked: 'Structure bloquée',
  bos_confirms_direction: 'BOS confirme la direction',
  bos_invalidates_direction: 'BOS invalide la direction',
  mtf_aligned: 'Multi-timeframe aligné',
  mtf_opposed: 'Multi-timeframe opposé (contre-tendance)',
  mtf_direction: 'Direction multi-timeframe',
  impulse_aligned: 'Impulsion alignée',
  fib_confluence: 'Confluence Fibonacci',
  fib_key_confluence: 'Confluence Fibonacci clé',
  fib_no_confluence: 'Pas de confluence Fibonacci',
  fib_impulse_misaligned: 'Impulsion Fibonacci mal alignée',
  fib_anchor_impulse: 'Ancre Fibonacci sur impulsion',
  fvg_active: 'FVG actif',
  no_retest_yet: 'Pas encore de retest',
  no_swings: 'Pas de swings détectés',
  no_detectors: 'Aucun détecteur actif',
  distance_atr_too_small: 'Distance ATR trop petite',

  // ── Régime ATR / ADX ────────────────────────────────────────────
  regime_dead: 'Régime de volatilité mort',
  regime_extreme: 'Volatilité extrême',
  regime_normal: 'Régime de volatilité normal',
  regime_no_trend: 'Pas de tendance (régime)',
  regime_no_breakout: 'Pas de cassure (régime)',
  regime_unfavorable: 'Régime défavorable',
  regime_fail: 'Échec du filtre de régime',
  regime_bull: 'Régime haussier',
  regime_bear: 'Régime baissier',
  regime_ranging: 'Régime range',
  regime_sideways: 'Régime latéral',
  regime_trending: 'Régime en tendance',
  regime_high_volatility: 'Volatilité élevée',
  regime_low_volatility: 'Volatilité faible',
  regime_normal_volatility: 'Volatilité normale',
  adx_no_trend: 'ADX — pas de tendance',
  adx_developing: 'ADX — tendance en formation',
  adx_trending: 'ADX — tendance en place',
  adx_strong_trend: 'ADX — tendance forte',

  // ── Location — VP / VWAP / AVWAP ────────────────────────────────
  beyond_value_area: 'Prix hors de la value area',
  beyond_va: 'Prix hors de la value area',
  wrong_side_value_area: 'Mauvais côté de la value area',
  wrong_side_va: 'Mauvais côté de la value area',
  inside_value_area: 'Prix dans la value area',
  inside_va: 'Prix dans la value area',
  avwap_aligned: 'Aligné avec le VWAP ancré (AVWAP)',
  avwap_opposed: 'Contre le VWAP ancré (AVWAP)',
  above_vwap: 'Au-dessus du VWAP',
  below_vwap: 'Sous le VWAP',
  congestion_hvn: 'Congestion (HVN — zone de volume dense)',
  thin_liquidity_lvn: 'Liquidité fine (LVN)',
  blocked_zone: 'Zone bloquée',

  // ── Flux / OI / funding ─────────────────────────────────────────
  cvd_buy_pressure: 'Pression acheteuse (CVD)',
  cvd_sell_pressure: 'Pression vendeuse (CVD)',
  cvd_balanced: 'CVD équilibré',
  oi_rising: 'Open interest en hausse',
  oi_falling: 'Open interest en baisse',
  funding_crowded_long: 'Funding encombré côté long',
  funding_crowded_short: 'Funding encombré côté short',

  // ── Context gates ───────────────────────────────────────────────
  context_block: 'Bloqué par le contexte',
  context_blocked: 'Bloqué par le contexte',
  context_cmf: 'Contexte CMF',
  context_obv: 'Contexte OBV',
  context_rsi: 'Contexte RSI',
  context_regime_hard: 'Contexte régime (filtre dur)',
  cmf_negative_block_long: 'CMF négatif — long bloqué',
  cmf_positive_block_short: 'CMF positif — short bloqué',

  // ── Preuves / evidence ──────────────────────────────────────────
  insufficient_historical_evidence: 'Preuves historiques insuffisantes',
  poor_historical_expectancy: 'Espérance historique faible',
  volume_semantics: 'Sémantique volume limitée',
  signal_present_but_not_validated: 'Signal présent mais non validé',
  no_data_or_not_wired: 'Données absentes ou non branchées',

  // ── Refus Risk Kernel / paper ───────────────────────────────────
  short_not_allowed: 'Vente à découvert non autorisée',
  stale_data: 'Données trop anciennes',
  stale_mark: 'Marque de prix périmée',
  stale_open: 'Ouverture périmée',
  no_atr_stop: 'Stop ATR indisponible',
  position_already_open: 'Position déjà ouverte',
  already_open: 'Déjà ouvert',
  already_closed_elsewhere: 'Déjà clôturé ailleurs',
  signal_already_processed: 'Signal déjà traité',
  signal_not_buy: 'Signal non acheteur',
  max_positions: 'Plafond de positions',
  max_open_positions: 'Plafond de positions ouvertes',
  max_exposure: 'Exposition maximale atteinte',
  open_risk_cap: 'Risque ouvert au plafond',
  symbol_exposure_cap: 'Exposition symbole au plafond',
  daily_loss_halt: 'Perte du jour au plafond',
  daily_loss_locked: 'Perte du jour verrouillée',
  kill_switch: "Arrêt d'urgence",
  kill_switch_armed: "Arrêt d'urgence armé",
  insufficient_cash: 'Cash insuffisant',
  insufficient_cash_or_size: 'Cash insuffisant',
  insufficient_cash_or_risk: 'Cash ou risque insuffisant',
  insufficient_liquidity: 'Liquidité insuffisante',
  order_not_executed: 'Ordre non exécuté',
  below_minimum: 'Sous le minimum',
  no_longer_open: 'Plus ouverte',
  no_open_without_mark: 'Pas d’ouverture sans marque',
  no_ledger: 'Pas de ledger',

  // ── Motifs d’ordre / sortie paper ───────────────────────────────
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
  force_flat: 'Aplatissement forcé',
  close_now: 'Clôture immédiate',
  close_capital_position: 'Clôture position capital',

  // ── Énumérations contextuelles (souvent en UPPER) ───────────────
  ABOVE: 'au-dessus',
  BELOW: 'sous',
  INSIDE: 'dans',
  LONG: 'Hausse',
  SHORT: 'Baisse',
  NEUTRAL: 'Neutre',
  BULLISH: 'Haussier',
  BEARISH: 'Baissier',
  NONE: 'Aucun',
  UNKNOWN: 'Inconnu',
  INSUFFICIENT: 'Insuffisant',
  CONFIRMED: 'Confirmé',
  TICK_VOLUME: 'Volume tick',
  SYNTHETIC_VOLUME: 'Volume synthétique',
  REAL_VOLUME: 'Volume réel',
  NO_DATA: 'Pas de données',
  FAIL: 'Échec',
  PASS: 'OK',
  WATCH: 'À surveiller',
  WAIT: 'Attendre',
  BUY: 'Achat',
  SELL: 'Vente',
  STRONG_BUY: 'Achat fort',
  STRONG_SELL: 'Vente forte',
  NO_TRADE: 'Pas de trade',
}

/**
 * Traduit un code moteur en français.
 * Gère les composés `base:valeur` (evidence) et refuse le snake_case brut.
 */
export function labelEngineCode(code: string | null | undefined): string {
  if (code == null) return '—'
  const raw = String(code).trim()
  if (!raw) return '—'

  const mapped = ENGINE_TERM_FR[raw]
  if (mapped) return mapped

  // Composé evidence : `ichimoku_direction_long:BULLISH` ou `rvol_confirmed:2.1`
  const colon = raw.indexOf(':')
  if (colon > 0) {
    const base = raw.slice(0, colon)
    const detail = raw.slice(colon + 1)
    const baseLabel = ENGINE_TERM_FR[base] ?? humanizeSnake(base)
    const detailLabel = ENGINE_TERM_FR[detail] ?? formatDetail(detail)
    return detailLabel ? `${baseLabel} (${detailLabel})` : baseLabel
  }

  const upper = ENGINE_TERM_FR[raw.toUpperCase()]
  if (upper) return upper

  const lower = ENGINE_TERM_FR[raw.toLowerCase()]
  if (lower) return lower

  return humanizeSnake(raw)
}

export function labelEngineCodes(codes: readonly string[], max?: number): string[] {
  const slice = max != null ? codes.slice(0, max) : codes
  return slice.map(labelEngineCode)
}

/** Sortie journal / trades — libellé court si connu, sinon labelEngineCode. */
export function labelExitReason(reason: string | null | undefined): string {
  if (!reason?.trim()) return '—'
  const short: Record<string, string> = {
    stop_hit: 'Stop',
    stop_loss: 'Stop',
    stop: 'Stop',
    take_profit_hit: 'Objectif atteint',
    take_profit: 'Objectif atteint',
    pipeline_flipped: 'Changement de direction',
    pipeline_downgraded: 'Signal affaibli',
    manual_close: 'Fermeture manuelle',
    horizon_end: "Fin d'horizon",
    time_stop: 'Sortie temps',
    window_end: 'Fin de fenêtre',
    force_flat: 'Aplatissement forcé',
    direction_flipped: 'Sens inversé',
    exposure_off: 'Exposition coupée',
  }
  return short[reason] ?? labelEngineCode(reason)
}

function formatDetail(detail: string): string {
  if (!detail) return ''
  if (ENGINE_TERM_FR[detail]) return ENGINE_TERM_FR[detail]
  if (ENGINE_TERM_FR[detail.toUpperCase()]) return ENGINE_TERM_FR[detail.toUpperCase()]
  // Nombre pur (ex. rvol 2.14)
  if (/^-?\d+(\.\d+)?$/.test(detail)) {
    const n = Number(detail)
    return Number.isFinite(n) ? n.toFixed(2) : detail
  }
  if (detail.includes('_')) return humanizeSnake(detail)
  return detail
}

/** Humanise un snake_case inconnu — jamais d’underscores affichés. */
function humanizeSnake(code: string): string {
  const parts = code
    .replace(/([a-z])([A-Z])/g, '$1_$2')
    .toLowerCase()
    .split(/[_\s-]+/)
    .filter(Boolean)

  if (parts.length === 0) return code

  const words = parts.map((p) => TOKEN_FR[p] ?? p)
  const phrase = words.join(' ')
  return phrase.charAt(0).toUpperCase() + phrase.slice(1)
}

/** Alias historiques — même API que decisionLabels / paperLabels. */
export const labelReason = labelEngineCode

export function labelRiskRefusal(reason: string | undefined | null): string {
  if (!reason) return 'Refusé'
  if (reason in ENGINE_TERM_FR) return ENGINE_TERM_FR[reason]
  const lower = ENGINE_TERM_FR[reason.toLowerCase()]
  if (lower) return lower
  if (reason.includes(':')) return labelEngineCode(reason)
  return 'Refusé par le risque'
}

export function labelPaperOrderReason(reason: string | null | undefined): string {
  if (!reason) return ''
  if (reason in ENGINE_TERM_FR) return ENGINE_TERM_FR[reason]
  return ''
}
