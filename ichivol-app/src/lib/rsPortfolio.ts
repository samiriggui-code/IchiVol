/** RS-D1 paper (docs/RS-09-RS-D1-PAPER-DESIGN.md) : portefeuille séparé, piloté par son runner seul. */

export const BASELINE_PORTFOLIO_CODE = 'ICHIVOL_BASELINE_V1'
export const RS_D1_CODE = 'RS_D1_PAPER_V1'
export const RS_D1_LABEL = 'RS-D1 — validé 2025, holdout 2026 non ouvert'
/** Règles baseline, décisions seulement aux ouvertures / clôtures Tokyo, Londres, New York. */
export const SESSIONS_CODE = 'ICHIVOL_SESSIONS_V1'
export const SESSIONS_LABEL = 'Sessions — décisions aux ouvertures et clôtures de Tokyo, Londres et New York'

/** YM, MGC et BTC (spot / perpétuel / CME) sur un compte à part : src/lib/futuresCrypto.ts. */
export const FUTURES_CRYPTO_CODE = 'FUTURES_CRYPTO_V1'

const SELECTABLE = new Set([RS_D1_CODE, SESSIONS_CODE, FUTURES_CRYPTO_CODE])

/** Portefeuilles qui acceptent un achat manuel (RS-D1 reste piloté par sa seule règle, RS-09 §7). */
export const MANUAL_PORTFOLIOS: ReadonlyArray<{ code: string; label: string }> = [
  { code: BASELINE_PORTFOLIO_CODE, label: 'IchiVol' },
  { code: SESSIONS_CODE, label: 'Sessions' },
]

export function isRsPortfolio(code: string | null | undefined): boolean {
  return code === RS_D1_CODE
}

/** Code du portefeuille demandé par l'URL (`?pf=`) ; tout autre valeur retombe sur le baseline. */
export function portfolioFromParam(param: string | null | undefined): string {
  return param && SELECTABLE.has(param) ? param : BASELINE_PORTFOLIO_CODE
}

/** Actions manuelles (achat, fermeture) partout sauf sur RS-D1. Futures & Crypto : fermeture d'une position
 * depuis sa page ; ses achats restent limités à ses trois marchés côté moteur. */
export function manualActionsAllowed(code: string | null | undefined): boolean {
  return MANUAL_PORTFOLIOS.some((p) => p.code === code) || code === FUTURES_CRYPTO_CODE
}
