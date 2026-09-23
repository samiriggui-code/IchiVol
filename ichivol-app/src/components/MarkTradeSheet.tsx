import { useEffect, useMemo, useState } from 'react'
import type { UserTradePointType } from '../lib/chartObjects'

export type MarkTradeStep = UserTradePointType | 'review'

export type MarkTradePoint = { time: number; price: number }

const STEPS: UserTradePointType[] = ['entry', 'stop', 'target']

const STEP_LABEL: Record<UserTradePointType, string> = {
  entry: 'Entrée',
  stop: 'Stop',
  target: 'Cible',
}

export function deduceMarkDirection(
  entry: MarkTradePoint | undefined,
  stop: MarkTradePoint | undefined,
): 'long' | 'short' | null {
  if (!entry || !stop) return null
  if (stop.price < entry.price) return 'long'
  if (stop.price > entry.price) return 'short'
  return null
}

export function isMarkSetupGeometryValid(
  entry: MarkTradePoint | undefined,
  stop: MarkTradePoint | undefined,
  target: MarkTradePoint | undefined,
): boolean {
  if (!entry || !stop || !target) return false
  const dir = deduceMarkDirection(entry, stop)
  if (dir === 'long') return stop.price < entry.price && entry.price < target.price
  if (dir === 'short') return target.price < entry.price && entry.price < stop.price
  return false
}

function fmtPx(n: number): string {
  return n.toLocaleString(undefined, { maximumFractionDigits: 6 })
}

function fmtPct(n: number): string {
  return `${(n * 100).toFixed(2)} %`
}

/**
 * Bottom sheet for T2c « Marquer un trade ».
 * Taps stay in memory until Valider (atomic /setup) or Annuler (écrit rien).
 */
export function MarkTradeSheet({
  symbolLabel,
  step,
  saving,
  error,
  placed,
  onCancel,
  onValidate,
}: {
  symbolLabel: string
  step: MarkTradeStep
  saving?: boolean
  error?: string | null
  placed: Partial<Record<UserTradePointType, MarkTradePoint>>
  onCancel: () => void
  onValidate: () => void
}) {
  const [hintPulse, setHintPulse] = useState(true)

  useEffect(() => {
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

  const direction = useMemo(
    () => deduceMarkDirection(placed.entry, placed.stop),
    [placed.entry, placed.stop],
  )

  const canValidate = useMemo(
    () => isMarkSetupGeometryValid(placed.entry, placed.stop, placed.target),
    [placed.entry, placed.stop, placed.target],
  )

  const metrics = useMemo(() => {
    const entry = placed.entry
    const stop = placed.stop
    const target = placed.target
    if (!entry || !stop) return null
    const stopDist = Math.abs(entry.price - stop.price)
    const stopPct = entry.price !== 0 ? stopDist / Math.abs(entry.price) : 0
    if (!target) {
      return { stopDist, stopPct, targetDist: null as number | null, targetPct: null as number | null, r: null as number | null }
    }
    const targetDist = Math.abs(target.price - entry.price)
    const targetPct = entry.price !== 0 ? targetDist / Math.abs(entry.price) : 0
    const r = stopDist > 0 ? Math.round((targetDist / stopDist) * 100) / 100 : null
    return { stopDist, stopPct, targetDist, targetPct, r }
  }, [placed.entry, placed.stop, placed.target])

  const picking = step !== 'review'
  const hint = saving
    ? 'Enregistrement…'
    : step === 'review'
      ? canValidate
        ? 'Vérifie le récap, puis Valider (rien n’est écrit tant que tu n’as pas validé).'
        : 'Setup incohérent — corrige en annulant et en recommençant.'
      : `Touche le graphique pour poser le ${STEP_LABEL[step].toLowerCase()}.`

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
            Annuler
          </button>
        </header>

        <div className="decision-sheet-scroll mark-trade-body">
          {direction ? (
            <p className="mark-trade-direction" aria-live="polite">
              Sens déduit : <strong>{direction.toUpperCase()}</strong>
            </p>
          ) : placed.entry && placed.stop ? (
            <p className="mark-trade-direction is-bad" role="alert">
              Stop = entrée — sens indéterminé
            </p>
          ) : (
            <p className="muted mark-trade-direction">
              Sens déduit après le stop (stop &lt; entrée → LONG)
            </p>
          )}

          <ol className="mark-trade-steps" aria-label="Étapes">
            {STEPS.map((s, i) => {
              const done = Boolean(placed[s])
              const current = picking && s === step
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
                    <span className="mark-trade-step-val">{fmtPx(placed[s]!.price)}</span>
                  ) : null}
                </li>
              )
            })}
          </ol>

          {metrics ? (
            <dl className="mark-trade-metrics">
              <div>
                <dt>Distance stop</dt>
                <dd>
                  {fmtPx(metrics.stopDist)} · {fmtPct(metrics.stopPct)}
                </dd>
              </div>
              {metrics.targetDist != null && metrics.r != null ? (
                <>
                  <div>
                    <dt>Distance cible</dt>
                    <dd>
                      {fmtPx(metrics.targetDist)} · {fmtPct(metrics.targetPct ?? 0)}
                    </dd>
                  </div>
                  <div>
                    <dt>R</dt>
                    <dd>{metrics.r.toFixed(2)}</dd>
                  </div>
                </>
              ) : null}
            </dl>
          ) : null}

          <p
            className={`mark-trade-hint${hintPulse ? ' is-pulse' : ''}`}
            aria-live="polite"
          >
            {hint}
          </p>

          {error ? (
            <div className="banner error" role="alert">
              {error}
            </div>
          ) : null}

          {step === 'review' ? (
            <div className="mark-trade-actions">
              <button type="button" className="ghost" onClick={onCancel} disabled={saving}>
                Annuler
              </button>
              <button
                type="button"
                className="mark-trade-validate"
                onClick={onValidate}
                disabled={saving || !canValidate}
              >
                {saving ? 'Validation…' : 'Valider'}
              </button>
            </div>
          ) : null}
        </div>
      </aside>
    </div>
  )
}
