import { llmStatusLabel } from '../../lib/llmStatus'
import { DEFAULT_MODELS, type LlmProvider } from '../../lib/settings'
import { PROVIDERS, providerLabel } from './settingsConstants'
import type { useSettingsController } from './useSettingsController'

type Ctrl = ReturnType<typeof useSettingsController>

export function LlmPanel({ c }: { c: Ctrl }) {
  const {
    apiMissing,
    clearKey,
    connections,
    customModel,
    hasActiveLlm,
    llmApiKey,
    llmApiKeySet,
    llmProvider,
    llmReady,
    llmStatus,
    modelOptions,
    modelSelect,
    onProviderChange,
    onTest,
    resolvedModel,
    savedModel,
    savedProvider,
    saving,
    setClearKey,
    setCustomModel,
    setLlmApiKey,
    setModelSelect,
    setPendingClearLlm,
    setShowKeyForm,
    setTestResult,
    showKeyForm,
    testing,
  } = c
  const connLabel = llmStatusLabel(llmStatus.state)

  return (
            <>
              <section className="panel settings-section">
                <header className="panel-head">
                  <h2>LLM connectés</h2>
                  <span className={`panel-meta llm-pill is-${llmStatus.state}`}>{connLabel}</span>
                </header>
                <div className="settings-body">
                  <div className="table-wrap settings-llm-table-wrap">
                    <table className="settings-llm-table">
                      <thead>
                        <tr>
                          <th>Provider</th>
                          <th>Statut</th>
                          <th>Modèle</th>
                          <th>Clé</th>
                          <th>Source</th>
                          <th>Latence</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(connections.length
                          ? connections
                          : PROVIDERS.map((p) => ({
                              provider: p.id,
                              connected: p.id === savedProvider && hasActiveLlm,
                              keySource: (llmApiKeySet
                                ? 'ui'
                                : llmReady
                                  ? 'env'
                                  : 'none') as 'ui' | 'env' | 'both' | 'none',
                              active: p.id === savedProvider,
                              model: p.id === savedProvider ? savedModel : null,
                            }))
                        ).map((row) => {
                          const isActive = row.active
                          const rowState = isActive ? llmStatus.state : row.connected ? 'ok' : 'no_key'
                          const statusText = isActive
                            ? connLabel
                            : row.connected
                              ? 'Clé dispo'
                              : 'Non configuré'
                          const sourceLabel =
                            row.keySource === 'ui'
                              ? 'Clé UI'
                              : row.keySource === 'env'
                                ? '.env serveur'
                                : row.keySource === 'both'
                                  ? 'UI + .env'
                                  : '—'
                          return (
                            <tr key={row.provider} className={isActive ? 'is-active-llm' : undefined}>
                              <td>
                                {providerLabel(row.provider)}
                                {isActive ? ' · actif' : ''}
                              </td>
                              <td>
                                <span className={`llm-row-status is-${rowState}`}>
                                  <i className="llm-status-dot" aria-hidden />
                                  {statusText}
                                </span>
                              </td>
                              <td className="mono">{row.model ?? '—'}</td>
                              <td>{row.connected ? 'Configurée' : 'Absente'}</td>
                              <td>{sourceLabel}</td>
                              <td className="mono">
                                {isActive && llmStatus.latencyMs != null
                                  ? `${llmStatus.latencyMs} ms`
                                  : '—'}
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                  {hasActiveLlm ? (
                    <>
                      <p className="settings-hint muted">
                        OpenRouter / clés déjà en place : pas besoin de ressaisir pour utiliser le
                        Copilot. Change provider/clé seulement si tu veux basculer.
                      </p>
                      <div className="settings-llm-actions">
                        <button
                          type="button"
                          className="ghost"
                          disabled={testing || apiMissing}
                          onClick={() => void onTest()}
                        >
                          {testing ? 'Test…' : 'Retester l’actif'}
                        </button>
                        <button
                          type="button"
                          className={`ghost${showKeyForm ? ' is-active-ghost' : ''}`}
                          onClick={() => setShowKeyForm((v) => !v)}
                        >
                          {showKeyForm ? 'Masquer le formulaire' : 'Changer provider / clé'}
                        </button>
                      </div>
                    </>
                  ) : (
                    <>
                      <p className="settings-empty muted">
                        Aucune clé détectée (UI ni .env). Ajoute OpenRouter ci-dessous.
                      </p>
                      <button
                        type="button"
                        className="ghost settings-save"
                        onClick={() => setShowKeyForm(true)}
                      >
                        Configurer un LLM
                      </button>
                    </>
                  )}
                </div>
              </section>

              {(showKeyForm || !hasActiveLlm) && (
                <section className="panel settings-section">
                  <header className="panel-head">
                    <h2>{hasActiveLlm ? 'Remplacer le LLM' : 'Nouveau LLM'}</h2>
                    <span className="panel-meta">Provider · modèle · clé</span>
                  </header>
                  <div className="settings-body">
                    <div className="controls">
                      <label>
                        Provider
                        <select
                          value={llmProvider}
                          onChange={(e) => onProviderChange(e.target.value as LlmProvider)}
                        >
                          {PROVIDERS.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.label}
                            </option>
                          ))}
                        </select>
                      </label>

                      <label className="settings-grow">
                        Modèle
                        <select
                          value={modelSelect}
                          onChange={(e) => {
                            setModelSelect(e.target.value)
                            setTestResult(null)
                          }}
                        >
                          {modelOptions.map((m) => (
                            <option key={m.id} value={m.id}>
                              {m.label}
                            </option>
                          ))}
                          <option value="__custom__">Autre (ID custom)…</option>
                        </select>
                      </label>

                      {modelSelect === '__custom__' && (
                        <label className="settings-grow">
                          ID modèle
                          <input
                            type="text"
                            value={customModel}
                            onChange={(e) => setCustomModel(e.target.value)}
                            placeholder={DEFAULT_MODELS[llmProvider]}
                            required
                          />
                        </label>
                      )}

                      <label className="settings-grow">
                        {llmApiKeySet ? 'Nouvelle clé (optionnel)' : 'Clé API'}
                        <input
                          type="password"
                          value={llmApiKey}
                          onChange={(e) => {
                            setLlmApiKey(e.target.value)
                            setClearKey(false)
                            setTestResult(null)
                          }}
                          placeholder={
                            PROVIDERS.find((p) => p.id === llmProvider)?.keyHint ?? 'sk-…'
                          }
                          autoComplete="off"
                        />
                      </label>
                    </div>

                    {llmApiKeySet && (
                      <label className="settings-check settings-clear-key">
                        <input
                          type="checkbox"
                          checked={clearKey}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setPendingClearLlm(true)
                              return
                            }
                            setClearKey(false)
                          }}
                        />
                        Effacer la clé stockée en base
                      </label>
                    )}

                    <div className="settings-llm-actions">
                      <button
                        type="button"
                        className="ghost"
                        disabled={testing || apiMissing || !resolvedModel}
                        onClick={() => void onTest()}
                      >
                        {testing ? 'Test…' : 'Tester avant d’enregistrer'}
                      </button>
                      <button type="submit" className="ghost settings-save" disabled={saving || apiMissing}>
                        {saving ? 'Enregistrement…' : 'Enregistrer le LLM'}
                      </button>
                      <span className="muted settings-model-id mono">{resolvedModel || '—'}</span>
                    </div>
                  </div>
                </section>
              )}
            </>
  )
}
