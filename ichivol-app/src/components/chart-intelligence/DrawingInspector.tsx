/** DrawingInspector — détail de l'objet sélectionné (lecture seule des champs Python). */

import type { ReactNode } from 'react'
import {
  fmtPct,
  fmtPrice,
  fmtTime,
  objectTitle,
  producerLabel,
  selectionKeyOf,
  STATUS_LABELS,
  statusTone,
  type IntelligenceObject,
} from '../../lib/chartIntelligence'
import { WhyPanel, type WhyTarget } from './WhyPanel'

interface Props {
  /** Objets de la sélection (un Fib = plusieurs niveaux du même group_id). */
  selection: IntelligenceObject[]
  /** Objets visibles (calques actifs) — liste de secours si rien n’est sélectionné. */
  candidates?: IntelligenceObject[]
  onSelect?: (key: string) => void
  onClose?: () => void
  /** AW1 : contexte pour « Pourquoi ? » (API moteur seulement, pas en mock). */
  why?: Omit<WhyTarget, 'objectId' | 'lineageKey'> | null
}

function Row({ k, children }: { k: string; children: ReactNode }) {
  return (
    <div className="ci-kv">
      <span>{k}</span>
      <b>{children}</b>
    </div>
  )
}

/** Une entrée par clé de sélection (Fib = un bloc). */
function uniqueCandidates(objects: IntelligenceObject[]): IntelligenceObject[] {
  const seen = new Set<string>()
  const out: IntelligenceObject[] = []
  for (const o of objects) {
    const k = selectionKeyOf(o)
    if (seen.has(k)) continue
    seen.add(k)
    out.push(o)
  }
  return out
}

/** Libellé liste de secours : titre lisible + prix pour distinguer les doublons. */
function pickLabel(o: IntelligenceObject): { title: string; meta: string; tone: 'bull' | 'bear' | 'muted' } {
  const og = o.origin
  const dir = og.direction === 'bearish' ? ' ↓' : og.direction === 'bullish' ? ' ↑' : ''
  const tone: 'bull' | 'bear' | 'muted' =
    og.direction === 'bearish' ? 'bear' : og.direction === 'bullish' ? 'bull' : 'muted'
  const px =
    og.level ??
    o.points[0]?.price ??
    (o.price_low != null && o.price_high != null ? (o.price_low + o.price_high) / 2 : null)
  const price = px != null ? fmtPrice(px) : ''

  if (og.kind === 'structure_event') {
    const tag = og.event_type === 'CHOCH' ? 'Change of character' : 'Break of structure'
    return { title: `${tag}${dir}`, meta: price, tone }
  }
  if (og.kind === 'fvg') {
    return {
      title: `${og.direction === 'bearish' ? 'Bearish' : 'Bullish'} FVG`,
      meta: price,
      tone,
    }
  }
  if (og.kind === 'fibonacci') {
    return { title: 'Fibonacci', meta: price, tone: 'muted' }
  }
  if (og.kind === 'liquidity') {
    return { title: o.side === 'resistance' ? 'Buy-side liquidity' : 'Sell-side liquidity', meta: price, tone }
  }
  if (og.kind === 'confluence') {
    return { title: 'Confluence', meta: price, tone: 'muted' }
  }
  if (og.kind === 'swing') {
    return { title: `Swing ${og.swing ?? ''}`.trim(), meta: price, tone }
  }
  if (o.side === 'resistance') return { title: 'Resistance', meta: price, tone: 'bear' }
  if (o.side === 'support') return { title: 'Support', meta: price, tone: 'bull' }
  return { title: objectTitle(o), meta: price || fmtPct(o.confidence), tone: 'muted' }
}

export function DrawingInspector({
  selection,
  candidates = [],
  onSelect,
  onClose,
  why = null,
}: Props) {
  const o = selection[0]
  if (!o) {
    const picks = uniqueCandidates(candidates).slice(0, 10)
    return (
      <section className="ci-card ci-inspector is-empty" aria-label="Inspecteur">
        <header className="ci-card-head">
          <div className="ci-eyebrow">DRAWING INSPECTOR</div>
        </header>
        <p className="ci-muted">
          Cliquez une zone / Fib / FVG / BOS sur le graphique, ou une ligne ci-dessous pour inspecter.
        </p>
        {picks.length > 0 && onSelect ? (
          <ul className="ci-pick-list" aria-label="Objets visibles">
            {picks.map((c) => {
              const pick = pickLabel(c)
              return (
                <li key={selectionKeyOf(c)}>
                  <button
                    type="button"
                    className={`ci-pick-btn ci-pick-btn--${pick.tone}`}
                    onClick={() => onSelect(selectionKeyOf(c))}
                  >
                    <span className="ci-pick-title">{pick.title}</span>
                    <span className="ci-pick-meta mono">
                      {pick.meta}
                      {pick.meta ? ' · ' : ''}
                      {fmtPct(c.confidence)}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        ) : (
          <p className="ci-muted">Aucun objet sur les calques actifs. Activez un pack (Structure, FVG…).</p>
        )}
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
      {og.used_by_decision != null && (
        <div className="ci-block ci-decision-row">
          <div className="ci-eyebrow">USED BY DECISION ENGINE</div>
          <span className={`ci-tag ${og.used_by_decision ? 'green' : 'gray'}`}>
            {og.used_by_decision ? 'YES' : 'NO'}
          </span>
        </div>
      )}
      {why && o.source === 'engine' && (
        <WhyPanel
          key={`${o.id}:${why.asOf ?? 'live'}`}
          target={{
            ...why,
            objectId: o.id,
            lineageKey: typeof og.lineage_key === 'string' ? og.lineage_key : null,
          }}
        />
      )}
      <p className="ci-id mono" title="Identifiant déterministe ChartObject">
        {o.origin.group_id ?? o.id}
      </p>
    </section>
  )
}
