/** Calques menu (desktop dropdown + mobile sheet) — Structure / Fib / FVG / Cassures… */

import {
  OBJECT_LAYER_META,
  type LayerPrefs,
  type ObjectLayerKey,
} from '../lib/marketPrefs'
import './MarketLayersMenu.css'

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
  if (!open) return null

  const toggle = (key: ObjectLayerKey) => {
    onChange({ ...prefs, [key]: !prefs[key] })
  }

  const body = (
    <div className={`mkt-layers-panel ${variant === 'sheet' ? 'is-sheet' : 'is-menu'}`}>
      {variant === 'sheet' && (
        <header className="mkt-layers-sheet-head">
          <strong>Calques</strong>
          <button type="button" className="mkt-layers-done" onClick={onClose}>
            Terminé
          </button>
        </header>
      )}
      <ul className="mkt-layers-list">
        {OBJECT_LAYER_META.map((m) => (
          <li key={m.key}>
            <button
              type="button"
              className={`mkt-layer-row${prefs[m.key] ? ' is-on' : ''}`}
              onClick={() => toggle(m.key)}
              aria-pressed={prefs[m.key]}
            >
              <span className="mkt-layer-swatch" style={{ background: m.color }} aria-hidden />
              <span className="mkt-layer-copy">
                <strong>{m.label}</strong>
                <small>
                  {m.subtitle}
                  {m.emptyUntil ? ` · vide jusqu’à ${m.emptyUntil}` : ''}
                </small>
              </span>
              <span className="mkt-layer-count mono">{counts[m.key]}</span>
              <span className="mkt-layer-eye" aria-hidden>
                {prefs[m.key] ? '◉' : '○'}
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
      {variant === 'sheet' && (
        <p className="mkt-layers-global">Réglage global — s’applique à tous les symboles</p>
      )}
    </div>
  )

  if (variant === 'sheet') {
    return (
      <div className="mkt-layers-sheet" role="dialog" aria-label="Calques">
        <button type="button" className="mkt-layers-backdrop" aria-label="Fermer" onClick={onClose} />
        {body}
      </div>
    )
  }

  return body
}
