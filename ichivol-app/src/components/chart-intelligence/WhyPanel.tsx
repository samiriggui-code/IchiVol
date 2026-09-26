/**
 * WhyPanel — AW1 « Pourquoi ? ». Affiche l'explication moteur d'un objet
 * (GET /chart-intelligence/{symbol}/explain). Aucun calcul : lecture des faits
 * Python, chacun avec le champ source.
 */

import { useState } from 'react'
import {
  explainPositionLine,
  fmtExplainValue,
  fmtTime,
  getChartObjectExplanation,
  type ChartObjectExplanation,
} from '../../lib/chartIntelligence'

export interface WhyTarget {
  symbol: string
  timeframe: string
  objectId: string
  lineageKey?: string | null
  asOf?: number | null
}

const MATURITY_TONE: Record<string, string> = {
  PRODUCTION: 'green',
  VALIDATED: 'green',
  EXPERIMENTAL: 'amber',
  CANDIDATE: 'amber',
}

export function WhyPanel({ target }: { target: WhyTarget }) {
  const [data, setData] = useState<ChartObjectExplanation | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function load() {
    setBusy(true)
    setError(null)
    try {
      setData(await getChartObjectExplanation(target))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Échec')
    } finally {
      setBusy(false)
    }
  }

  if (!data) {
    return (
      <div className="ci-block ci-why-block">
        <button type="button" className="ci-why-btn" onClick={() => void load()} disabled={busy}>
          {busy ? 'Analyse moteur…' : 'Pourquoi ?'}
        </button>
        {error && (
          <p className="ci-why-error" role="alert">
            {error}
          </p>
        )}
      </div>
    )
  }

  const { identity, timeline, validation } = data
  const maturity = identity.maturity.status
  const position = explainPositionLine(data.context)
  const known = timeline.known_at != null ? fmtTime(timeline.known_at) : '—'

  return (
    <div className="ci-block ci-why-block" aria-label="Pourquoi cet objet ?">
      <div className="ci-eyebrow">POURQUOI ?</div>

      <div className="ci-why-tags">
        <span className={`ci-tag ${MATURITY_TONE[maturity] ?? 'gray'}`} title={identity.maturity.field ?? undefined}>
          {maturity}
        </span>
        <span className="ci-tag gray" title={validation.note}>
          {validation.label.toUpperCase()}
        </span>
      </div>

      <ul className="ci-list ci-why-list">
        <li>
          <span>Produit par</span>
          <b>{identity.engine ?? identity.producer ?? '—'}</b>
        </li>
        <li>
          <span>Détecté</span>
          <b>
            {timeline.known_at_is_upper_bound ? `au plus tard ${known}` : known}
            {timeline.detection_lag_bars != null && ` · ${timeline.detection_lag_bars} barre(s) après l'ancrage`}
          </b>
        </li>
        {data.facts.map((f) => (
          <li key={f.key} title={f.field}>
            <span>{f.label}</span>
            <b className="mono">{fmtExplainValue(f.value)}</b>
          </li>
        ))}
      </ul>

      {position && <p className="ci-why">{position}</p>}
      <p className="ci-why">{identity.pipeline}</p>

      {timeline.status_history.length > 1 && (
        <>
          <div className="ci-eyebrow ci-why-sub">HISTORIQUE</div>
          <ul className="ci-list ci-why-list">
            {timeline.status_history.map((h) => (
              <li key={h.at}>
                <span>{fmtTime(h.at)}</span>
                <b className="mono">
                  {[h.status, h.touch_count != null ? `${h.touch_count} touches` : null]
                    .filter(Boolean)
                    .join(' · ') || '—'}
                </b>
              </li>
            ))}
          </ul>
        </>
      )}

      {data.caveats.length > 0 && (
        <ul className="ci-why-caveats">
          {data.caveats.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      )}
      <p className="ci-why-note ci-muted">{validation.note}</p>
    </div>
  )
}
