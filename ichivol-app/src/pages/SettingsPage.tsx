/**
 * Paramètres — port littéral de design-reference/ichivol-workspace `parametres()` + page-head.
 * Classes HTML = maquette. Préférences locales + écritures engine (patchSettings / push).
 */

import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { getPaperOverview, type PaperOverview } from '../lib/paper'
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
import { invalidateEngineThresholdsCache } from '../lib/engineThresholds'
import { llmStatusLabel, useLlmStatus } from '../lib/llmStatus'
import type { LlmConnection } from '../lib/settings'
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
  const [settingsTab, setSettingsTab] = useState<SettingsTab>('Limites de risque')
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
  const [paperRisk, setPaperRisk] = useState<PaperOverview['risk'] | null>(null)

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
    getPaperOverview()
      .then((ov) => setPaperRisk(ov.risk ?? null))
      .catch(() => setPaperRisk(null))
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
    [local, settingsTab, engine, llmProvider, llmModel, llmApiKey, clearKey, llmLive, rvol, tenkan, kijun, senkouB, sources, alertPrefs],
  )

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
          <form id="settings-form" className="card-body" onSubmit={(ev) => void onSave(ev)}>
            {settingsTab === 'Limites de risque' && (
              <>
                <p style={{ fontSize: 12, color: 'var(--muted)' }}>
                  Plafonds appliqués par le profil paper ICHIVOL_BASELINE_V1. Ils ne sont pas des
                  préférences navigateur : les modifier ici ne changerait pas le risk kernel.
                </p>
                <div className="statline">
                  <span>Risque par trade</span>
                  <b>0,5 %</b>
                </div>
                <div className="statline">
                  <span>Risque ouvert max</span>
                  <b>
                    {paperRisk?.max_open_risk_pct != null
                      ? `${(paperRisk.max_open_risk_pct * 100).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} %`
                      : '4 %'}
                  </b>
                </div>
                <div className="statline">
                  <span>Positions simultanées max</span>
                  <b>{paperRisk?.max_open_positions ?? '—'}</b>
                </div>
                <div className="statline">
                  <span>Positions ouvertes</span>
                  <b>{paperRisk?.open_positions ?? '—'}</b>
                </div>
              </>
            )}

            {settingsTab === 'Marché et univers' && (
              <>
                <div className="field">
                  <span>Sources de données</span>
                  {(
                    [
                      ['binance', 'Binance'],
                      ['bybit', 'Bybit'],
                      ['okx', 'OKX'],
                    ] as const
                  ).map(([id, label]) => (
                    <label className="checkrow" key={id}>
                      {label}
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
                  <small>Enregistré sur votre compte (activeSources).</small>
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
                <div className="grid equal">
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
                  <small>OpenRouter reste le provider par défaut (une clé, plusieurs modèles).</small>
                </div>
                <div className="field">
                  <label htmlFor="llmModel">Modèle d’analyse</label>
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
                      ? `État : ${engine.llmProvider}${engine.llmApiKeySet ? ' · clé enregistrée' : ' · pas de clé UI'}${engine.llmReady ? ' · prêt' : ' · non prêt'}. Vide = conserver la clé actuelle.`
                      : 'Settings engine : —.'}
                  </small>
                </div>
                {engine?.llmApiKeySet && (
                  <label className="checkrow">
                    Effacer la clé enregistrée
                    <input
                      type="checkbox"
                      checked={clearKey}
                      onChange={(ev) => setClearKey(ev.target.checked)}
                    />
                  </label>
                )}
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
                {testResult && (
                  <div
                    className="notice"
                    role="status"
                    style={{
                      marginTop: 12,
                      background: testResult.ok ? '#e7f3ee' : '#f8ecea',
                      borderColor: testResult.ok ? '#c5ddd4' : '#e8cfc9',
                      color: testResult.ok ? '#168579' : '#c8412f',
                    }}
                  >
                    {testResult.ok ? 'Connecté' : 'Échec'} · {providerLabel(testResult.provider)} ·{' '}
                    {testResult.model} · {testResult.message}
                    {testResult.latencyMs ? ` · ${testResult.latencyMs} ms` : ''}
                  </div>
                )}

                <h3 style={{ marginTop: 22 }}>LLM enregistrés</h3>
                <p style={{ fontSize: 12, color: 'var(--muted)' }}>
                  Chaque provider avec une clé (interface ou serveur) apparaît ici. « Connecté »
                  veut dire que le dernier test a répondu.
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
                              {row.active ? <small>provider actif</small> : null}
                            </td>
                            <td>{badge(status, tone)}</td>
                            <td>{modelShown}</td>
                            <td>{row.connected ? 'Configurée' : 'Absente'}</td>
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

            {settingsTab === 'Alertes' && (
              <>
                {(
                  [
                    ['targetStop', 'Alerte stop / objectif'],
                    ['accel', 'Alerte accélération'],
                    ['directionFlip', 'Alerte retournement de direction'],
                  ] as const
                ).map(([key, label]) => (
                  <label className="checkrow" key={key}>
                    {label}
                    <input
                      type="checkbox"
                      checked={alertPrefs[key]}
                      onChange={(ev) =>
                        setAlertPrefs((prev) => ({ ...prev, [key]: ev.target.checked }))
                      }
                    />
                  </label>
                ))}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 16 }}>
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
                    Désabonner cet appareil
                  </button>
                </div>
                {pushMsg && (
                  <p style={{ fontSize: 12, color: 'var(--muted)', marginTop: 10 }} role="status">
                    {pushMsg}
                  </p>
                )}
              </>
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

            {error && (
              <p style={{ fontSize: 12, color: 'var(--red)', marginTop: 12 }} role="alert">
                {error}
              </p>
            )}

            <button type="submit" className="primary" disabled={saving}>
              {saving ? 'Enregistrement…' : saved ? 'Enregistré' : 'Enregistrer les préférences'}
            </button>
            <p style={{ fontSize: 10, color: 'var(--muted)' }}>
              Marché, alertes et LLM sont écrits sur votre compte. Les plafonds de risque affichés
              sont ceux du profil paper, en lecture seule.
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
            <p style={{ fontSize: 12, color: 'var(--muted)' }}>
              Aucun ordre n’est envoyé à un courtier. Le portefeuille est simulé : c’est voulu, pas
              une panne.
            </p>
            <div className="statline">
              <span>Bougies utilisées</span>
              <b>Déjà clôturées</b>
            </div>
            <p style={{ fontSize: 12, color: 'var(--muted)' }}>
              Le moteur ignore la bougie en cours. Une décision ne sort qu’une fois la bougie
              fermée.
            </p>
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
