/**
 * Badge discret « Signal non validé » (UI-VP-BADGE).
 * Affichage seulement — aucun impact moteur / paper / gates.
 * Pas de lien externe (tooltip = verdict VP3) — createElement pour tests SSR.
 */

import { createElement } from 'react'
import { VP_VALIDATION_BADGE_LABEL, vpValidationTitle } from '../lib/vpValidationCopy'

interface Props {
  /** Variante densifiée (cellule matrice). */
  compact?: boolean
}

export function VpValidationBadge({ compact = false }: Props) {
  return createElement(
    'span',
    {
      className: `vp-validation-badge${compact ? ' is-compact' : ''}`,
      title: vpValidationTitle(),
      role: 'status',
    },
    VP_VALIDATION_BADGE_LABEL,
  )
}
