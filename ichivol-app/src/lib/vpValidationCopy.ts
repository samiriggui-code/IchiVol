/**
 * Copy unique — badge « Signal non validé » (UI-VP-BADGE).
 * Mettre à jour ici quand un futur programme VP changera le verdict mesuré.
 */

export const VP_VALIDATION_BADGE_LABEL = 'Signal non validé'

export const VP_VALIDATION_TOOLTIP =
  'Programme de validation VP3 : aucun edge mesuré (0/48 cas, 2021–2024, après coûts).'

/** Chemin repo (affichage / docs). */
export const VP_VALIDATION_REPORT_PATH = 'docs/VP3-REPORT-FINAL.md'

/** Lien ouvrable depuis l’app (blob main). */
export const VP_VALIDATION_REPORT_HREF =
  'https://github.com/samiriggui-code/IchiVol/blob/main/docs/VP3-REPORT-FINAL.md'

/** Title atome : tooltip + chemin rapport. */
export function vpValidationTitle(): string {
  return `${VP_VALIDATION_TOOLTIP} → ${VP_VALIDATION_REPORT_PATH}`
}

/**
 * Afficher le badge seulement sur un verdict d’action ACHAT/VENTE
 * (portes BUY/SELL ou combiner STRONG_* / BUY / SELL).
 */
export function isActionableBuySell(code: string | null | undefined): boolean {
  const u = (code ?? '').trim().toUpperCase()
  return u === 'BUY' || u === 'SELL' || u === 'STRONG_BUY' || u === 'STRONG_SELL'
}
