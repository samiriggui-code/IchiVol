/**
 * Fiche d'un mode d'Ève — même chrome que Opportunités / FicheDecision (`fiche-dialog`).
 * ids : eve:analyst | eve:challenger | eve:guardian | eve:shadow (les autres renvoient vers la page Ève).
 */

import { useEffect, useRef, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { eveModeById, JEV_PRIMITIVES, type EveMode } from '../../lib/eveModes'
import { EveShadowPanel } from '../eve/EveShadowPanel'
import './ficheDialog.css'

type BadgeTone = 'green' | 'amber' | 'red' | 'gray' | ''

function badge(text: string, tone: BadgeTone = 'gray'): ReactNode {
  return <span className={`tag ${tone}`.trim()}>{text}</span>
}

function parseAgentId(id: string): { mode: EveMode | null; title: string } {
  const raw = id.trim().toLowerCase().replace(/^eve[:-]/, '')
  const mode = eveModeById(raw) ?? null
  return { mode, title: mode ? `Ève ${mode.name}` : 'Ève' }
}

export function FicheAgent({ agentId, onClose }: { agentId: string; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null)
  const { mode, title } = parseAgentId(agentId)

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
      aria-label={`Fiche ${title}`}
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

        {mode ? (
          <>
            {badge('MODE', mode.id === 'guardian' ? 'amber' : 'green')}
            <p>{mode.blurb}</p>
            <div className="statline">
              <span>Quand il n’est pas d’accord</span>
              <b>{mode.effect}</b>
            </div>
            <div className="statline">
              <span>Questions posées à JEV</span>
              <b>
                <code>{JEV_PRIMITIVES}</code>
              </b>
            </div>
            <div className="statline">
              <span>Ce qu’il lit</span>
              <b>les calculs du moteur, jamais le marché en direct</b>
            </div>
            <div className="statline">
              <span>Ce qu’il exécute</span>
              <b>rien : la synthèse d’Ève décide, le Risk Kernel autorise, le tout en paper</b>
            </div>
            {mode.id === 'shadow' ? (
              <div className="fiche-tab-panel">
                <EveShadowPanel />
              </div>
            ) : null}
            <div className="dialog-actions">
              <Link className="link" to="/app/agents" onClick={() => ref.current?.close()}>
                Page Ève →
              </Link>
              <button type="button" className="primary" onClick={() => ref.current?.close()}>
                Fermer
              </button>
            </div>
          </>
        ) : (
          <>
            <p>Cette fiche n’existe plus : tout ce qui concerne Ève est sur sa page.</p>
            <div className="dialog-actions">
              <Link className="link" to="/app/agents" onClick={() => ref.current?.close()}>
                Page Ève →
              </Link>
              <button type="button" className="primary" onClick={() => ref.current?.close()}>
                Fermer
              </button>
            </div>
          </>
        )}
      </div>
    </dialog>
  )
}
