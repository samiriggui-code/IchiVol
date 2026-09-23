import { useEffect, useRef, useState } from 'react'
import type { UserTradePointType } from '../lib/chartObjects'

export type MarkTradeStep = UserTradePointType

const STEPS: MarkTradeStep[] = ['entry', 'stop', 'target']

const STEP_LABEL: Record<MarkTradeStep, string> = {
  entry: 'Entrée',
  stop: 'Stop',
  target: 'Cible',
}

/**
 * Bottom sheet for T2c « Marquer un trade » — pick ENTRY → STOP → TARGET on the chart.
 * Mobile-first; Escape / Annuler exits without deleting already-saved points.
 */
export function MarkTradeSheet({
  symbolLabel,
  step,
  side,
  saving,
  error,
  placed,
  onSideChange,
  onCancel,
}: {
  symbolLabel: string
  step: MarkTradeStep
  side: 'LONG' | 'SHORT'
  saving?: boolean
  error?: string | null
  placed: Partial<Record<MarkTradeStep, { price: number; time: number }>>
  onSideChange: (side: 'LONG' | 'SHORT') => void
  onCancel: () => void
}) {
  const [hintPulse, setHintPulse] = useState(true)
  const stepRef = useRef(step)

  useEffect(() => {
    stepRef.current = step
    setHintPulse(true)
    const t = window.setTimeout(() => setHintPulse(false), 900)
    return () => window.clearTimeout(t)
  }, [step])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !saving) onCancel()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancel, saving])

  const stepIndex = STEPS.indexOf(step)

  return (
    <div className="mark-trade-backdrop" role="presentation">
      <aside
        className="mark-trade-sheet decision-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="mark-trade-title"
      >
        <header className="decision-sheet-head mark-trade-head">
          <div>
            <p className="muted mark-trade-eyebrow">Marquer un trade</p>
            <h2 id="mark-trade-title">{symbolLabel}</h2>
          </div>
          <button
            type="button"
            className="ghost decision-sheet-close"
            onClick={onCancel}
            disabled={saving}
          >
            Fermer
          </button>
        </header>

        <div className="decision-sheet-scroll mark-trade-body">
          <div className="mark-trade-side" role="group" aria-label="Sens">
            <button
              type="button"
              className={side === 'LONG' ? 'is-on' : undefined}
              onClick={() => onSideChange('LONG')}
              disabled={saving || Boolean(placed.entry)}
            >
              LONG
            </button>
            <button
              type="button"
              className={side === 'SHORT' ? 'is-on' : undefined}
              onClick={() => onSideChange('SHORT')}
              disabled={saving || Boolean(placed.entry)}
            >
              SHORT
            </button>
          </div>

          <ol className="mark-trade-steps" aria-label="Étapes">
            {STEPS.map((s, i) => {
              const done = Boolean(placed[s])
              const current = s === step
              return (
                <li
                  key={s}
                  className={
                    done ? 'is-done' : current ? 'is-current' : 'is-todo'
                  }
                >
                  <span className="mark-trade-step-idx">{i + 1}</span>
                  <span className="mark-trade-step-label">{STEP_LABEL[s]}</span>
                  {done ? (
                    <span className="mark-trade-step-val">
                      {placed[s]!.price.toLocaleString(undefined, {
                        maximumFractionDigits: 6,
                      })}
                    </span>
                  ) : null}
                </li>
              )
            })}
          </ol>

          <p
            className={`mark-trade-hint${hintPulse ? ' is-pulse' : ''}`}
            aria-live="polite"
          >
            {saving
              ? 'Enregistrement…'
              : stepIndex < STEPS.length
                ? `Touche le graphique pour poser le ${STEP_LABEL[step].toLowerCase()}.`
                : 'Setup enregistré.'}
          </p>

          {error ? (
            <div className="banner error" role="alert">
              {error}
            </div>
          ) : null}
        </div>
      </aside>
    </div>
  )
}
