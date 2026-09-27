/** DrawingInspector — détail de l'objet sélectionné (lecture seule des champs Python). */

import { useState, type ReactNode } from 'react'
import {
  fmtPct,
  fmtPrice,
  fmtTime,
  INTELLIGENCE_LAYER_META,
  intelligenceLayerOf,
  objectTitle,
  producerLabel,
  selectionKeyOf,
  STATUS_LABELS,
  statusTone,
  type IntelligenceLayerPrefs,
  type IntelligenceObject,
} from '../../lib/chartIntelligence'
import { WhyPanel, type WhyTarget } from './WhyPanel'

const PER_LAYER_CAP = 6

interface Props {
  /** Objets de la sélection (un Fib = plusieurs niveaux du même group_id). */
  selection: IntelligenceObject[]
  /** Objets visibles (calques actifs). */
  candidates?: IntelligenceObject[]
  /** Préférences calques — une section inspecteur par calque ON. */
  layers?: IntelligenceLayerPrefs | null
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

/** Libellé liste : titre lisible + prix pour distinguer les doublons. */
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

function LayerBrowser({
  candidates,
  layers,
  onSelect,
}: {
  candidates: IntelligenceObject[]
  layers: IntelligenceLayerPrefs
  onSelect: (key: string) => void
}) {
  const byKey = uniqueCandidates(candidates)
  const activeMeta = INTELLIGENCE_LAYER_META.filter(
    (m) => m.key !== 'ichimoku' && layers[m.key],
  )
  /** Étagères repliées par défaut — une seule ouverte à la fois. */
  const [openKey, setOpenKey] = useState<string | null>(null)

  if (activeMeta.length === 0) {
    return (
      <p className="ci-muted">
        Aucun calque objet actif. Activez Market Structure, FVG, Fib… dans Palette signaux.
      </p>
    )
  }

  return (
    <div className="ci-inspect-layers" aria-label="Objets par calque actif">
      <p className="ci-inspect-hint">
        Compteurs = objets moteur à cet as_of. Fib = 1 dessin (plusieurs niveaux). 0 = rien détecté.
      </p>
      {activeMeta.map((m) => {
        const layerItems = byKey.filter((o) => intelligenceLayerOf(o) === m.key)
        const total = layerItems.length
        const items = layerItems.slice(0, PER_LAYER_CAP)
        const open = openKey === m.key
        return (
          <section key={m.key} className={`ci-inspect-layer${open ? ' is-open' : ''}`}>
            <button
              type="button"
              className="ci-inspect-layer-head"
              aria-expanded={open}
              onClick={() => setOpenKey(open ? null : m.key)}
            >
              <span className="ci-inspect-swatch" style={{ background: m.color }} aria-hidden />
              <div className="ci-inspect-layer-copy">
                <strong>{m.label}</strong>
                <small>{m.subtitle}</small>
              </div>
              <span className="ci-inspect-layer-count mono">{total}</span>
              <span className="ci-inspect-chevron" aria-hidden>
                {open ? '▾' : '▸'}
              </span>
            </button>
            {open &&
              (items.length === 0 ? (
                <p className="ci-inspect-empty">
                  {m.key === 'fibonacci'
                    ? 'Aucun Fib ancré sur la structure à cet as_of (ou 1 groupe déjà compté ailleurs).'
                    : 'Aucun objet moteur à cet as_of — normal si le calque n’a rien produit.'}
                </p>
              ) : (
                <ul className="ci-pick-list">
                  {items.map((c) => {
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
                  {total > items.length && (
                    <li className="ci-inspect-more muted">
                      +{total - items.length} autres — voir le graphique
                    </li>
                  )}
                </ul>
              ))}
          </section>
        )
      })}
    </div>
  )
}

export function DrawingInspector({
  selection,
  candidates = [],
  layers = null,
  onSelect,
  onClose,
  why = null,
}: Props) {
  const o = selection[0]
  if (!o) {
    return (
      <section className="ci-card ci-inspector is-empty" aria-label="Inspecteur">
        <header className="ci-card-head">
          <div>
            <div className="ci-eyebrow">DRAWING INSPECTOR</div>
            <p className="ci-source-line">Calques ON · étagères ▸ pour dérouler</p>
          </div>
        </header>
        {layers && onSelect ? (
          <LayerBrowser candidates={candidates} layers={layers} onSelect={onSelect} />
        ) : (
          <p className="ci-muted">Sélectionner un objet sur le graphique (zone, Fib, FVG, BOS…).</p>
        )}
      </section>
    )
  }
  const og = o.origin
  const status = og.status
  const tf = (og.htf ?? o.timeframe).toUpperCase()
  const layerMeta = INTELLIGENCE_LAYER_META.find((m) => m.key === intelligenceLayerOf(o))

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
          {layerMeta && (
            <p className="ci-source-line" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span className="ci-inspect-swatch" style={{ background: layerMeta.color }} aria-hidden />
              {layerMeta.label}
            </p>
          )}
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
