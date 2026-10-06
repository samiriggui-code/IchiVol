/** Libellés courts des portefeuilles paper, pour l'affichage. */

import { BASELINE_PORTFOLIO_CODE, RS_D1_CODE, SESSIONS_CODE } from './rsPortfolio'

const LABELS: Record<string, string> = {
  [BASELINE_PORTFOLIO_CODE]: 'IchiVol',
  [SESSIONS_CODE]: 'Sessions',
  [RS_D1_CODE]: 'RS-D1',
}

export function portfolioLabel(code: string | null | undefined): string {
  if (!code) return '—'
  return LABELS[code] ?? code
}

/** Remplace dans un texte libre les codes de portefeuille bruts par leur libellé. */
export function replacePortfolioCodes(text: string): string {
  return text.replace(/ICHIVOL_BASELINE_V1|ICHIVOL_SESSIONS_V1|RS_D1_PAPER_V1/g, (c) => LABELS[c] ?? c)
}
