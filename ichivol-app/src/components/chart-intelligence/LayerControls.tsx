/**
 * LayerControls — active / masque les couches Chart Intelligence.
 * Réutilise le balisage et le CSS de MarketLayersMenu (.mkt-layer-row…) et
 * les couleurs de OBJECT_LAYER_META (via INTELLIGENCE_LAYER_META) : même rendu que le bouton « Calques » du Marché.
 */

import {
  DEFAULT_INTELLIGENCE_LAYERS,
  INTELLIGENCE_LAYER_META,
  type IntelligenceLayerKey,
  type IntelligenceLayerPrefs,
} from '../../lib/chartIntelligence'
import '../MarketLayersMenu.css'

interface Props {
  prefs: IntelligenceLayerPrefs
  onChange: (next: IntelligenceLayerPrefs) => void
  counts?: Partial<Record<IntelligenceLayerKey, number>>
}

export function LayerControls({ prefs, onChange, counts }: Props) {
  const setAll = (on: boolean) =>
    onChange(
      Object.fromEntries(Object.keys(prefs).map((k) => [k, on])) as IntelligenceLayerPrefs,
    )
  return (
    <div className="ci-layers" role="group" aria-label="Calques Chart Intelligence">
      <div className="mkt-layers-quick">
        <button type="button" onClick={() => setAll(true)}>
          Tout afficher
        </button>
        <button type="button" onClick={() => setAll(false)}>
          Tout masquer
        </button>
        <button type="button" onClick={() => onChange(DEFAULT_INTELLIGENCE_LAYERS)}>
          Défaut
        </button>
      </div>
      <ul className="mkt-layers-list">
        {INTELLIGENCE_LAYER_META.map((m) => (
          <li key={m.key}>
            <button
              type="button"
              className={`mkt-layer-row${prefs[m.key] ? ' is-on' : ''}`}
              onClick={() => onChange({ ...prefs, [m.key]: !prefs[m.key] })}
              aria-pressed={prefs[m.key]}
            >
              <span className="mkt-layer-swatch" style={{ background: m.color }} aria-hidden />
              <span className="mkt-layer-copy">
                <strong>{m.label}</strong>
                <small>{m.subtitle}</small>
              </span>
              <span className="mkt-layer-count mono">{m.key === 'ichimoku' ? '—' : (counts?.[m.key] ?? 0)}</span>
              <span className="mkt-layer-eye" aria-hidden>
                {prefs[m.key] ? '◉' : '○'}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
