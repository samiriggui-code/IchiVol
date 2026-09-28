/**
 * Host de sheet en <dialog showModal> + portal body.
 * Passe au-dessus d’une fiche Opportunités déjà ouverte en showModal (top layer).
 * Un simple z-index ne suffit pas contre le top layer natif.
 */

import { useEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

export function ModalSheetHost({
  ariaLabel,
  confirming,
  onCancel,
  children,
}: {
  ariaLabel: string
  confirming?: boolean
  onCancel: () => void
  children: ReactNode
}) {
  const hostRef = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const el = hostRef.current
    if (!el) return
    if (!el.open) el.showModal()
    return () => {
      if (el.open) el.close()
    }
  }, [])

  return createPortal(
    <dialog
      ref={hostRef}
      className="trade-sheet-dialog paper-confirm-dialog"
      aria-label={ariaLabel}
      onCancel={(e) => {
        e.preventDefault()
        if (!confirming) onCancel()
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !confirming) onCancel()
      }}
    >
      {children}
    </dialog>,
    document.body,
  )
}
