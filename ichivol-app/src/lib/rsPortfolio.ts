/** RS-D1 paper (docs/RS-09-RS-D1-PAPER-DESIGN.md) : portefeuille séparé, piloté par son runner seul. */

export const BASELINE_PORTFOLIO_CODE = 'ICHIVOL_BASELINE_V1'
export const RS_D1_CODE = 'RS_D1_PAPER_V1'
export const RS_D1_LABEL = 'RS-D1 — validé 2025, holdout 2026 non ouvert'

export function isRsPortfolio(code: string | null | undefined): boolean {
  return code === RS_D1_CODE
}

/** Code du portefeuille demandé par l'URL (`?pf=`) ; tout autre valeur retombe sur le baseline. */
export function portfolioFromParam(param: string | null | undefined): string {
  return param === RS_D1_CODE ? RS_D1_CODE : BASELINE_PORTFOLIO_CODE
}

/** Aucune action manuelle (achat, fermeture) sur un portefeuille RS. */
export function manualActionsAllowed(code: string | null | undefined): boolean {
  return !isRsPortfolio(code)
}
