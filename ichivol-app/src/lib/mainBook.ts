/**
 * Le portefeuille paper unique vu par l'écran : sa ligne `/paper/portfolios` (verrous) et sa vue d'ensemble.
 * Les chiffres sont ceux du moteur ; rien n'est recalculé ici.
 */

import { getPaperOverview, listPaperPortfolios, type PaperOverview, type PaperPortfolioRow } from './paper'
import { MAIN_PORTFOLIO_CODE, MAIN_PORTFOLIO_LABEL } from './mainPortfolio'

export type Book = {
  code: string
  label: string
  row: PaperPortfolioRow
  overview: PaperOverview
}

export async function loadMainBook(): Promise<Book> {
  const [rows, overview] = await Promise.all([
    listPaperPortfolios().catch(() => [] as PaperPortfolioRow[]),
    getPaperOverview(MAIN_PORTFOLIO_CODE),
  ])
  const row =
    rows.find((r) => r.code === MAIN_PORTFOLIO_CODE) ??
    ({ code: MAIN_PORTFOLIO_CODE, label: MAIN_PORTFOLIO_LABEL } as PaperPortfolioRow)
  return { code: MAIN_PORTFOLIO_CODE, label: MAIN_PORTFOLIO_LABEL, row, overview }
}
