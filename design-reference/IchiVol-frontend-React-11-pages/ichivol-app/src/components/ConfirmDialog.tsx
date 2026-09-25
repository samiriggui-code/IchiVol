import { useEffect, useRef } from 'react'

/**
 * Dialogue de confirmation générique (suppression, retrait, etc.).
 * Reset du verrou quand `confirming` repasse à false.
 */
export function ConfirmDialog({
  title,
  body,
  confirmLabel = 'Confirmer',
  cancelLabel = 'Annuler',
  confirming,
  danger,
  error,
  onConfirm,
  onCancel,
}: {
  title: string
  body: string
  confirmLabel?: string
  cancelLabel?: string
  confirming?: boolean
  danger?: boolean
  error?: string | null
  onConfirm: () => void
  onCancel: () => void
}) {
  const clickLock = useRef(false)

  useEffect(() => {
    if (!confirming) clickLock.current = false
  }, [confirming])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !confirming) onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancel, confirming])

  function handleConfirm() {
    if (confirming || clickLock.current) return
    clickLock.current = true
    onConfirm()
  }

  return (
    <div
      className="trade-sheet-backdrop paper-confirm-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={(e) => {
        if (e.target === e.currentTarget && !confirming) onCancel()
      }}
    >
      <aside className="panel trade-sheet paper-confirm-sheet" style={{ maxWidth: '22rem' }}>
        <header className="panel-head trade-sheet-head">
          <div>
            <h2>{title}</h2>
          </div>
          <button type="button" className="ghost" onClick={onCancel} disabled={confirming}>
            {cancelLabel}
          </button>
        </header>
        <div className="trade-sheet-scroll">
          {error && (
            <div className="banner error" role="alert">
              {error}
            </div>
          )}
          <p className="muted" style={{ margin: '0 0 0.75rem', lineHeight: 1.4 }}>
            {body}
          </p>
          <div className="paper-confirm-actions">
            <button
              type="button"
              className="ghost"
              disabled={confirming}
              onClick={handleConfirm}
              style={danger ? { color: 'var(--bear)' } : undefined}
            >
              {confirming ? '…' : confirmLabel}
            </button>
            <button type="button" className="ghost" disabled={confirming} onClick={onCancel}>
              {cancelLabel}
            </button>
          </div>
        </div>
      </aside>
    </div>
  )
}
