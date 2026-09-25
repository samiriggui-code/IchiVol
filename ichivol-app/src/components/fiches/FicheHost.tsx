/**
 * Hôte shell des fiches deep-link (`?fiche=`).
 * Back / fermeture → retire le param. Phase B stubs pour position/run/agent.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ACTION_NOTICE_EVENT,
  actionNoticeStyle,
  type ActionNotice,
} from '../../lib/actionFeedback'
import { useFicheNav } from '../../lib/useFicheNav'
import { FicheDecision } from './FicheDecision'
import './ficheDialog.css'

function PhaseBStub({
  title,
  detail,
  onClose,
}: {
  title: string
  detail: string
  onClose: () => void
}) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (!el.open) el.showModal()
    const onDialogClose = () => onClose()
    el.addEventListener('close', onDialogClose)
    return () => el.removeEventListener('close', onDialogClose)
  }, [onClose])

  return (
    <dialog
      ref={ref}
      className="fiche-dialog"
      onCancel={(e) => {
        e.preventDefault()
        ref.current?.close()
      }}
    >
      <div className="dialog-body">
        <div className="dialog-head">
          <h2>{title}</h2>
          <button type="button" onClick={() => ref.current?.close()} aria-label="Fermer">
            ×
          </button>
        </div>
        <div className="notice blue">{detail}</div>
        <div className="dialog-actions">
          <button type="button" className="primary" onClick={() => ref.current?.close()}>
            Fermer
          </button>
        </div>
      </div>
    </dialog>
  )
}

export function FicheHost() {
  const { fiche, tab, asOf, closeFiche } = useFicheNav()
  const [notice, setNotice] = useState<ActionNotice | null>(null)

  useEffect(() => {
    const onNotice = (e: Event) => {
      const ce = e as CustomEvent<ActionNotice>
      if (ce.detail) setNotice(ce.detail)
    }
    window.addEventListener(ACTION_NOTICE_EVENT, onNotice)
    return () => window.removeEventListener(ACTION_NOTICE_EVENT, onNotice)
  }, [])

  useEffect(() => {
    if (!notice) return
    const t = window.setTimeout(() => setNotice(null), 6000)
    return () => window.clearTimeout(t)
  }, [notice])

  const handleClose = useCallback(() => {
    closeFiche({ replace: true })
  }, [closeFiche])

  return (
    <>
      {notice && (
        <div
          className="notice"
          role="status"
          style={{
            position: 'fixed',
            bottom: 24,
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 80,
            maxWidth: 'min(520px, 92vw)',
            ...actionNoticeStyle(notice.ok),
          }}
        >
          {notice.text}
        </div>
      )}

      {fiche?.kind === 'decision' && (
        <FicheDecision
          key={`${fiche.symbol}:${fiche.timeframe}:${tab}:${asOf ?? ''}`}
          symbol={fiche.symbol}
          timeframe={fiche.timeframe}
          initialTab={tab}
          onClose={handleClose}
          asOfNote={
            asOf === 'journal'
              ? 'Lecture courante du moteur — pas de replay as-of à la date d’enregistrement (API détail live uniquement).'
              : null
          }
        />
      )}

      {fiche?.kind === 'position' && (
        <PhaseBStub
          title="Fiche position"
          detail={`Phase B — position ${fiche.id}. Retour navigateur pour fermer.`}
          onClose={handleClose}
        />
      )}
      {fiche?.kind === 'run' && (
        <PhaseBStub
          title="Fiche run"
          detail={`Phase B — run ${fiche.id}. Retour navigateur pour fermer.`}
          onClose={handleClose}
        />
      )}
      {fiche?.kind === 'agent' && (
        <PhaseBStub
          title="Fiche agent"
          detail={`Phase B — agent ${fiche.id}. Retour navigateur pour fermer.`}
          onClose={handleClose}
        />
      )}
    </>
  )
}
