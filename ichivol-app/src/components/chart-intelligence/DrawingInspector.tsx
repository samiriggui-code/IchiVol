/** DrawingInspector — détail de l'objet sélectionné (lecture seule des champs Python). */

import type { ReactNode } from 'react'
import {
  fmtPct,
  fmtPrice,
  fmtTime,
  objectTitle,
  producerLabel,
  STATUS_LABELS,
  statusTone,
  type IntelligenceObject,
} from '../../lib/chartIntelligence'

interface Props {
  /** Objets de la sélection (un Fib = plusieurs niveaux du même group_id). */
  selection: IntelligenceObject[]
  onClose?: () => void
}

function Row({ k, children }: { k: string; children: ReactNode }) {
  return (
    <div className="ci-kv">
      <span>{k}</span>
      <b>{children}</b>
    </div>
  )
}

export function DrawingInspector({ selection, onClose }: Props) {
  const o = selection[0]
  if (!o) {
    return (
      <section className="ci-card ci-inspector is-empty" aria-label="Inspecteur">
        <header className="ci-card-head">
          <div className="ci-eyebrow">DRAWING INSPECTOR</div>
        </header>
        <p className="ci-muted">Sélectionner un objet sur le graphique (zone, Fib, FVG, BOS…).</p>
      </section>
    )
  }
  const og = o.origin
  const status = og.status
  const tf = (og.htf ?? o.timeframe).toUpperCase()

  let range: ReactNode = null
  if (og.kind === 'fibonacci') {
    range = (
      <>
        <Row k="FROM">{fmtPrice(og.anchor_start?.price ?? og.swing_low)}</Row>
        <Row k="TO">{fmtPrice(og.anchor_end?.price ?? og.swing_high)}</Row>
        <Row k="LEVELS">
          {[...selection]
            .sort((a, b) => (a.origin.ratio ?? 0) - (b.origin.ratio ?? 0))
            .map((lv) => `${((lv.origin.ratio ?? 0) * 100).toFixed(1)}`)
            .join(' · ')}
        </Row>
      </>
    )
  } else if (o.price_low != null && o.price_high != null) {
    range = (
      <>
        <Row k="LOW">{fmtPrice(o.price_low)}</Row>
        <Row k="HIGH">{fmtPrice(o.price_high)}</Row>
      </>
    )
  } else if (o.points.length >= 2) {
    range = (
      <>
        <Row k="FROM">{`${fmtPrice(o.points[0]!.price)} · ${fmtTime(o.points[0]!.time)}`}</Row>
        <Row k="TO">{`${fmtPrice(o.points[1]!.price)} · ${fmtTime(o.points[1]!.time)}`}</Row>
      </>
    )
  } else if (o.points[0]) {
    range = <Row k="LEVEL">{`${fmtPrice(og.level ?? o.points[0].price)} · ${fmtTime(o.points[0].time)}`}</Row>
  }

  return (
    <section className="ci-card ci-inspector" aria-label="Inspecteur">
      <header className="ci-card-head">
        <div>
          <div className="ci-eyebrow">DRAWING INSPECTOR</div>
          <h3>{objectTitle(o).toUpperCase()}</h3>
        </div>
        {onClose && (
          <button type="button" className="ci-icon-btn" onClick={onClose} aria-label="Fermer l’inspecteur">
            ×
          </button>
        )}
      </header>
      <div className="ci-kvs">
        <Row k="SOURCE">{producerLabel(o)}</Row>
        <Row k="TIMEFRAME">{tf}</Row>
        {range}
        {og.touch_count != null && <Row k="TOUCHES">{og.touch_count}</Row>}
        {og.fill_ratio != null && <Row k="FILL">{fmtPct(og.fill_ratio)}</Row>}
        <Row k="CONFIDENCE">
          {fmtPct(o.confidence)}
          {og.score_is_mock ? <span className="ci-tag gray ci-ml">MOCK</span> : null}
        </Row>
        {status && (
          <Row k="STATUS">
            <span className={`ci-tag ${statusTone(status)}`}>{STATUS_LABELS[status]}</span>
          </Row>
        )}
        <Row k="KNOWN AT">{fmtTime(og.known_at)}</Row>
      </div>
      {og.components && og.components.length > 0 && (
        <div className="ci-block">
          <div className="ci-eyebrow">COMPONENTS</div>
          <ul className="ci-components">
            {og.components.map((c) => (
              <li key={c.label} className={c.satisfied === false ? 'is-off' : undefined}>
                <span>{c.label}</span>
                <small className="mono">{c.value ?? ''}</small>
                <em>{c.family}</em>
              </li>
            ))}
          </ul>
        </div>
      )}
      {og.reason && (
        <div className="ci-block">
          <div className="ci-eyebrow">WHY?</div>
          <p className="ci-why">{og.reason}</p>
        </div>
      )}
      <div className="ci-block ci-decision-row">
        <div className="ci-eyebrow">USED BY DECISION ENGINE</div>
        <span className={`ci-tag ${og.used_by_decision ? 'green' : 'gray'}`}>
          {og.used_by_decision ? 'YES' : 'NO'}
        </span>
      </div>
      <p className="ci-id mono" title="Identifiant déterministe ChartObject">
        {o.origin.group_id ?? o.id}
      </p>
    </section>
  )
}
