import './SettingsPage.css'
import { SettingsDialogs } from './settings/SettingsDialogs'
import { SettingsForm } from './settings/SettingsForm'
import { SECTIONS } from './settings/settingsConstants'
import { useSettingsController } from './settings/useSettingsController'

export function SettingsPage() {
  const c = useSettingsController()
  const { loading, section, setSection, setError, setSaved, apiMissing, error, saved, testResult } = c

  if (loading) {
    return (
      <div className="settings-layout">
        <aside className="settings-nav panel">
          <p className="settings-nav-title">Paramètres</p>
        </aside>
        <div className="settings-main">
          <p className="muted">Chargement…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="settings-layout">
      <aside className="settings-nav panel" aria-label="Sections paramètres">
        <p className="settings-nav-title">Paramètres</p>
        <nav className="settings-nav-list">
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`settings-nav-item${section === s.id ? ' is-active' : ''}`}
              onClick={() => {
                setSection(s.id)
                setError(null)
                setSaved(false)
              }}
            >
              <span className="settings-nav-label">{s.label}</span>
              <span className="settings-nav-blurb muted">{s.blurb}</span>
            </button>
          ))}
        </nav>
      </aside>

      <div className="settings-main">
        <header className="iv-page-header page-head">
          <p className="iv-page-eyebrow">Système · Paramètres</p>
          <h1>{SECTIONS.find((s) => s.id === section)?.label}</h1>
          <p className="iv-page-question">Quels réglages gouvernent le cockpit ?</p>
          <p className="muted">
            {section === 'llm'
              ? 'LLM actif en haut. Ajoute ou remplace la clé seulement si tu changes de provider.'
              : section === 'connections'
                ? 'Données publiques — aucune clé exchange requise.'
                : section === 'market'
                  ? 'Seuils Ichimoku / RVOL persistés ; univers moteur en lecture seule.'
                  : section === 'risk'
                    ? 'Limites Risk Kernel en lecture — modification prévue dans une tranche engine.'
                    : section === 'environment'
                      ? 'Mode paper, exécution réelle désactivée, identité session.'
                      : 'Alertes push pour positions paper ouvertes.'}
          </p>
        </header>

        {apiMissing && (
          <div className="banner error" role="alert">
            API <code>/api/settings</code> indisponible — {error}.
          </div>
        )}
        {!apiMissing && error && (
          <div className="banner error" role="alert">
            {error}
          </div>
        )}
        {saved && !error && (
          <div className="banner settings-ok" role="status">
            Paramètres enregistrés.
          </div>
        )}
        {testResult?.ok && (
          <div className="banner settings-ok" role="status">
            {testResult.message} · {testResult.latencyMs} ms
          </div>
        )}

        <SettingsForm c={c} />
      </div>

      <SettingsDialogs c={c} />
    </div>
  )
}
