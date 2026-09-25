import { type FormEvent, useEffect, useMemo, useState } from 'react'
import { getMe, type AuthUser } from '../../lib/auth'
import {
  invalidateEngineThresholdsCache,
  validateEngineThresholds,
  thresholdsFromVolume,
} from '../../lib/engineThresholds'
import { useLlmStatus } from '../../lib/llmStatus'
import { getPaperOverview, type PaperOverview } from '../../lib/paper'
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
} from '../../lib/settings'
import { DEFAULT_ICHI, DEFAULT_VOL } from '../../lib/types'
import { getEngineUniverse, type EngineUniverse } from '../../lib/universe'
import type { SettingsSection } from './settingsConstants'

export function useSettingsController() {
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
  const [pushPrefs, setPushPrefs] = useState({
    enabled: false,
    targetStop: true,
    accel: true,
    directionFlip: true,
    nearPct: 0.2,
    cooldownMin: 30,
  })
  const [pushStatusMsg, setPushStatusMsg] = useState<string | null>(null)
  const [pushBusy, setPushBusy] = useState(false)
  const [universe, setUniverse] = useState<EngineUniverse | null>(null)
  const [universeError, setUniverseError] = useState<string | null>(null)
  const [risk, setRisk] = useState<PaperOverview['risk'] | null>(null)
  const [riskError, setRiskError] = useState<string | null>(null)
  const [identity, setIdentity] = useState<AuthUser | null>(null)

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

    getEngineUniverse()
      .then((u) => {
        if (!cancelled) {
          setUniverse(u)
          setUniverseError(null)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setUniverse(null)
          setUniverseError(err instanceof Error ? err.message : 'Univers indisponible')
        }
      })

    getPaperOverview()
      .then((ov) => {
        if (!cancelled) {
          setRisk(ov.risk ?? null)
          setRiskError(ov.risk ? null : 'Risk Kernel absent de l’overview.')
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setRisk(null)
          setRiskError(err instanceof Error ? err.message : 'Limites de risque indisponibles')
        }
      })

    getMe()
      .then((user) => {
        if (!cancelled) setIdentity(user)
      })
      .catch(() => {
        if (!cancelled) setIdentity(null)
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
    if (s.pushAlertPrefs) {
      setPushPrefs({
        enabled: Boolean(s.pushAlertPrefs.enabled),
        targetStop: s.pushAlertPrefs.targetStop !== false,
        accel: s.pushAlertPrefs.accel !== false,
        directionFlip: s.pushAlertPrefs.directionFlip !== false,
        nearPct: s.pushAlertPrefs.nearPct ?? 0.2,
        cooldownMin: s.pushAlertPrefs.cooldownMin ?? 30,
      })
    }
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
      setSection('market')
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
      if (section === 'connections') {
        if (clearTwelveDataKey) patch.twelveDataApiKey = ''
        else if (twelveDataApiKey.trim()) patch.twelveDataApiKey = twelveDataApiKey.trim()
      }
      if (section === 'alerts') {
        patch.pushAlertPrefs = { ...pushPrefs }
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

  return {
    llmStatus,
    section,
    setSection,
    loading,
    setLoading,
    saving,
    setSaving,
    testing,
    setTesting,
    error,
    setError,
    saved,
    setSaved,
    apiMissing,
    setApiMissing,
    testResult,
    setTestResult,
    showKeyForm,
    setShowKeyForm,
    savedProvider,
    setSavedProvider,
    savedModel,
    setSavedModel,
    llmReady,
    setLlmReady,
    llmApiKeySet,
    setLlmApiKeySet,
    twelveDataApiKeySet,
    setTwelveDataApiKeySet,
    twelveDataApiKey,
    setTwelveDataApiKey,
    clearTwelveDataKey,
    setClearTwelveDataKey,
    llmProvider,
    setLlmProvider,
    modelSelect,
    setModelSelect,
    customModel,
    setCustomModel,
    llmApiKey,
    setLlmApiKey,
    clearKey,
    setClearKey,
    pendingClearLlm,
    setPendingClearLlm,
    pendingClearTwelve,
    setPendingClearTwelve,
    catalog,
    setCatalog,
    connections,
    setConnections,
    activeSources,
    setActiveSources,
    theme,
    setTheme,
    ichi,
    setIchi,
    vol,
    setVol,
    pushPrefs,
    setPushPrefs,
    pushStatusMsg,
    setPushStatusMsg,
    pushBusy,
    setPushBusy,
    universe,
    setUniverse,
    universeError,
    setUniverseError,
    risk,
    setRisk,
    riskError,
    setRiskError,
    identity,
    setIdentity,
    modelOptions,
    resolvedModel,
    hasActiveLlm,
    applySettings,
    onProviderChange,
    toggleSource,
    onSubmit,
    onTest,
  }
}
