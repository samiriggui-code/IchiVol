/**
 * Le portefeuille paper unique d'IchiVol (décision du propriétaire, 27/10/2026).
 *
 * Un seul compte, `ICHIVOL_MAIN_V1`, 50 000 € de capital virtuel : le scan automatique, Ève (avec JEV) et les
 * ordres manuels décident tous pour lui ; le moteur arbitre (un seul lot par symbole). Les huit anciens comptes
 * (baseline, 4h, élargi, shorts, sessions, combiné, RS-D1, Futures & Crypto) ne sont plus synchronisés ni
 * affichés. Le front n'en sélectionne jamais un autre : les règles et les chiffres viennent du moteur.
 */

export const MAIN_PORTFOLIO_CODE = 'ICHIVOL_MAIN_V1'
export const MAIN_PORTFOLIO_LABEL = 'IchiVol'
export const MAIN_PORTFOLIO_SUMMARY =
  'Portefeuille paper unique d’IchiVol (50 000 € virtuels) : le scan automatique, Ève et vos ordres manuels décident tous pour ce seul compte, un seul lot par symbole.'

/** Anciens comptes paper retirés le 27/10/2026 : jamais sélectionnables ni affichés comme actifs. */
export const RETIRED_PORTFOLIO_CODES: ReadonlyArray<string> = [
  'ICHIVOL_BASELINE_V1',
  'ICHIVOL_4H_V1',
  'ICHIVOL_WIDE_V1',
  'ICHIVOL_SHORTS_V1',
  'ICHIVOL_SESSIONS_V1',
  'ICHIVOL_COMBO_V1',
  'RS_D1_PAPER_V1',
  'FUTURES_CRYPTO_V1',
]

export function isRetiredPortfolio(code: string | null | undefined): boolean {
  return code != null && RETIRED_PORTFOLIO_CODES.includes(code)
}

/** Code de portefeuille demandé par l'URL (`?pf=`) : toujours le portefeuille unique, un ancien code est ignoré. */
export function portfolioFromParam(_param?: string | null): string {
  return MAIN_PORTFOLIO_CODE
}

/** Nom court d'un portefeuille pour l'écran. Un ancien code (historique d'Ève, journal) est marqué « retiré ». */
export function portfolioLabel(code: string | null | undefined, apiLabel?: string | null): string {
  if (!code || code === MAIN_PORTFOLIO_CODE) return MAIN_PORTFOLIO_LABEL
  if (isRetiredPortfolio(code)) return `${apiLabel || code} (compte retiré)`
  return apiLabel || code
}
