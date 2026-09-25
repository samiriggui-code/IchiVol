/** Calques menu (desktop dropdown + mobile sheet) — maquette: Ichimoku + S/R + avancés. */

import { useState } from 'react'
import {
  ADVANCED_LAYER_META,
  isIchimokuOn,
  withIchimoku,
  type AdvancedLayerKey,
  type LayerPrefs,
  type ObjectLayerKey,
} from '../lib/marketPrefs'

interface Props {
  open: boolean
  onClose: () => void
  prefs: LayerPrefs
  onChange: (next: LayerPrefs) => void
  counts: Record<ObjectLayerKey, number>
  variant?: 'menu' | 'sheet'
}

export function MarketLayersMenu({
  open,
  onClose,
  prefs,
  onChange,
  counts,
  variant = 'menu',
}: Props) {
  const [advancedOpen, setAdvancedOpen] = useState(false)

  if (!open) return null

  const ichimokuOn = isIchimokuOn(prefs)
  const structureOn = prefs.structure

  const toggleAdvanced = (key: AdvancedLayerKey) => {
    onChange({ ...prefs, [key]: !prefs[key] })
  }

  const body = (
    <div className={`mkt-layers-panel ${variant === 'sheet' ? 'is-sheet' : 'is-menu'}`}>
      {variant === 'sheet' && (
        <header className="mkt-layers-sheet-head">
          <strong>Calques</strong>
          <button type="button" className="ghost" onClick={onClose}>
            Terminé
          </button>
        </header>
      )}

      <ul className="mkt-layers-list mkt-layers-primary">
        <li>
          <button
            type="button"
            className={`mkt-layer-row${ichimokuOn ? ' is-on' : ''}`}
            onClick={() => onChange(withIchimoku(prefs, !ichimokuOn))}
            aria-pressed={ichimokuOn}
          >
            <span className="mkt-layer-swatch" style={{ background: 'var(--cloud)' }} aria-hidden />
            <span className="mkt-layer-copy">
              <strong>Ichimoku</strong>
              <small>Nuage · Tenkan · Kijun (9 / 26 / 52)</small>
            </span>
            <span className="mkt-layer-switch" aria-hidden>
              {ichimokuOn ? '●' : '○'}
            </span>
          </button>
        </li>
        <li>
          <button
            type="button"
            className={`mkt-layer-row${structureOn ? ' is-on' : ''}`}
            onClick={() => onChange({ ...prefs, structure: !structureOn })}
            aria-pressed={structureOn}
          >
            <span className="mkt-layer-swatch" style={{ background: 'var(--bull)' }} aria-hidden />
            <span className="mkt-layer-copy">
              <strong>Supports / résistances</strong>
              <small>Zones S/R et trendlines</small>
            </span>
            <span className="mkt-layer-count mono">{counts.structure}</span>
            <span className="mkt-layer-switch" aria-hidden>
              {structureOn ? '●' : '○'}
            </span>
          </button>
        </li>
      </ul>

      <button
        type="button"
        className={`mkt-layers-advanced-toggle${advancedOpen ? ' is-open' : ''}`}
        aria-expanded={advancedOpen}
        onClick={() => setAdvancedOpen((v) => !v)}
      >
        Calques avancés
        <span aria-hidden>{advancedOpen ? '▾' : '▸'}</span>
      </button>

      {advancedOpen && (
        <>
          <ul className="mkt-layers-list mkt-layers-advanced">
            {ADVANCED_LAYER_META.map((m) => (
              <li key={m.key}>
                <button
                  type="button"
                  className={`mkt-layer-row${prefs[m.key] ? ' is-on' : ''}`}
                  onClick={() => toggleAdvanced(m.key)}
                  aria-pressed={prefs[m.key]}
                >
                  <span className="mkt-layer-swatch" style={{ background: m.color }} aria-hidden />
                  <span className="mkt-layer-copy">
                    <strong>{m.label}</strong>
                    <small>{m.subtitle}</small>
                  </span>
                  {m.key !== 'signals' && (
                    <span className="mkt-layer-count mono">{counts[m.key]}</span>
                  )}
                  <span className="mkt-layer-switch" aria-hidden>
                    {prefs[m.key] ? '●' : '○'}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          <div className="mkt-layers-opts">
            <label>
              <input
                type="checkbox"
                checked={prefs.fadeFilledFvg}
                onChange={(e) => onChange({ ...prefs, fadeFilledFvg: e.target.checked })}
              />
              Estomper les FVG remplis
            </label>
            <label>
              <input
                type="checkbox"
                checked={prefs.showInvalidated}
                onChange={(e) => onChange({ ...prefs, showInvalidated: e.target.checked })}
              />
              Montrer les invalidés
            </label>
          </div>
        </>
      )}

      {variant === 'sheet' && (
        <p className="muted mkt-layers-global">Réglage global — s’applique à tous les symboles</p>
      )}
    </div>
  )

  if (variant === 'sheet') {
    return (
      <div className="mkt-layers-sheet" role="dialog" aria-label="Calques">
        <button type="button" className="mkt-search-backdrop" aria-label="Fermer" onClick={onClose} />
        {body}
      </div>
    )
  }

  return body
}
