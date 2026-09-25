/**
 * Paramètres — port littéral de design-reference/ichivol-workspace `parametres()` + page-head.
 * Classes HTML = maquette. Préférences locales + lecture settings engine (manquant → « — »).
 */

import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { getSettings, type AppSettings } from '../lib/settings'
import './SettingsPage.css'

type SettingsTab =
  | 'Marché et univers'
  | 'LLM'
  | 'Alertes'
  | 'Limites de risque'
  | 'Connexions'

type BadgeTone = 'green' | 'amber' | 'red' | 'gray' | ''

const TABS: SettingsTab[] = [
  'Marché et univers',
  'LLM',
  'Alertes',
  'Limites de risque',
  'Connexions',
]

const LS_KEY = 'ichivol-settings'

function badge(text: string, tone: BadgeTone = ''): ReactNode {
  let inferred = tone
  if (!inferred) {
    inferred = /PASSE|ACCEPTÉ|OUVERTE|VALIDÉ/i.test(text)
      ? 'green'
      : /REFUS|BLOQU|ERREUR/i.test(text)
        ? 'red'
        : /PRUDENCE|ARMED|WATCH/i.test(text)
          ? 'amber'
          : ''
  }
  return <span className={`tag ${inferred}`.trim()}>{text}</span>
}

function loadLocal(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(LS_KEY) || '{}') as Record<string, string>
  } catch {
    return {}
  }
}

export function SettingsPage() {
  const [settingsTab, setSettingsTab] = useState<SettingsTab>('Limites de risque')
  const [local, setLocal] = useState(loadLocal)
  const [engine, setEngine] = useState<AppSettings | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    getSettings()
      .then(setEngine)
      .catch(() => setEngine(null))
  }, [])

  const onSave = useCallback(
    (e: FormEvent<HTMLFormElement>) => {
      e.preventDefault()
      const fd = new FormData(e.currentTarget)
      const next: Record<string, string> = { ...local }
      fd.forEach((v, k) => {
        if (typeof v === 'string') next[k] = v
      })
      // checkboxes
      for (let i = 0; i < 4; i++) {
        next[`alert${i}`] = fd.get(`alert${i}`) ? '1' : '0'
      }
      try {
        localStorage.setItem(LS_KEY, JSON.stringify(next))
        setLocal(next)
        setSaved(true)
        window.setTimeout(() => setSaved(false), 1500)
      } catch {
        /* ignore */
      }
    },
    [local],
  )

  const riskDefaults = {
    trade: local.trade || '0.5',
    day: local.day || '3',
    exposure: local.exposure || '40',
    positions: local.positions || '6',
  }

  return (
    <div className="params-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">11 / ICHIVOL WORKSPACE</div>
          <h1>Paramètres</h1>
          <p className="subtitle">Votre environnement de travail.</p>
        </div>
        <div className="actions">{badge('DONNÉES LIVE', 'gray')}</div>
      </div>

      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            className={settingsTab === t ? 'active' : ''}
            onClick={() => setSettingsTab(t)}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="grid">
        <section className="card">
          <div className="card-head">
            <h2>{settingsTab}</h2>
          </div>
          <form id="settings-form" className="card-body" onSubmit={onSave}>
            {settingsTab === 'Limites de risque' && (
              <div className="grid equal">
                {(
                  [
                    ['trade', 'Risque par trade (%)'],
                    ['day', 'Risque par jour (%)'],
                    ['exposure', 'Exposition maximale (%)'],
                    ['positions', 'Positions simultanées'],
                  ] as const
                ).map(([id, label]) => (
                  <div className="field" key={id}>
                    <label htmlFor={id}>{label}</label>
                    <input
                      id={id}
                      name={id}
                      type="number"
                      step="0.1"
                      min="0.1"
                      max="100"
                      defaultValue={riskDefaults[id]}
                      required
                    />
                  </div>
                ))}
              </div>
            )}

            {settingsTab === 'Marché et univers' && (
              <>
                <div className="field">
                  <label>Univers</label>
                  <select name="universe" defaultValue="Crypto spot · Binance">
                    <option>Crypto spot · Binance</option>
                    <option>Multi-marchés · aperçu</option>
                  </select>
                </div>
                <div className="field">
                  <label>Unité de temps</label>
                  <select name="timeframe" defaultValue="1H">
                    <option>1H</option>
                    <option>4H</option>
                    <option>1D</option>
                  </select>
                </div>
                <div className="field">
                  <label>Seuil RVOL</label>
                  <input
                    name="rvol"
                    type="number"
                    min="0.1"
                    step="0.1"
                    defaultValue={
                      engine?.volumeParams?.rvolConfirm != null
                        ? String(engine.volumeParams.rvolConfirm)
                        : local.rvol || '1.5'
                    }
                  />
                </div>
              </>
            )}

            {settingsTab === 'LLM' && (
              <>
                <div className="field">
                  <label>Modèle d’analyse</label>
                  <select
                    name="llmModel"
                    defaultValue={engine?.llmModel || ''}
                    disabled={!engine}
                  >
                    {engine?.llmModel ? (
                      <option value={engine.llmModel}>{engine.llmModel}</option>
                    ) : (
                      <option value="">—</option>
                    )}
                  </select>
                </div>
                <p style={{ fontSize: 12, color: 'var(--muted)' }}>
                  Les clés et l’appel au modèle restent gérés par votre serveur.
                  {engine
                    ? ` Provider actif : ${engine.llmProvider}${engine.llmReady ? ' · prêt' : ' · non prêt'}.`
                    : ' Settings engine : —.'}
                </p>
              </>
            )}

            {settingsTab === 'Alertes' &&
              ['Signal déclenché', 'Décision refusée', 'Donnée périmée', 'Stop modifié'].map(
                (l, i) => (
                  <label className="checkrow" key={l}>
                    {l}
                    <input
                      name={`alert${i}`}
                      type="checkbox"
                      defaultChecked={local[`alert${i}`] !== '0'}
                    />
                  </label>
                ),
              )}

            {settingsTab === 'Connexions' && (
              <>
                <div className="field">
                  <label>Connexion moteur</label>
                  <input
                    value={engine ? 'Connectée' : 'Non connectée'}
                    disabled
                    readOnly
                  />
                  <small>
                    {engine
                      ? 'Contrat API settings OK.'
                      : 'La connexion nécessite le contrat API de votre moteur.'}
                  </small>
                </div>
                <div className="statline">
                  <span>Données de marché</span>
                  <b>{badge(engine ? 'LIVE' : '—', 'gray')}</b>
                </div>
                <div className="statline">
                  <span>Broker</span>
                  <b>{badge('NON CONNECTÉ', 'gray')}</b>
                </div>
              </>
            )}

            <button type="submit" className="primary">
              {saved ? 'Enregistré' : 'Enregistrer les préférences'}
            </button>
            <p style={{ fontSize: 10, color: 'var(--muted)' }}>
              Préférences enregistrées dans ce navigateur. Aucune modification du moteur.
            </p>
          </form>
        </section>

        <section className="card">
          <div className="card-head">
            <h2>Environnement</h2>
          </div>
          <div className="card-body">
            <div className="statline">
              <span>Mode</span>
              <b>{badge('PAPER', 'gray')}</b>
            </div>
            <div className="statline">
              <span>Exécution réelle</span>
              <b>{badge('BLOQUÉE')}</b>
            </div>
            <div className="statline">
              <span>Bougies analysées</span>
              <b>Clôturées</b>
            </div>
            <h3 style={{ marginTop: 28 }}>Identité IchiVol</h3>
            <p style={{ fontSize: 12, color: 'var(--muted)' }}>
              Fond crème, surfaces sobres, couleurs réservées aux décisions. Une lecture
              cohérente sur les onze espaces.
            </p>
          </div>
        </section>
      </div>
    </div>
  )
}
