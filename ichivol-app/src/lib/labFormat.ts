/** Strategy Lab : libellés et formats lisibles pour les résultats du moteur (fractions → %). */

/** Fraction → « 12,3 % » ; null → « — ». `signed` ajoute le + devant les valeurs positives. */
export function pct(v: number | null | undefined, digits = 1, signed = false): string {
  if (v == null || !Number.isFinite(v)) return '—'
  const s = (v * 100).toFixed(digits).replace('.', ',')
  return `${signed && v > 0 ? '+' : ''}${s} %`
}

export function num(v: number | null | undefined, digits = 2): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return v.toFixed(digits).replace('.', ',')
}

/** Variantes du backtest quotidien (engine/app/backtest/experiments.py). */
export const VARIANT_LABELS: Record<string, string> = {
  ICHIMOKU_ONLY: 'Ichimoku seul',
  ICHIMOKU_RVOL: 'Ichimoku + volume (chaque barre)',
  ICHIMOKU_RVOL_ENTRY_GATE: 'Ichimoku + volume (à l’entrée)',
  PIPELINE: 'Pipeline complet',
  PIPELINE_WYCKOFF_FILTER: 'Pipeline + filtre Wyckoff',
}

/** Étapes de l'échelle d'ablation (engine/app/strategy_lab/ablation.py, DEFAULT_ABLATION_LAYERS). */
const LAYER_LABELS: Record<string, string> = {
  A_ICHIMOKU: 'A · Ichimoku (prix au-dessus du nuage, croisement récent)',
  B_RVOL: 'B · + Volume relatif ≥ 1,5',
  C_BOS: 'C · + Cassure de structure haussière',
  D_ATR: 'D · + Volatilité en expansion',
  E_CMF: 'E · + Flux acheteur (CMF ≥ 0)',
}

export function layerLabel(raw: string): string {
  const key = raw.split('+').pop()?.trim() ?? raw
  return LAYER_LABELS[raw] ?? LAYER_LABELS[key] ?? raw.replace(/_/g, ' ')
}

export const REGIME_LABELS: Record<string, string> = {
  GLOBAL: 'Tous les signaux',
  TRENDING: 'Marché en tendance',
  RANGING: 'Marché sans tendance',
  HIGH_VOLATILITY: 'Forte volatilité',
  NORMAL_VOLATILITY: 'Volatilité normale',
  LOW_VOLATILITY: 'Faible volatilité',
  BULL: 'Haussier',
  BEAR: 'Baissier',
  SIDEWAYS: 'Latéral',
}

export function regimeLabel(raw: string): string {
  return REGIME_LABELS[raw] ?? raw.replace(/_/g, ' ').toLowerCase()
}

export type Verdict = { text: string; tone: 'green' | 'red' | 'amber' | 'gray' }

/** Une couche d'ablation se garde si elle améliore l'espérance ou le profit factor (règle du moteur). */
export function ablationVerdict(
  improvesExpectancy: boolean | null | undefined,
  improvesPf: boolean | null | undefined,
): Verdict {
  if (improvesExpectancy == null && improvesPf == null) return { text: 'PAS ASSEZ DE TRADES', tone: 'gray' }
  if (improvesExpectancy && improvesPf) return { text: 'AMÉLIORE', tone: 'green' }
  if (improvesExpectancy || improvesPf) return { text: 'MITIGÉ', tone: 'amber' }
  return { text: 'DÉGRADE', tone: 'red' }
}
