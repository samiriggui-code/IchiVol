/**
 * Paramètres — port littéral de design-reference/ichivol-workspace `parametres()` + page-head.
 * Classes HTML = maquette. Préférences locales + écritures engine (patchSettings / push).
 */

import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { type PaperOverview } from '../lib/paper'
import { loadAllBooks } from '../lib/allBooks'
import { disablePushAlerts, enablePushAlerts } from '../lib/pushAlerts'
import {
  DEFAULT_MODELS,
  getSettings,
  modelsForProvider,
  patchSettings,
  testLlm,
  type AppSettings,
  type LlmProvider,
  type LlmTestResult,
} from '../lib/settings'
import {
  getEveSettingsSchema,
  getEveSettingsValues,
  patchEveSettingsValues,
  sortedSchemaGroups,
  type EveSettingItem,
  type EveSettingGroup,
} from '../lib/eveSettings'
import { invalidateEngineThresholdsCache } from '../lib/engineThresholds'
import { llmStatusLabel, useLlmStatus } from '../lib/llmStatus'
import type { LlmConnection } from '../lib/settings'
import './SettingsPage.css'

type SettingsTab =
  | 'Marché et univers'
  | 'LLM'
  | 'Ève / JEV'
  | 'Alertes'
  | 'Limites de risque'
  | 'Connexions'

type BadgeTone = 'green' | 'amber' | 'red' | 'gray' | ''

const TABS: SettingsTab[] = [
  'Marché et univers',
  'LLM',
  'Ève / JEV',
  'Alertes',
  'Limites de risque',
  'Connexions',
]

const LS_KEY = 'ichivol-settings'

const PROVIDERS: { id: LlmProvider; label: string; keyHint: string }[] = [
  { id: 'openrouter', label: 'OpenRouter', keyHint: 'sk-or-…' },
  { id: 'anthropic', label: 'Anthropic', keyHint: 'sk-ant-…' },
  { id: 'openai', label: 'OpenAI', keyHint: 'sk-…' },
]

function providerLabel(id: LlmProvider): string {
  return PROVIDERS.find((p) => p.id === id)?.label ?? id
}

function sourceLabel(source: LlmConnection['keySource']): string {
  switch (source) {
    case 'ui':
      return 'Clé enregistrée'
    case 'env':
      return '.env serveur'
    case 'both':
      return 'UI + .env'
    case 'none':
      return '—'
    default: {
      const _exhaustive: never = source
      return _exhaustive
    }
  }
}

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
  const llmLive = useLlmStatus()
  const [settingsTab, setSettingsTab] = useState<SettingsTab>('LLM')
  const [local, setLocal] = useState(loadLocal)
  const [engine, setEngine] = useState<AppSettings | null>(null)
  const [saved, setSaved] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pushBusy, setPushBusy] = useState(false)
  const [pushMsg, setPushMsg] = useState<string | null>(null)
  const [llmProvider, setLlmProvider] = useState<LlmProvider>('openrouter')
  const [llmModel, setLlmModel] = useState(DEFAULT_MODELS.openrouter)
  const [llmApiKey, setLlmApiKey] = useState('')
  const [clearKey, setClearKey] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<LlmTestResult | null>(null)
  const [rowTests, setRowTests] = useState<Partial<Record<LlmProvider, LlmTestResult>>>({})
  const [rowTesting, setRowTesting] = useState<LlmProvider | null>(null)
  const [rvol, setRvol] = useState('1.5')
  const [tenkan, setTenkan] = useState('9')
  const [kijun, setKijun] = useState('26')
  const [senkouB, setSenkouB] = useState('52')
  const [sources, setSources] = useState<string[]>(['binance'])
  const [alertPrefs, setAlertPrefs] = useState({
    targetStop: true,
    accel: true,
    directionFlip: true,
  })
  /** Plafonds de risque de chaque portefeuille paper actif. */
  const [bookRisks, setBookRisks] = useState<Array<{ code: string; label: string; risk: PaperOverview['risk'] | null }>>([])
  const [eveSchema, setEveSchema] = useState<Record<string, EveSettingGroup> | null>(null)
  const [eveValues, setEveValues] = useState<Record<string, string | number | boolean>>({})
  const [eveDraft, setEveDraft] = useState<Record<string, string | number | boolean>>({})
  const [eveAdvanced, setEveAdvanced] = useState(false)
  const [eveLoaded, setEveLoaded] = useState(false)

  useEffect(() => {
    getSettings()
      .then((s) => {
        setEngine(s)
        setLlmProvider(s.llmProvider)
        setLlmModel(s.llmModel || DEFAULT_MODELS[s.llmProvider])
        setRvol(String(s.volumeParams?.rvolConfirm ?? 1.5))
        setTenkan(String(s.ichimokuParams?.tenkan ?? 9))
        setKijun(String(s.ichimokuParams?.kijun ?? 26))
        setSenkouB(String(s.ichimokuParams?.senkouB ?? 52))
        setSources(s.activeSources?.length ? s.activeSources : ['binance'])
        setAlertPrefs({
          targetStop: s.pushAlertPrefs?.targetStop ?? true,
          accel: s.pushAlertPrefs?.accel ?? true,
          directionFlip: s.pushAlertPrefs?.directionFlip ?? true,
        })
      })
      .catch(() => setEngine(null))
    loadAllBooks()
      .then((books) => setBookRisks(books.map((b) => ({ code: b.code, label: b.label, risk: b.overview.risk ?? null }))))
      .catch(() => setBookRisks([]))
    Promise.all([getEveSettingsSchema(), getEveSettingsValues()])
      .then(([schemaRes, valuesRes]) => {
        setEveSchema(schemaRes.schema)
        setEveValues(valuesRes.values)
        setEveDraft(valuesRes.values)
        setEveLoaded(true)
      })
      .catch(() => {
        setEveSchema(null)
        setEveLoaded(false)
      })
  }, [])

  const onSave = useCallback(
    async (e: FormEvent<HTMLFormElement>) => {
      e.preventDefault()
      const fd = new FormData(e.currentTarget)
      const next: Record<string, string> = { ...local }
      fd.forEach((v, k) => {
        if (k === 'llmApiKey') return
        if (typeof v === 'string') next[k] = v
      })
      for (let i = 0; i < 4; i++) {
        next[`alert${i}`] = fd.get(`alert${i}`) ? '1' : '0'
      }
      try {
        localStorage.setItem(LS_KEY, JSON.stringify(next))
        setLocal(next)
      } catch {
        /* ignore quota */
      }

      setSaving(true)
      setError(null)
      setSaved(false)
      try {
        const patch: Parameters<typeof patchSettings>[0] = {}
        if (settingsTab === 'Marché et univers' && engine) {
          const rvolN = Number(rvol)
          const tenkanN = Number(tenkan)
          const kijunN = Number(kijun)
          const senkouN = Number(senkouB)
          if (!Number.isFinite(rvolN) || rvolN <= 0) {
            throw new Error('Seuil RVOL invalide')
          }
          if (![tenkanN, kijunN, senkouN].every((n) => Number.isFinite(n) && n > 0)) {
            throw new Error('Paramètres Ichimoku invalides')
          }
          if (sources.length === 0) throw new Error('Au moins une source de données')
          patch.activeSources = sources
          patch.volumeParams = {
            ...engine.volumeParams,
            rvolConfirm: rvolN,
            rvolSignificant: rvolN,
          }
          patch.ichimokuParams = {
            ...engine.ichimokuParams,
            tenkan: tenkanN,
            kijun: kijunN,
            senkouB: senkouN,
          }
        }
        if (settingsTab === 'LLM' && engine) {
          patch.llmProvider = llmProvider
          patch.llmModel = llmModel || DEFAULT_MODELS[llmProvider]
          if (clearKey) patch.llmApiKey = ''
          else if (llmApiKey.trim()) patch.llmApiKey = llmApiKey.trim()
        }
        if (settingsTab === 'Alertes') {
          patch.pushAlertPrefs = {
            enabled: engine?.pushAlertPrefs?.enabled ?? false,
            targetStop: alertPrefs.targetStop,
            accel: alertPrefs.accel,
            directionFlip: alertPrefs.directionFlip,
            nearPct: engine?.pushAlertPrefs?.nearPct ?? 0.5,
            cooldownMin: engine?.pushAlertPrefs?.cooldownMin ?? 30,
          }
        }
        if (settingsTab === 'Ève / JEV') {
          if (!eveSchema) {
            throw new Error('Schéma Ève / JEV indisponible (moteur ?)')
          }
          const writablePatch: Record<string, string | number | boolean> = {}
          for (const [, group] of sortedSchemaGroups(eveSchema)) {
            for (const item of group.items) {
              if (!item.writable) continue
              const next = eveDraft[item.key]
              const prev = eveValues[item.key]
              if (next !== undefined && next !== prev) {
                writablePatch[item.key] = next
              }
            }
          }
          if (Object.keys(writablePatch).length === 0) {
            setError('Aucun knob Ève / JEV modifié (ou champs en lecture seule).')
            return
          }
          const saved = await patchEveSettingsValues(writablePatch)
          setEveValues(saved.values)
          setEveDraft(saved.values)
          setSaved(true)
          window.setTimeout(() => setSaved(false), 1500)
          return
        }
        if (Object.keys(patch).length === 0) {
          if (settingsTab === 'Limites de risque' || settingsTab === 'Connexions') {
            setError(
              'Ces valeurs viennent du profil paper ou de l’état du moteur. Ce formulaire ne les réécrit pas.',
            )
          }
          return
        }
        const updated = await patchSettings(patch)
        setEngine(updated)
        invalidateEngineThresholdsCache()
        setLlmApiKey('')
        setClearKey(false)
        if (settingsTab === 'LLM') void llmLive.refresh()
        setSaved(true)
        window.setTimeout(() => setSaved(false), 1500)
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Échec de la sauvegarde moteur')
      } finally {
        setSaving(false)
      }
    },
    [
      local,
      settingsTab,
      engine,
      llmProvider,
      llmModel,
      llmApiKey,
      clearKey,
      llmLive,
      rvol,
      tenkan,
      kijun,
      senkouB,
      sources,
      alertPrefs,
      eveSchema,
      eveDraft,
      eveValues,
    ],
  )

  function renderEveField(item: EveSettingItem): ReactNode {
    const value = eveDraft[item.key]
    const disabled = !item.writable || Boolean(item.read_only)
    const label = item.is_advanced ? `${item.label} · avancé` : item.label
    if (item.type === 'boolean') {
      return (
        <label key={item.key} className="checkrow">
          <span className="check-copy">
            {label}
            {item.description ? <small>{item.description}</small> : null}
          </span>
          <input
            type="checkbox"
            checked={Boolean(value)}
            disabled={disabled}
            onChange={(e) =>
              setEveDraft((prev) => ({ ...prev, [item.key]: e.target.checked }))
            }
          />
        </label>
      )
    }
    if (item.type === 'number') {
      return (
        <div className="field" key={item.key}>
          <label htmlFor={`eve-${item.key}`}>{label}</label>
          <input
            id={`eve-${item.key}`}
            type="number"
            step="any"
            disabled={disabled}
            value={value === undefined || value === null ? '' : String(value)}
            onChange={(e) => {
              const n = Number(e.target.value)
              setEveDraft((prev) => ({
                ...prev,
                [item.key]: Number.isFinite(n) ? n : e.target.value,
              }))
            }}
          />
          {item.description ? <small>{item.description}</small> : null}
        </div>
      )
    }
    return (
      <div className="field" key={item.key}>
        <label htmlFor={`eve-${item.key}`}>{label}</label>
        <input
          id={`eve-${item.key}`}
          type={item.type === 'password' ? 'password' : 'text'}
          disabled={disabled}
          value={value === undefined || value === null ? '' : String(value)}
          onChange={(e) =>
            setEveDraft((prev) => ({ ...prev, [item.key]: e.target.value }))
          }
          readOnly={disabled}
        />
        {item.description ? <small>{item.description}</small> : null}
      </div>
    )
  }

  const saveHint =
    settingsTab === 'Limites de risque'
      ? 'Lecture seule — plafonds du profil paper ICHIVOL_BASELINE_V1.'
      : settingsTab === 'Ève / JEV'
        ? 'Knobs Ève écrits sur le moteur. Secrets JEV / TypeSafe restent en .env.'
        : settingsTab === 'Connexions'
          ? 'Statut lecture seule — rien à enregistrer ici.'
          : 'Marché, alertes et LLM sont écrits sur votre compte.'

  const llmRows: LlmConnection[] =
    engine?.llmConnections && engine.llmConnections.length > 0
      ? engine.llmConnections
      : PROVIDERS.map((p) => ({
          provider: p.id,
          connected: p.id === engine?.llmProvider && Boolean(engine?.llmReady || engine?.llmApiKeySet),
          keySource:
            p.id === engine?.llmProvider
              ? engine?.llmApiKeySet
                ? 'ui'
                : engine?.llmReady
                  ? 'env'
                  : 'none'
              : 'none',
          active: p.id === engine?.llmProvider,
          model: p.id === engine?.llmProvider ? engine?.llmModel ?? null : null,
        }))

  async function probeProvider(provider: LlmProvider, model: string | null) {
    const modelId =
      model && model !== '—' ? model : DEFAULT_MODELS[provider]
    const apiKey = provider === llmProvider && llmApiKey.trim() ? llmApiKey.trim() : undefined
    setRowTesting(provider)
    setTesting(true)
    setTestResult(null)
    setError(null)
    try {
      const result = await testLlm({ provider, model: modelId, apiKey })
      setRowTests((prev) => ({ ...prev, [provider]: result }))
      setTestResult(result)
      if (!engine || provider === engine.llmProvider) {
        await llmLive.refresh({ provider, model: modelId, apiKey })
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Test LLM échoué')
    } finally {
      setTesting(false)
      setRowTesting(null)
    }
  }

  const eveAutonomy = Boolean(eveValues.EVE_PAPER_AUTONOMY)
  const eveRadar = Boolean(eveValues.EVENT_RADAR_ENABLED)
  const showSave =
    settingsTab !== 'Limites de risque' && settingsTab !== 'Connexions'

  return (
    <div className="params-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">IchiVol · Desk</div>
          <h1>Paramètres</h1>
          <p className="subtitle">LLM, Ève / JEV API, marché, alertes — paper only.</p>
        </div>
        <div className="actions">
          {badge(engine ? 'MOTEUR OK' : 'MOTEUR OFF', engine ? 'green' : 'red')}
          {badge(eveAutonomy ? 'ÈVE AUTO ON' : 'ÈVE DRY-RUN', eveAutonomy ? 'green' : 'amber')}
        </div>
      </div>

      <div className="tabs" role="tablist" aria-label="Sections paramètres">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={settingsTab === t}
            className={settingsTab === t ? 'active' : ''}
            onClick={() => setSettingsTab(t)}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="params-layout">
        <section className="card">
          <div className="card-head">
            <h2>{settingsTab}</h2>
          </div>
          <form id="settings-form" className="card-body" onSubmit={(ev) => void onSave(ev)}>
            {settingsTab === 'Limites de risque' && (
              <>
                <p className="lede">
                  Plafonds de chaque portefeuille paper, en lecture seule. Le Risk Kernel ne se
                  configure pas depuis le navigateur.
                </p>
                {bookRisks.length === 0 ? (
                  <div className="statline">
                    <span>Portefeuilles</span>
                    <b>—</b>
                  </div>
                ) : (
                  bookRisks.map((b) => (
                    <div key={b.code} style={{ marginBottom: 14 }}>
                      <h3 style={{ fontSize: 13, margin: '8px 0 4px' }}>{b.label}</h3>
                      <div className="statline">
                        <span>Risque ouvert max</span>
                        <b>
                          {b.risk?.max_open_risk_pct != null
                            ? `${(b.risk.max_open_risk_pct * 100).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} %`
                            : '—'}
                        </b>
                      </div>
                      <div className="statline">
                        <span>Positions simultanées max</span>
                        <b>{b.risk?.max_open_positions ?? '—'}</b>
                      </div>
                      <div className="statline">
                        <span>Positions ouvertes</span>
                        <b>{b.risk?.open_positions ?? '—'}</b>
                      </div>
                    </div>
                  ))
                )}
              </>
            )}

            {settingsTab === 'Marché et univers' && (
              <>
                <p className="lede">Sources et paramètres Ichimoku × RVOL du moteur.</p>
                <div className="field">
                  <span className="label">Sources de données</span>
                  {(
                    [
                      ['binance', 'Binance'],
                      ['bybit', 'Bybit'],
                      ['okx', 'OKX'],
                    ] as const
                  ).map(([id, label]) => (
                    <label className="checkrow" key={id}>
                      <span className="check-copy">{label}</span>
                      <input
                        type="checkbox"
                        checked={sources.includes(id)}
                        onChange={(ev) => {
                          setSources((prev) =>
                            ev.target.checked
                              ? [...prev, id]
                              : prev.filter((s) => s !== id),
                          )
                        }}
                      />
                    </label>
                  ))}
                  <small>Enregistré sur le compte (activeSources).</small>
                </div>
                <div className="field">
                  <label htmlFor="rvol">Seuil RVOL</label>
                  <input
                    id="rvol"
                    name="rvol"
                    type="number"
                    min="0.1"
                    step="0.1"
                    value={rvol}
                    onChange={(ev) => setRvol(ev.target.value)}
                  />
                </div>
                <div className="field-row">
                  {(
                    [
                      ['tenkan', 'Tenkan', tenkan, setTenkan],
                      ['kijun', 'Kijun', kijun, setKijun],
                      ['senkou', 'Senkou B', senkouB, setSenkouB],
                    ] as const
                  ).map(([id, label, value, setValue]) => (
                    <div className="field" key={id}>
                      <label htmlFor={id}>{label}</label>
                      <input
                        id={id}
                        type="number"
                        min="1"
                        step="1"
                        value={value}
                        onChange={(ev) => setValue(ev.target.value)}
                      />
                    </div>
                  ))}
                </div>
              </>
            )}

            {settingsTab === 'LLM' && (
              <>
                <p className="lede">
                  Copilot / chat. Distinct de JEV API / System One — onglet Ève / JEV.
                </p>
                <div className="field">
                  <label htmlFor="llmProvider">Provider</label>
                  <select
                    id="llmProvider"
                    name="llmProvider"
                    value={llmProvider}
                    disabled={!engine}
                    onChange={(ev) => {
                      const next = ev.target.value as LlmProvider
                      setLlmProvider(next)
                      const models = modelsForProvider(next, engine?.llmModels)
                      setLlmModel(
                        models.some((m) => m.id === llmModel) ? llmModel : DEFAULT_MODELS[next],
                      )
                      setTestResult(null)
                    }}
                  >
                    {PROVIDERS.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.label}
                      </option>
                    ))}
                  </select>
                  <small>OpenRouter par défaut (une clé, plusieurs modèles).</small>
                </div>
                <div className="field">
                  <label htmlFor="llmModel">Modèle</label>
                  <select
                    id="llmModel"
                    name="llmModel"
                    value={llmModel}
                    disabled={!engine}
                    onChange={(ev) => setLlmModel(ev.target.value)}
                  >
                    {modelsForProvider(llmProvider, engine?.llmModels).map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.label}
                      </option>
                    ))}
                    {llmModel &&
                    !modelsForProvider(llmProvider, engine?.llmModels).some((m) => m.id === llmModel) ? (
                      <option value={llmModel}>{llmModel}</option>
                    ) : null}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="llmApiKey">
                    {engine?.llmApiKeySet ? 'Nouvelle clé (optionnel)' : 'Clé API'}
                  </label>
                  <input
                    id="llmApiKey"
                    name="llmApiKey"
                    type="password"
                    autoComplete="off"
                    value={llmApiKey}
                    placeholder={PROVIDERS.find((p) => p.id === llmProvider)?.keyHint ?? 'sk-…'}
                    onChange={(ev) => setLlmApiKey(ev.target.value)}
                    disabled={!engine}
                  />
                  <small>
                    {engine
                      ? `${engine.llmProvider}${engine.llmApiKeySet ? ' · clé OK' : ' · pas de clé UI'}${engine.llmReady ? ' · prêt' : ' · non prêt'}. Vide = garder la clé.`
                      : 'Moteur indisponible.'}
                  </small>
                </div>
                {engine?.llmApiKeySet && (
                  <label className="checkrow">
                    <span className="check-copy">Effacer la clé enregistrée</span>
                    <input
                      type="checkbox"
                      checked={clearKey}
                      onChange={(ev) => setClearKey(ev.target.checked)}
                    />
                  </label>
                )}
                <div className="btn-row">
                  <button
                    type="button"
                    className="suggestion"
                    disabled={!engine || testing}
                    onClick={() => {
                      void probeProvider(llmProvider, llmModel)
                    }}
                  >
                    {testing ? 'Test…' : 'Tester la connexion'}
                  </button>
                </div>
                {testResult && (
                  <div className={`notice ${testResult.ok ? 'ok' : 'err'}`} role="status">
                    {testResult.ok ? 'Connecté' : 'Échec'} · {providerLabel(testResult.provider)} ·{' '}
                    {testResult.model} · {testResult.message}
                    {testResult.latencyMs ? ` · ${testResult.latencyMs} ms` : ''}
                  </div>
                )}

                <h3 className="section-title">Providers enregistrés</h3>
                <p className="hint">
                  « Connecté » = dernier test OK. Distinct de JEV API / System One.
                </p>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>PROVIDER</th>
                        <th>STATUT</th>
                        <th>MODÈLE</th>
                        <th>CLÉ</th>
                        <th>SOURCE</th>
                        <th>LATENCE</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {llmRows.map((row) => {
                        const tested = rowTests[row.provider]
                        const live =
                          llmLive.provider === row.provider && row.active ? llmLive : null
                        const checking =
                          rowTesting === row.provider || (row.active && llmLive.state === 'checking')
                        let status = 'Non configuré'
                        let tone: BadgeTone = 'gray'
                        if (checking) {
                          status = 'Test…'
                          tone = 'amber'
                        } else if (tested?.ok || live?.state === 'ok') {
                          status = row.active ? 'Connecté · actif' : 'Connecté'
                          tone = 'green'
                        } else if (tested && !tested.ok) {
                          status = tested.status === 'bad_key' ? 'Clé refusée' : 'Échec test'
                          tone = 'red'
                        } else if (live && live.state !== 'idle') {
                          status = llmStatusLabel(live.state)
                          tone = 'red'
                        } else if (row.connected) {
                          status = row.active ? 'Enregistré · actif' : 'Clé enregistrée'
                          tone = 'amber'
                        }
                        const latency =
                          tested?.latencyMs ??
                          (live?.state === 'ok' ? live.latencyMs : undefined)
                        const modelShown =
                          (row.provider === llmProvider ? llmModel : row.model) || '—'
                        return (
                          <tr key={row.provider}>
                            <td>
                              <b>{providerLabel(row.provider)}</b>
                              {row.active ? <small>actif</small> : null}
                            </td>
                            <td>{badge(status, tone)}</td>
                            <td>{modelShown}</td>
                            <td>{row.connected ? 'OK' : '—'}</td>
                            <td>{sourceLabel(row.keySource)}</td>
                            <td>{latency != null ? `${latency} ms` : '—'}</td>
                            <td>
                              <button
                                type="button"
                                className="suggestion"
                                disabled={checking || !engine}
                                onClick={() => void probeProvider(row.provider, modelShown)}
                              >
                                Tester
                              </button>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </>
            )}

            {settingsTab === 'Ève / JEV' && (
              <>
                <p className="lede">
                  Knobs moteur pour les 4 modes Ève. Secrets{' '}
                  <code>JEV_*</code> / <code>TYPESAFE_*</code> uniquement en <code>.env</code> —
                  jamais via l’UI.
                </p>
                <label className="toggle-row">
                  <input
                    id="eve-advanced"
                    type="checkbox"
                    checked={eveAdvanced}
                    onChange={(e) => setEveAdvanced(e.target.checked)}
                  />
                  Afficher les knobs avancés
                </label>
                {!eveLoaded || !eveSchema ? (
                  <p className="hint">
                    Schéma indisponible — démarre le moteur Python (
                    <code>/api/engine/eve/settings/schema</code>).
                  </p>
                ) : (
                  sortedSchemaGroups(eveSchema).map(([groupKey, group]) => {
                    const items = group.items.filter(
                      (item) => eveAdvanced || !item.is_advanced,
                    )
                    if (items.length === 0) return null
                    return (
                      <div key={groupKey} className="eve-group">
                        <h3>{group.title}</h3>
                        {items.map((item) => renderEveField(item))}
                      </div>
                    )
                  })
                )}
              </>
            )}

            {settingsTab === 'Alertes' && (
              <>
                <p className="lede">Préférences push sur cet appareil.</p>
                {(
                  [
                    ['targetStop', 'Alerte stop / objectif'],
                    ['accel', 'Alerte accélération'],
                    ['directionFlip', 'Alerte retournement de direction'],
                  ] as const
                ).map(([key, label]) => (
                  <label className="checkrow" key={key}>
                    <span className="check-copy">{label}</span>
                    <input
                      type="checkbox"
                      checked={alertPrefs[key]}
                      onChange={(ev) =>
                        setAlertPrefs((prev) => ({ ...prev, [key]: ev.target.checked }))
                      }
                    />
                  </label>
                ))}
                <div className="btn-row">
                  <button
                    type="button"
                    className="suggestion"
                    disabled={pushBusy}
                    onClick={() => {
                      setPushBusy(true)
                      setPushMsg(null)
                      void enablePushAlerts().then((r) => {
                        setPushBusy(false)
                        setPushMsg(
                          r.ok
                            ? 'Abonnement push enregistré sur cet appareil.'
                            : r.message,
                        )
                      })
                    }}
                  >
                    {pushBusy ? 'Activation…' : 'Activer les alertes push'}
                  </button>
                  <button
                    type="button"
                    className="suggestion"
                    disabled={pushBusy}
                    onClick={() => {
                      setPushBusy(true)
                      void disablePushAlerts().then(() => {
                        setPushBusy(false)
                        setPushMsg('Abonnement push retiré sur cet appareil.')
                      })
                    }}
                  >
                    Désabonner
                  </button>
                </div>
                {pushMsg ? (
                  <p className="hint" role="status">
                    {pushMsg}
                  </p>
                ) : null}
              </>
            )}

            {settingsTab === 'Connexions' && (
              <>
                <p className="lede">État des liens — lecture seule.</p>
                <div className="statline">
                  <span>Moteur</span>
                  <b>{badge(engine ? 'CONNECTÉ' : 'OFF', engine ? 'green' : 'red')}</b>
                </div>
                <div className="statline">
                  <span>Marché</span>
                  <b>{badge(engine ? 'LIVE' : '—', engine ? 'green' : 'gray')}</b>
                </div>
                <div className="statline">
                  <span>Broker live</span>
                  <b>{badge('NON CONNECTÉ', 'gray')}</b>
                </div>
                <div className="statline">
                  <span>Ève autonomie paper</span>
                  <b>{badge(eveAutonomy ? 'ON' : 'OFF', eveAutonomy ? 'green' : 'amber')}</b>
                </div>
                <div className="statline">
                  <span>Event Radar</span>
                  <b>{badge(eveRadar ? 'ON' : 'OFF', eveRadar ? 'green' : 'gray')}</b>
                </div>
                <p className="hint">
                  JEV API (typesafe) + jevos fallback crédit : env moteur. Knobs : onglet
                  Ève / JEV.
                </p>
              </>
            )}

            {error ? (
              <p className="alert" role="alert">
                {error}
              </p>
            ) : null}

            <div className="form-foot">
              {showSave ? (
                <button type="submit" className="primary" disabled={saving}>
                  {saving ? 'Enregistrement…' : saved ? 'Enregistré' : 'Enregistrer'}
                </button>
              ) : null}
              <p className="hint">{saveHint}</p>
            </div>
          </form>
        </section>

        <aside className="card side-card">
          <div className="card-head">
            <h2>Statut</h2>
          </div>
          <div className="card-body">
            <div className="statline">
              <span>Mode</span>
              <b>{badge('PAPER', 'gray')}</b>
            </div>
            <p>Aucun ordre broker. Portefeuilles simulés.</p>
            <div className="statline">
              <span>Bougies</span>
              <b>Clôturées</b>
            </div>
            <p>Décision uniquement sur bougie fermée.</p>
            <div className="statline">
              <span>Ève</span>
              <b>{eveAutonomy ? 'Trade paper' : 'Dry-run'}</b>
            </div>
            <p>
              Autonomie on = ouverture paper via Risk Kernel. Kill-switch ={' '}
              <code>EVE_PAPER_AUTONOMY</code>.
            </p>
          </div>
        </aside>
      </div>
    </div>
  )
}
