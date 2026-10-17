/**
 * Réglages « Ève et JEV » — lus et écrits sur le moteur (`/api/engine/eve/settings/*`).
 * Chaque réglage : une phrase d'explication, valeur actuelle, défaut, effet d'une hausse / d'une baisse.
 */

import { useMemo, useState } from 'react'
import {
  patchEveSettingsValues,
  sortedSchemaGroups,
  type EveSettingGroup,
  type EveSettingItem,
} from '../../lib/eveSettings'
import {
  EVE_KNOBS,
  EVE_MODES,
  formatKnob,
  fromDisplay,
  jevServiceLabel,
  toDisplay,
  type KnobCopy,
  type KnobGroup,
} from './eveCopy'

type Value = string | number | boolean

type Props = {
  schema: Record<string, EveSettingGroup> | null
  values: Record<string, Value>
  loadError: string | null
  onSaved: (values: Record<string, Value>) => void
}

type Knob = { item: EveSettingItem; copy: KnobCopy | undefined }

function editable(item: EveSettingItem): boolean {
  return Boolean(item.writable) && !item.read_only
}

export function EveSettings({ schema, values, loadError, onSaved }: Props) {
  /** Brouillon : texte saisi pour les nombres, booléen pour les interrupteurs. */
  const [draft, setDraft] = useState<Record<string, string | boolean>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savedAt, setSavedAt] = useState<number | null>(null)

  const knobs = useMemo(() => {
    const byGroup: Record<KnobGroup | 'other', Knob[]> = {
      decision: [],
      news: [],
      server: [],
      autonomy: [],
      other: [],
    }
    if (!schema) return byGroup
    for (const [, group] of sortedSchemaGroups(schema)) {
      for (const item of group.items) {
        const copy = EVE_KNOBS[item.key]
        if (copy) byGroup[copy.group].push({ item, copy })
        else if (editable(item)) byGroup.other.push({ item, copy: undefined })
      }
    }
    return byGroup
  }, [schema])

  const allEditable = useMemo(
    () => [...knobs.decision, ...knobs.news, ...knobs.other].filter((k) => editable(k.item)),
    [knobs],
  )

  /** Changements valides prêts à envoyer, + champs invalides. */
  const { patch, invalid } = useMemo(() => {
    const out: Record<string, Value> = {}
    const bad: string[] = []
    for (const { item, copy } of allEditable) {
      if (!(item.key in draft)) continue
      const d = draft[item.key]
      if (typeof d === 'boolean') {
        if (d !== Boolean(values[item.key])) out[item.key] = d
        continue
      }
      const n = fromDisplay(copy, d ?? '')
      if (n == null) {
        bad.push(copy?.label ?? item.label)
        continue
      }
      if (n !== Number(values[item.key])) out[item.key] = n
    }
    return { patch: out, invalid: bad }
  }, [allEditable, draft, values])

  const changeCount = Object.keys(patch).length

  async function save() {
    if (changeCount === 0 || invalid.length > 0) return
    setSaving(true)
    setError(null)
    try {
      const res = await patchEveSettingsValues(patch)
      onSaved(res.values)
      setDraft({})
      setSavedAt(Date.now())
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Enregistrement impossible')
    } finally {
      setSaving(false)
    }
  }

  function renderKnob({ item, copy }: Knob) {
    const unit = copy?.unit ?? (item.type === 'boolean' ? 'switch' : undefined)
    const label = copy?.label ?? item.label
    const current = values[item.key]
    const def = item.default
    const canEdit = editable(item) && !copy?.unused
    const id = `eve-${item.key}`

    if (unit === 'switch' || item.type === 'boolean') {
      const checked = item.key in draft ? Boolean(draft[item.key]) : Boolean(current)
      return (
        <div key={item.key} className={`knob${copy?.unused ? ' is-unused' : ''}`}>
          <div className="knob-main">
            <label className="knob-label" htmlFor={id}>
              {label}
            </label>
            <label className="switch">
              <input
                id={id}
                type="checkbox"
                checked={copy?.unused ? false : checked}
                disabled={!canEdit}
                onChange={(e) => setDraft((p) => ({ ...p, [item.key]: e.target.checked }))}
              />
              <span aria-hidden="true" />
            </label>
          </div>
          <p className="knob-explain">{copy?.explain ?? item.description}</p>
          {copy?.unused ? (
            <span className="tag gray">Pas encore utilisé par le moteur</span>
          ) : def !== undefined ? (
            <p className="knob-meta">Par défaut : {formatKnob('switch', Boolean(def))}</p>
          ) : null}
        </div>
      )
    }

    const shown = item.key in draft ? String(draft[item.key]) : toDisplay(unit, current)
    const bad = item.key in draft && fromDisplay(copy, String(draft[item.key])) == null
    const changed = item.key in patch
    const differsFromDefault = def !== undefined && Number(current) !== Number(def)
    const suffix = unit === 'pct' ? '%' : unit === 'seconds' ? 's' : unit === 'days' ? 'jours' : ''
    return (
      <div key={item.key} className="knob">
        <div className="knob-main">
          <label className="knob-label" htmlFor={id}>
            {label}
          </label>
          <div className={`num-input${bad ? ' bad' : ''}`}>
            <input
              id={id}
              type="number"
              inputMode="decimal"
              min={copy?.min}
              max={copy?.max}
              step={copy?.step ?? 'any'}
              disabled={!canEdit}
              value={shown}
              onChange={(e) => setDraft((p) => ({ ...p, [item.key]: e.target.value }))}
            />
            {suffix ? <span>{suffix}</span> : null}
          </div>
        </div>
        <p className="knob-explain">{copy?.explain ?? item.description}</p>
        {copy?.up || copy?.down ? (
          <ul className="knob-effects">
            {copy.up ? (
              <li>
                <b>Plus haut :</b> {copy.up}
              </li>
            ) : null}
            {copy.down ? (
              <li>
                <b>Plus bas :</b> {copy.down}
              </li>
            ) : null}
          </ul>
        ) : null}
        <p className="knob-meta">
          Actuel : <b>{formatKnob(unit, current)}</b>
          {def !== undefined ? <> · Par défaut : {formatKnob(unit, def)}</> : null}
          {changed ? <span className="tag amber">Modifié, non enregistré</span> : null}
          {!changed && differsFromDefault && canEdit ? (
            <button
              type="button"
              className="linkish"
              onClick={() => setDraft((p) => ({ ...p, [item.key]: toDisplay(unit, def) }))}
            >
              Revenir au défaut
            </button>
          ) : null}
          {bad ? (
            <span className="knob-bad">
              Valeur attendue entre {copy?.min ?? 0} et {copy?.max ?? '∞'}.
            </span>
          ) : null}
        </p>
      </div>
    )
  }

  const radarOn = Boolean(
    'EVENT_RADAR_ENABLED' in draft ? draft.EVENT_RADAR_ENABLED : values.EVENT_RADAR_ENABLED,
  )
  const keySet = values.JEV_API_KEY === '***'

  return (
    <>
      <section className="card">
        <div className="card-head">
          <h2>Comment Ève décide</h2>
        </div>
        <div className="card-body">
          <p className="lede">
            Ève est une seule intelligence qui travaille en cinq modes. À chaque bougie clôturée,
            Analyst, Challenger, Guardian et Shadow interrogent JEV, le modèle de jugement d’IchiVol.
            Si JEV est injoignable, trop lent ou pas assez sûr, Ève n’ouvre rien.
          </p>
          <ol className="modes">
            {EVE_MODES.map((m) => (
              <li key={m.name}>
                <b>{m.name}</b>
                <span>{m.text}</span>
              </li>
            ))}
          </ol>
          <p className="hint">Les modes sont fixes : il n’y a rien à régler ici, c’est un rappel.</p>
        </div>
      </section>

      {loadError || !schema ? (
        <section className="card">
          <div className="card-body">
            <p className="notice err" role="alert">
              Les réglages d’Ève sont indisponibles : le moteur ne répond pas
              {loadError ? ` (${loadError})` : ''}. Rien n’est modifiable tant qu’il est injoignable.
            </p>
          </div>
        </section>
      ) : (
        <>
          <section className="card">
            <div className="card-head">
              <h2>Seuils de décision</h2>
            </div>
            <div className="card-body">
              <p className="lede">
                Ce qu’Ève exige de JEV avant d’agir. Ces seuils s’appliquent à toutes les décisions,
                automatiques ou demandées à la main.
              </p>
              {knobs.decision.map(renderKnob)}
            </div>
          </section>

          <section className="card">
            <div className="card-head">
              <h2>Veille d’actualité</h2>
              <span className={`tag ${radarOn ? 'green' : 'gray'}`}>{radarOn ? 'Activée' : 'Désactivée'}</span>
            </div>
            <div className="card-body">
              <p className="lede">
                Les actualités récentes de l’actif, résumées et ajoutées au contexte de JEV.
              </p>
              {knobs.news.map(renderKnob)}
            </div>
          </section>

          {knobs.other.length > 0 ? (
            <section className="card">
              <div className="card-head">
                <h2>Autres réglages du moteur</h2>
              </div>
              <div className="card-body">{knobs.other.map(renderKnob)}</div>
            </section>
          ) : null}

          <div className="savebar" role="region" aria-label="Enregistrer les réglages d’Ève">
            <div>
              {invalid.length > 0 ? (
                <span className="knob-bad">À corriger : {invalid.join(', ')}</span>
              ) : changeCount > 0 ? (
                <span>
                  {changeCount} modification{changeCount > 1 ? 's' : ''} en attente
                </span>
              ) : savedAt ? (
                <span className="ok-text">Enregistré. Le moteur applique les nouveaux seuils dès la prochaine décision.</span>
              ) : (
                <span className="muted">Aucune modification.</span>
              )}
              {error ? <span className="knob-bad"> {error}</span> : null}
            </div>
            <div className="btn-row tight">
              <button
                type="button"
                className="suggestion"
                disabled={saving || Object.keys(draft).length === 0}
                onClick={() => {
                  setDraft({})
                  setError(null)
                }}
              >
                Annuler
              </button>
              <button
                type="button"
                className="primary"
                disabled={saving || changeCount === 0 || invalid.length > 0}
                onClick={() => void save()}
              >
                {saving ? 'Enregistrement…' : 'Enregistrer'}
              </button>
            </div>
          </div>

          <section className="card">
            <div className="card-head">
              <h2>Service JEV</h2>
              <span className="tag gray">Réglé sur le serveur</span>
            </div>
            <div className="card-body">
              <p className="lede">
                Où Ève envoie ses questions. Ces informations se règlent sur le serveur du moteur
                et ne sont jamais modifiables depuis le navigateur, pour protéger la clé d’accès.
              </p>
              <div className="statline">
                <span>Service principal</span>
                <b>{jevServiceLabel(values.JEV_PROVIDER)}</b>
              </div>
              <div className="statline">
                <span>Secours si les crédits sont épuisés</span>
                <b>{jevServiceLabel(values.JEV_FALLBACK)}</b>
              </div>
              <div className="statline">
                <span>Clé d’accès</span>
                <b>
                  <span className={`tag ${keySet ? 'green' : 'amber'}`}>
                    {keySet ? 'Présente' : 'Absente'}
                  </span>
                </b>
              </div>
              <div className="statline">
                <span>Version du modèle (figée = jamais changée sans prévenir)</span>
                <b>{values.JEV_MODEL ? 'Figée' : 'Non figée'}</b>
              </div>
            </div>
          </section>
        </>
      )}
    </>
  )
}
