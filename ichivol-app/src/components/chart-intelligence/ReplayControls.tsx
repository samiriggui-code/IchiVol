/**
 * ReplayControls — ◀ PLAY ▶ + curseur as_of. Chaque pas redemande un snapshot
 * « tel que connu à as_of » à la source (mock aujourd'hui, Python demain).
 */

import { fmtTime } from '../../lib/chartIntelligence'
import type { ChartIntelligenceState } from '../../lib/useChartIntelligence'

interface Props {
  replay: ChartIntelligenceState['replay']
}

export function ReplayControls({ replay }: Props) {
  const { bounds, asOf, isLive, playing } = replay
  if (!bounds || asOf == null) return null
  const total = Math.round((bounds.last - bounds.first) / bounds.bar_seconds)
  const idx = Math.round((asOf - bounds.first) / bounds.bar_seconds)
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
