import { type FormEvent, useEffect, useMemo, useState } from 'react'
import { ConfirmDialog } from '../components/ConfirmDialog'
import {
  invalidateEngineThresholdsCache,
  validateEngineThresholds,
  thresholdsFromVolume,
} from '../lib/engineThresholds'
import { llmStatusLabel, useLlmStatus } from '../lib/llmStatus'
import {
  DEFAULT_MODELS,
  getSettings,
  modelsForProvider,
  patchSettings,
  resolveModelSelection,
  type AppSettings,
  type LlmModelOption,
  type LlmProvider,
  type LlmTestResult,
} from '../lib/settings'
import { DEFAULT_ICHI, DEFAULT_VOL } from '../lib/types'

type SettingsSection = 'llm' | 'sources' | 'indicators'

const SECTIONS: { id: SettingsSection; label: string; blurb: string }[] = [
  { id: 'llm', label: 'Agent LLM', blurb: 'Provider, modèle, clé' },
  { id: 'sources', label: 'Feeds marché', blurb: 'Vision · Bybit · OKX (data only)' },
  { id: 'indicators', label: 'Indicateurs', blurb: 'Ichimoku · RVOL/ATR moteur' },
]

const SOURCES = [
  { id: 'binance', label: 'Binance Vision (data)' },
  { id: 'bybit', label: 'Bybit (data)' },
  { id: 'okx', label: 'OKX (data)' },
] as const

const PROVIDERS: { id: LlmProvider; label: string; keyHint: string }[] = [
  { id: 'openrouter', label: 'OpenRouter', keyHint: 'sk-or-…' },
  { id: 'anthropic', label: 'Anthropic', keyHint: 'sk-ant-…' },
  { id: 'openai', label: 'OpenAI', keyHint: 'sk-…' },
]

function providerLabel(id: LlmProvider): string {
  return PROVIDERS.find((p) => p.id === id)?.label ?? id
}

export function SettingsPage() {
  const llmStatus = useLlmStatus()
  const [section, setSection] = useState<SettingsSection>('llm')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [apiMissing, setApiMissing] = useState(false)
  const [testResult, setTestResult] = useState<LlmTestResult | null>(null)
  const [showKeyForm, setShowKeyForm] = useState(false)

  const [savedProvider, setSavedProvider] = useState<LlmProvider>('openrouter')
  const [savedModel, setSavedModel] = useState(DEFAULT_MODELS.openrouter)
  const [llmReady, setLlmReady] = useState(false)
  const [llmApiKeySet, setLlmApiKeySet] = useState(false)

  const [twelveDataApiKeySet, setTwelveDataApiKeySet] = useState(false)
  const [twelveDataApiKey, setTwelveDataApiKey] = useState('')
  const [clearTwelveDataKey, setClearTwelveDataKey] = useState(false)

  const [llmProvider, setLlmProvider] = useState<LlmProvider>('openrouter')
  const [modelSelect, setModelSelect] = useState(DEFAULT_MODELS.openrouter)
  const [customModel, setCustomModel] = useState('')
  const [llmApiKey, setLlmApiKey] = useState('')
  const [clearKey, setClearKey] = useState(false)
  const [pendingClearLlm, setPendingClearLlm] = useState(false)
  const [pendingClearTwelve, setPendingClearTwelve] = useState(false)
  const [catalog, setCatalog] = useState<Record<LlmProvider, LlmModelOption[]> | undefined>()
  const [connections, setConnections] = useState<
    NonNullable<AppSettings['llmConnections']>
  >([])

  const [activeSources, setActiveSources] = useState<string[]>(['binance'])
  const [theme, setTheme] = useState('dark')
  const [ichi, setIchi] = useState(DEFAULT_ICHI)
  const [vol, setVol] = useState(DEFAULT_VOL)

  const modelOptions = useMemo(
    () => modelsForProvider(llmProvider, catalog),
    [llmProvider, catalog],
  )

  const resolvedModel =
    modelSelect === '__custom__' ? customModel.trim() : modelSelect

  const hasActiveLlm = llmReady || llmApiKeySet || connections.some((c) => c.connected)

  useEffect(() => {
    let cancelled = false
    getSettings()
      .then((s) => {
        if (cancelled) return
        applySettings(s)
        setApiMissing(false)
        setShowKeyForm(!s.llmReady && !s.llmApiKeySet)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const msg = err instanceof Error ? err.message : 'Impossible de charger les paramètres'
        const looksMissing =
          /404|Failed to fetch|NetworkError|ECONNREFUSED/i.test(msg) || msg === 'Erreur 404'
        setError(msg)
        setApiMissing(looksMissing)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  function applySettings(s: AppSettings) {
    setSavedProvider(s.llmProvider)
    setSavedModel(s.llmModel)
    setLlmProvider(s.llmProvider)
    const sel = resolveModelSelection(s.llmProvider, s.llmModel)
    setModelSelect(sel.selectValue)
    setCustomModel(sel.custom)
    setLlmApiKeySet(s.llmApiKeySet)
    setLlmReady(s.llmReady)
    if (s.llmModels) setCatalog(s.llmModels)
    setConnections(s.llmConnections ?? [])
    setActiveSources(s.activeSources.length ? s.activeSources : ['binance'])
    setTheme(s.theme || 'dark')
    setIchi({ ...DEFAULT_ICHI, ...s.ichimokuParams })
    setVol({ ...DEFAULT_VOL, ...s.volumeParams })
    setLlmApiKey('')
    setClearKey(false)
    setTwelveDataApiKeySet(s.twelveDataApiKeySet)
    setTwelveDataApiKey('')
    setClearTwelveDataKey(false)
  }

  function onProviderChange(next: LlmProvider) {
    setLlmProvider(next)
    setModelSelect(DEFAULT_MODELS[next])
    setCustomModel('')
    setTestResult(null)
  }

  function toggleSource(id: string) {
    setActiveSources((prev) => {
      if (prev.includes(id)) {
        if (prev.length === 1) return prev
        return prev.filter((s) => s !== id)
      }
      return [...prev, id]
    })
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (section === 'llm' && !resolvedModel) {
      setError('Choisis un modèle dans la liste.')
      return
    }
    const thrErr = validateEngineThresholds(thresholdsFromVolume(vol))
    if (thrErr) {
      setError(thrErr)
      setSection('indicators')
      return
    }
    setSaving(true)
    setError(null)
    setSaved(false)
    try {
      // Keep chart client confirm in sync with engine significant bucket.
      const volumeParams = { ...vol, rvolConfirm: vol.rvolSignificant }
      const patch: Parameters<typeof patchSettings>[0] = {
        activeSources,
        theme,
        ichimokuParams: ichi,
        volumeParams,
      }
      if (section === 'llm') {
        patch.llmProvider = llmProvider
        patch.llmModel = resolvedModel
        if (clearKey) patch.llmApiKey = ''
        else if (llmApiKey.trim()) patch.llmApiKey = llmApiKey.trim()
      }
      if (section === 'sources') {
        if (clearTwelveDataKey) patch.twelveDataApiKey = ''
        else if (twelveDataApiKey.trim()) patch.twelveDataApiKey = twelveDataApiKey.trim()
      }

      const next = await patchSettings(patch)
      invalidateEngineThresholdsCache()
      applySettings(next)
      setSaved(true)
      setApiMissing(false)
      setShowKeyForm(false)
      if (section === 'llm') {
        const result = await llmStatus.refresh({
          provider: llmProvider,
          model: resolvedModel,
          apiKey: llmApiKey.trim() || undefined,
        })
        setTestResult(result)
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Échec de la sauvegarde')
    } finally {
      setSaving(false)
    }
  }

  async function onTest() {
    if (!resolvedModel) {
      setError('Choisis un modèle avant de tester.')
      return
    }
    setTesting(true)
    setError(null)
    setTestResult(null)
    try {
      const result = await llmStatus.refresh({
        provider: showKeyForm ? llmProvider : savedProvider,
        model: showKeyForm ? resolvedModel : savedModel,
        apiKey: llmApiKey.trim() || undefined,
      })
      setTestResult(result)
      if (result && !result.ok) setError(result.message)
    } finally {
      setTesting(false)
    }
  }

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

  const connLabel = llmStatusLabel(llmStatus.state)

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
        <header className="page-head">
          <h1>{SECTIONS.find((s) => s.id === section)?.label}</h1>
      <p className="muted">
            {section === 'llm'
              ? 'LLM actif en haut. Ajoute ou remplace la clé seulement si tu changes de provider.'
              : section === 'sources'
                ? 'Données publiques — aucune clé exchange requise.'
                : 'Seuils Ichimoku / RVOL persistés pour le cockpit.'}
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

        <form className="settings-form" onSubmit={onSubmit}>
          {section === 'llm' && (
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
          )}

          {section === 'sources' && (
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
          )}

          {section === 'sources' && (
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
          )}

          {section === 'indicators' && (
            <section className="panel settings-section">
              <header className="panel-head">
                <h2>Ichimoku · RVOL · thème</h2>
              </header>
              <div className="settings-body controls">
                <label>
                  Tenkan
                  <input
                    type="number"
                    min={1}
                    value={ichi.tenkan}
                    onChange={(e) => setIchi((v) => ({ ...v, tenkan: Number(e.target.value) }))}
                  />
                </label>
                <label>
                  Kijun
                  <input
                    type="number"
                    min={1}
                    value={ichi.kijun}
                    onChange={(e) => setIchi((v) => ({ ...v, kijun: Number(e.target.value) }))}
                  />
                </label>
                <label>
                  Senkou B
                  <input
                    type="number"
                    min={1}
                    value={ichi.senkouB}
                    onChange={(e) => setIchi((v) => ({ ...v, senkouB: Number(e.target.value) }))}
                  />
                </label>
                <label>
                  Displacement
                  <input
                    type="number"
                    min={1}
                    value={ichi.displacement}
                    onChange={(e) =>
                      setIchi((v) => ({ ...v, displacement: Number(e.target.value) }))
                    }
                  />
                </label>
                <label>
                  RVOL len (chart)
                  <input
                    type="number"
                    min={1}
                    value={vol.rvolLen}
                    onChange={(e) => setVol((v) => ({ ...v, rvolLen: Number(e.target.value) }))}
                  />
                </label>
                <label>
                  Spike × (chart)
                  <input
                    type="number"
                    min={0}
                    step={0.1}
                    value={vol.spikeMult}
                    onChange={(e) => setVol((v) => ({ ...v, spikeMult: Number(e.target.value) }))}
                  />
                </label>
                <label>
                  Thème
                  <select value={theme} onChange={(e) => setTheme(e.target.value)}>
                    <option value="dark">Dark</option>
                    <option value="light">Light</option>
                  </select>
                </label>
              </div>

              <p className="muted settings-engine-note">
                Seuils moteur (envoyés à /decisions, /screener, /backtest). Ordre RVOL : low &lt;
                significant &lt; strong &lt; anomaly. ATR : 0 ≤ dead &lt; extreme ≤ 1.
              </p>
              <div className="settings-grid">
                <label>
                  RVOL low
                  <input
                    type="number"
                    min={0}
                    step={0.05}
                    value={vol.rvolLow}
                    onChange={(e) => setVol((v) => ({ ...v, rvolLow: Number(e.target.value) }))}
                  />
                </label>
                <label>
                  RVOL significant
                  <input
                    type="number"
                    min={0}
                    step={0.05}
                    value={vol.rvolSignificant}
                    onChange={(e) =>
                      setVol((v) => ({
                        ...v,
                        rvolSignificant: Number(e.target.value),
                        rvolConfirm: Number(e.target.value),
                      }))
                    }
                  />
                </label>
                <label>
                  RVOL strong
                  <input
                    type="number"
                    min={0}
                    step={0.05}
                    value={vol.rvolStrong}
                    onChange={(e) => setVol((v) => ({ ...v, rvolStrong: Number(e.target.value) }))}
                  />
                </label>
                <label>
                  RVOL anomaly
                  <input
                    type="number"
                    min={0}
                    step={0.05}
                    value={vol.rvolAnomaly}
                    onChange={(e) => setVol((v) => ({ ...v, rvolAnomaly: Number(e.target.value) }))}
                  />
                </label>
                <label>
                  ATR dead %ile
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.01}
                    value={vol.atrDeadPercentile}
                    onChange={(e) =>
                      setVol((v) => ({ ...v, atrDeadPercentile: Number(e.target.value) }))
                    }
                  />
                </label>
                <label>
                  ATR extreme %ile
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.01}
                    value={vol.atrExtremePercentile}
                    onChange={(e) =>
                      setVol((v) => ({ ...v, atrExtremePercentile: Number(e.target.value) }))
                    }
                  />
                </label>
                <label>
                  ATR stop ×
                  <input
                    type="number"
                    min={0.1}
                    step={0.1}
                    value={vol.atrStopMultiplier}
                    onChange={(e) =>
                      setVol((v) => ({ ...v, atrStopMultiplier: Number(e.target.value) }))
                    }
                  />
                </label>
              </div>
              <div className="settings-body">
                <button type="submit" className="ghost settings-save" disabled={saving || apiMissing}>
                  {saving ? 'Enregistrement…' : 'Enregistrer'}
                </button>
              </div>
            </section>
          )}
        </form>
      </div>

      {pendingClearLlm && (
        <ConfirmDialog
          title="Effacer la clé LLM ?"
          body="La clé stockée en base sera supprimée à l’enregistrement. Irréversible tant que tu n’en resaisis pas une nouvelle."
          confirmLabel="Effacer"
          danger
          onConfirm={() => {
            setClearKey(true)
            setLlmApiKey('')
            setPendingClearLlm(false)
          }}
          onCancel={() => setPendingClearLlm(false)}
        />
      )}

      {pendingClearTwelve && (
        <ConfirmDialog
          title="Effacer la clé Twelve Data ?"
          body="Ta clé perso sera retirée à l’enregistrement — retour à la clé opérateur si configurée."
          confirmLabel="Effacer"
          danger
          onConfirm={() => {
            setClearTwelveDataKey(true)
            setTwelveDataApiKey('')
            setPendingClearTwelve(false)
          }}
          onCancel={() => setPendingClearTwelve(false)}
        />
      )}
    </div>
  )
}
