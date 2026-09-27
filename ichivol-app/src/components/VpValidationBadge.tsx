/**
 * Badge discret « Signal non validé » (UI-VP-BADGE).
 * Affichage seulement — aucun impact moteur / paper / gates.
 * createElement : rendu stable sous Vite (react-jsx) et sous `tsx --test`.
 */

import { createElement, type MouseEvent } from 'react'
import {
  VP_VALIDATION_BADGE_LABEL,
  VP_VALIDATION_REPORT_HREF,
  vpValidationTitle,
} from '../lib/vpValidationCopy'

interface Props {
  /** Variante densifiée (cellule matrice). */
  compact?: boolean
}

export function VpValidationBadge({ compact = false }: Props) {
  return createElement(
    'a',
    {
      className: `vp-validation-badge${compact ? ' is-compact' : ''}`,
      href: VP_VALIDATION_REPORT_HREF,
      target: '_blank',
      rel: 'noopener noreferrer',
      title: vpValidationTitle(),
      onClick: (e: MouseEvent<HTMLAnchorElement>) => e.stopPropagation(),
    },
    VP_VALIDATION_BADGE_LABEL,
  )
}
