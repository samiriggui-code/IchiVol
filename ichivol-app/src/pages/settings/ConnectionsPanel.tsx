import { SOURCES } from './settingsConstants'
import type { useSettingsController } from './useSettingsController'

type Ctrl = ReturnType<typeof useSettingsController>

export function ConnectionsPanel({ c }: { c: Ctrl }) {
  const {
    activeSources,
    apiMissing,
    clearTwelveDataKey,
    saving,
    setClearTwelveDataKey,
    setPendingClearTwelve,
    setTwelveDataApiKey,
    toggleSource,
    twelveDataApiKey,
    twelveDataApiKeySet,
  } = c

  return (
    <>
            <section className="panel settings-section">
              <header className="panel-head">
                <h2>Feeds de données actifs</h2>
                <span className="panel-meta">Public · pas de trading</span>
              </header>
              <div className="settings-body settings-sources">
                <p className="muted settings-feed-note">
                  Ces cases choisissent d’où viennent les OHLCV. Aucune clé exchange, aucun ordre —
                  voir{' '}
                  <a
                    href="https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Market Data Only
                  </a>
                  .
                </p>
                {SOURCES.map((s) => (
                  <label key={s.id} className="settings-check">
                    <input
                      type="checkbox"
                      checked={activeSources.includes(s.id)}
                      onChange={() => toggleSource(s.id)}
                    />
                    {s.label}
                  </label>
                ))}
              </div>
              <div className="settings-body">
                <button type="submit" className="ghost settings-save" disabled={saving || apiMissing}>
                  {saving ? 'Enregistrement…' : 'Enregistrer'}
                </button>
              </div>
            </section>
            <section className="panel settings-section">
              <header className="panel-head">
                <h2>Twelve Data (actions)</h2>
                <span className="panel-meta">{twelveDataApiKeySet ? 'Clé perso active' : 'Clé opérateur'}</span>
              </header>
              <div className="settings-body">
                <p className="muted settings-feed-note">
                  Forex, métaux, indices et énergie sont gratuits (biquote) et n’ont pas besoin de
                  clé. AAPL/TSLA restent sur Twelve Data, dont le quota gratuit (~8 crédits/min) est
                  partagé par défaut. Ajoute ta propre clé pour utiliser ton quota à toi plutôt que
                  celui de l’opérateur.
                </p>
                <div className="controls">
                  <label className="settings-grow">
                    {twelveDataApiKeySet ? 'Nouvelle clé (optionnel)' : 'Clé API Twelve Data'}
                    <input
                      type="password"
                      value={twelveDataApiKey}
                      onChange={(e) => {
                        setTwelveDataApiKey(e.target.value)
                        setClearTwelveDataKey(false)
                      }}
                      placeholder="Clé Twelve Data…"
                      autoComplete="off"
                    />
                  </label>
                </div>
                {twelveDataApiKeySet && (
                  <label className="settings-check settings-clear-key">
                    <input
                      type="checkbox"
                      checked={clearTwelveDataKey}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setPendingClearTwelve(true)
                          return
                        }
                        setClearTwelveDataKey(false)
                      }}
                    />
                    Effacer ma clé (retour à la clé opérateur)
                  </label>
                )}
                <button type="submit" className="ghost settings-save" disabled={saving || apiMissing}>
                  {saving ? 'Enregistrement…' : 'Enregistrer'}
                </button>
              </div>
            </section>
    </>
  )
}
