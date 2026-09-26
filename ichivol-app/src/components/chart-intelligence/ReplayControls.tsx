/**
 * ReplayControls — PLAY walk-forward (CI-R1a).
 * Si le pack `/replay` échoue : bouton grisé « Replay en cours de correction ».
 */

import { fmtTime } from '../../lib/chartIntelligence'
import type { ChartIntelligenceState, ReplaySpeed } from '../../lib/useChartIntelligence'

interface Props {
  replay: ChartIntelligenceState['replay']
}

const SPEEDS: ReplaySpeed[] = [0.5, 1, 2]

export function ReplayControls({ replay }: Props) {
  const { bounds, asOf, isLive, playing, speed, setSpeed, blocked, loading, hasFrames } = replay
  if (!bounds || asOf == null) return null

  const spanFirst = hasFrames ? asOf : bounds.first
  // Index approximatif sur la fenêtre replay (lookback) ; suffisant pour le slider.
  const total = Math.max(1, Math.round((bounds.last - bounds.first) / bounds.bar_seconds))
  const idx = Math.max(0, Math.min(total, Math.round((asOf - bounds.first) / bounds.bar_seconds)))
  const playDisabled = blocked
  const playLabel = blocked
    ? 'Replay en cours de correction'
    : loading
      ? 'Chargement…'
      : playing
        ? 'PAUSE'
        : 'PLAY'

  void spanFirst

  return (
    <div className="ci-replay" role="group" aria-label="Replay">
      <div className="ci-replay-btns">
        <button
          type="button"
          onClick={() => replay.step(-1)}
          disabled={playDisabled || loading || idx <= 0}
          aria-label="Bougie précédente"
        >
          ◀
        </button>
        <button
          type="button"
          className={`ci-replay-play${playing ? ' is-on' : ''}${playDisabled ? ' is-blocked' : ''}`}
          onClick={playing ? replay.pause : () => void replay.play()}
          disabled={playDisabled || loading}
          title={blocked ? 'Replay en cours de correction (CI-R1)' : undefined}
        >
          {playLabel}
        </button>
        <button
          type="button"
          onClick={() => replay.step(1)}
          disabled={playDisabled || loading || isLive}
          aria-label="Bougie suivante"
        >
          ▶
        </button>
      </div>
      <div className="ci-replay-speeds" role="group" aria-label="Vitesse">
        {SPEEDS.map((s) => (
          <button
            key={s}
            type="button"
            className={speed === s ? 'is-on' : undefined}
            onClick={() => setSpeed(s)}
            disabled={playDisabled}
          >
            {s}×
          </button>
        ))}
      </div>
      <input
        className="ci-replay-range"
        type="range"
        min={0}
        max={total}
        value={idx}
        disabled={playDisabled || loading}
        onChange={(e) => replay.seek(bounds.first + Number(e.target.value) * bounds.bar_seconds)}
        aria-label="Position du replay"
      />
      <span className="ci-replay-meta mono">
        {blocked ? 'REPLAY BLOQUÉ' : isLive ? 'LIVE' : `REPLAY ${idx}/${total}`} · {fmtTime(asOf)}
      </span>
      {!isLive && !blocked && (
        <button type="button" className="ci-replay-live" onClick={() => replay.seek(null)}>
          Live
        </button>
      )}
    </div>
  )
}
