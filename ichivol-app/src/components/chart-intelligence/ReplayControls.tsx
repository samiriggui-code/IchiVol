/**
 * ReplayControls — PLAY progressif sur fenêtre récente + vitesse 0.5× / 1× / 2×.
 * Le curseur filtre le snapshot live côté client (pas de re-fetch fulgurant).
 */

import { fmtTime } from '../../lib/chartIntelligence'
import type { ChartIntelligenceState, ReplaySpeed } from '../../lib/useChartIntelligence'

interface Props {
  replay: ChartIntelligenceState['replay']
}

const SPEEDS: ReplaySpeed[] = [0.5, 1, 2]

export function ReplayControls({ replay }: Props) {
  const { bounds, asOf, isLive, playing, speed, setSpeed } = replay
  if (!bounds || asOf == null) return null
  const total = Math.max(1, Math.round((bounds.last - bounds.first) / bounds.bar_seconds))
  const idx = Math.max(0, Math.min(total, Math.round((asOf - bounds.first) / bounds.bar_seconds)))
  return (
    <div className="ci-replay" role="group" aria-label="Replay">
      <div className="ci-replay-btns">
        <button type="button" onClick={() => replay.step(-1)} disabled={idx <= 0} aria-label="Bougie précédente">
          ◀
        </button>
        <button
          type="button"
          className={`ci-replay-play${playing ? ' is-on' : ''}`}
          onClick={playing ? replay.pause : replay.play}
        >
          {playing ? 'PAUSE' : 'PLAY'}
        </button>
        <button type="button" onClick={() => replay.step(1)} disabled={isLive} aria-label="Bougie suivante">
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
        onChange={(e) => replay.seek(bounds.first + Number(e.target.value) * bounds.bar_seconds)}
        aria-label="Position du replay"
      />
      <span className="ci-replay-meta mono">
        {isLive ? 'LIVE' : `REPLAY ${idx}/${total}`} · {fmtTime(asOf)}
      </span>
      {!isLive && (
        <button type="button" className="ci-replay-live" onClick={() => replay.seek(null)}>
          Live
        </button>
      )}
    </div>
  )
}
