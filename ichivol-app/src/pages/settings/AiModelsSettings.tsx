/**
 * « Modèles d'IA » — le modèle de langage du Copilot (chat). Écrit sur le compte via `/api/settings`.
 * La clé n'est jamais renvoyée en clair : le serveur ne dit que si elle existe.
 */

import { useEffect, useState } from 'react'
import { useLlmStatus, type LlmConnState } from '../../lib/llmStatus'
import {
  DEFAULT_MODELS,
  modelsForProvider,
  patchSettings,
  testLlm,
  type AppSettings,
  type LlmConnection,
  type LlmProvider,
  type LlmTestResult,
} from '../../lib/settings'

const PROVIDERS: { id: LlmProvider; label: string; keyHint: string; blurb: string }[] = [
  {
    id: 'openrouter',
    label: 'OpenRouter',
    keyHint: 'sk-or-…',
    blurb: 'Une seule clé donne accès à plusieurs modèles. Conseillé.',
  },
  { id: 'anthropic', label: 'Anthropic', keyHint: 'sk-ant-…', blurb: 'Modèles Claude, clé Anthropic.' },
  { id: 'openai', label: 'OpenAI', keyHint: 'sk-…', blurb: 'Modèles GPT, clé OpenAI.' },
]

function providerLabel(id: LlmProvider): string {
  return PROVIDERS.find((p) => p.id === id)?.label ?? id
}

function keySourceText(source: LlmConnection['keySource']): string {
  switch (source) {
    case 'ui':
      return 'clé enregistrée ici'
    case 'env':
      return 'clé du serveur'
    case 'both':
      return 'clé enregistrée ici (prioritaire) et clé du serveur'
    case 'none':
      return 'aucune clé'
    default: {
      const _exhaustive: never = source
      return _exhaustive
    }
  }
}

/** État de connexion en mots simples + couleur de pastille. */
export function connText(state: LlmConnState): { text: string; tone: 'green' | 'amber' | 'red' | 'gray' } {
  switch (state) {
    case 'ok':
      return { text: 'Connecté', tone: 'green' }
    case 'idle':
    case 'checking':
      return { text: 'Vérification…', tone: 'amber' }
    case 'no_key':
      return { text: 'Pas de clé', tone: 'amber' }
    case 'bad_key':
      return { text: 'Clé refusée', tone: 'red' }
    case 'unreachable':
      return { text: 'Injoignable', tone: 'red' }
    case 'error':
      return { text: 'Erreur', tone: 'red' }
    default: {
      const _exhaustive: never = state
      return _exhaustive
    }
  }
}

function testText(r: LlmTestResult): string {
  if (r.ok) return `Connexion réussie en ${r.latencyMs} ms.`
  switch (r.status) {
    case 'no_key':
      return 'Aucune clé pour ce fournisseur.'
    case 'bad_key':
      return 'Clé refusée par le fournisseur.'
    case 'unreachable':
      return 'Fournisseur injoignable.'
    default:
      return r.message || 'Le test a échoué.'
  }
}

type Props = {
  engine: AppSettings | null
  onSaved: (s: AppSettings) => void
}

export function AiModelsSettings({ engine, onSaved }: Props) {
  const llmLive = useLlmStatus()
  const [provider, setProvider] = useState<LlmProvider>('openrouter')
  const [model, setModel] = useState(DEFAULT_MODELS.openrouter)
  const [apiKey, setApiKey] = useState('')
  const [clearKey, setClearKey] = useState(false)
  const [busy, setBusy] = useState<'save' | LlmProvider | null>(null)
  const [tests, setTests] = useState<Partial<Record<LlmProvider, LlmTestResult>>>({})
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)

  useEffect(() => {
    if (!engine) return
    setProvider(engine.llmProvider)
    setModel(engine.llmModel || DEFAULT_MODELS[engine.llmProvider])
  }, [engine])

  const models = modelsForProvider(provider, engine?.llmModels)
  const dirty =
    Boolean(engine) &&
    (provider !== engine?.llmProvider ||
      model !== (engine?.llmModel || DEFAULT_MODELS[engine?.llmProvider ?? 'openrouter']) ||
      apiKey.trim() !== '' ||
      clearKey)

  const rows: LlmConnection[] =
    engine?.llmConnections && engine.llmConnections.length > 0
      ? engine.llmConnections
      : PROVIDERS.map((p) => ({
          provider: p.id,
          connected: p.id === engine?.llmProvider && Boolean(engine?.llmReady || engine?.llmApiKeySet),
          keySource:
            p.id === engine?.llmProvider ? (engine?.llmApiKeySet ? 'ui' : engine?.llmReady ? 'env' : 'none') : 'none',
          active: p.id === engine?.llmProvider,
          model: p.id === engine?.llmProvider ? (engine?.llmModel ?? null) : null,
        }))

  async function save() {
    if (!engine) return
    setBusy('save')
    setMsg(null)
    try {
      const updated = await patchSettings({
        llmProvider: provider,
        llmModel: model || DEFAULT_MODELS[provider],
        ...(clearKey ? { llmApiKey: '' } : apiKey.trim() ? { llmApiKey: apiKey.trim() } : {}),
      })
      onSaved(updated)
      setApiKey('')
      setClearKey(false)
      setMsg({ ok: true, text: 'Enregistré. Le Copilot utilise désormais ce modèle.' })
      void llmLive.refresh()
    } catch (err: unknown) {
      setMsg({ ok: false, text: err instanceof Error ? err.message : 'Enregistrement impossible' })
    } finally {
      setBusy(null)
    }
  }

  async function probe(p: LlmProvider, m: string | null) {
    const modelId = m || DEFAULT_MODELS[p]
    const key = p === provider && apiKey.trim() ? apiKey.trim() : undefined
    setBusy(p)
    setMsg(null)
    try {
      const result = await testLlm({ provider: p, model: modelId, apiKey: key })
      setTests((prev) => ({ ...prev, [p]: result }))
      if (p === engine?.llmProvider) await llmLive.refresh({ provider: p, model: modelId, apiKey: key })
    } catch (err: unknown) {
      setMsg({ ok: false, text: err instanceof Error ? err.message : 'Test impossible' })
    } finally {
      setBusy(null)
    }
  }

  const formTest = tests[provider]

  return (
    <>
      <section className="card">
        <div className="card-head">
          <h2>Modèle du Copilot</h2>
          <span className={`tag ${connText(llmLive.state).tone}`}>{connText(llmLive.state).text}</span>
        </div>
        <div className="card-body">
          <p className="lede">
            Le Copilot est le chat d’Ève. Il a besoin d’un modèle de langage et d’une clé chez un
            fournisseur. Ce choix n’a aucun effet sur les décisions de trading : elles passent par JEV.
          </p>
          {!engine ? (
            <p className="notice err">Serveur IchiVol injoignable : impossible de lire ou modifier ce réglage.</p>
          ) : null}
          <div className="field">
            <label htmlFor="llmProvider">Fournisseur</label>
            <select
              id="llmProvider"
              value={provider}
              disabled={!engine}
              onChange={(e) => {
                const next = e.target.value as LlmProvider
                setProvider(next)
                const list = modelsForProvider(next, engine?.llmModels)
                setModel(list.some((m) => m.id === model) ? model : DEFAULT_MODELS[next])
              }}
            >
              {PROVIDERS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
            <small>{PROVIDERS.find((p) => p.id === provider)?.blurb}</small>
          </div>
          <div className="field">
            <label htmlFor="llmModel">Modèle</label>
            <select id="llmModel" value={model} disabled={!engine} onChange={(e) => setModel(e.target.value)}>
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
              {model && !models.some((m) => m.id === model) ? <option value={model}>{model}</option> : null}
            </select>
          </div>
          <div className="field">
            <label htmlFor="llmApiKey">{engine?.llmApiKeySet ? 'Remplacer la clé (facultatif)' : 'Clé d’accès'}</label>
            <input
              id="llmApiKey"
              type="password"
              autoComplete="off"
              value={apiKey}
              placeholder={PROVIDERS.find((p) => p.id === provider)?.keyHint ?? 'sk-…'}
              disabled={!engine || clearKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
            <small>
              {engine?.llmApiKeySet
                ? 'Une clé est déjà enregistrée (chiffrée, jamais réaffichée). Laissez vide pour la garder.'
                : engine?.llmReady
                  ? 'Aucune clé enregistrée ici : le Copilot utilise la clé du serveur.'
                  : 'Aucune clé pour l’instant : le Copilot ne peut pas répondre.'}
            </small>
          </div>
          {engine?.llmApiKeySet ? (
            <label className="checkrow">
              <span className="check-copy">
                Supprimer la clé enregistrée
                <small>Le Copilot repassera sur la clé du serveur, s’il y en a une.</small>
              </span>
              <input type="checkbox" checked={clearKey} onChange={(e) => setClearKey(e.target.checked)} />
            </label>
          ) : null}
          <div className="btn-row">
            <button type="button" className="primary" disabled={!engine || !dirty || busy !== null} onClick={() => void save()}>
              {busy === 'save' ? 'Enregistrement…' : 'Enregistrer'}
            </button>
            <button
              type="button"
              className="suggestion"
              disabled={!engine || busy !== null}
              onClick={() => void probe(provider, model)}
            >
              {busy === provider ? 'Test en cours…' : 'Tester la connexion'}
            </button>
          </div>
          {formTest ? (
            <p className={`notice ${formTest.ok ? 'ok' : 'err'}`} role="status">
              {providerLabel(formTest.provider)} · {testText(formTest)}
            </p>
          ) : null}
          {msg ? (
            <p className={`notice ${msg.ok ? 'ok' : 'err'}`} role="status">
              {msg.text}
            </p>
          ) : null}
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Fournisseurs</h2>
        </div>
        <div className="card-body">
          <p className="lede">Les clés connues pour chaque fournisseur. Un test vérifie que la clé est acceptée.</p>
          <ul className="rows">
            {rows.map((row) => {
              const t = tests[row.provider]
              const checking = busy === row.provider
              let tone = 'gray'
              let status = 'Non configuré'
              if (checking) {
                tone = 'amber'
                status = 'Test…'
              } else if (t) {
                tone = t.ok ? 'green' : 'red'
                status = t.ok ? 'Connecté' : t.status === 'bad_key' ? 'Clé refusée' : 'Échec'
              } else if (row.active && llmLive.state === 'ok') {
                tone = 'green'
                status = 'Connecté'
              } else if (row.connected) {
                tone = 'amber'
                status = 'Clé présente, non testée'
              }
              return (
                <li key={row.provider}>
                  <div className="row-main">
                    <b>{providerLabel(row.provider)}</b>
                    {row.active ? <span className="tag">Utilisé par le Copilot</span> : null}
                    <span className={`tag ${tone}`}>{status}</span>
                  </div>
                  <p className="row-sub">
                    {keySourceText(row.keySource)}
                    {row.model ? ` · ${row.model}` : ''}
                    {t?.ok ? ` · ${t.latencyMs} ms` : ''}
                  </p>
                  <button
                    type="button"
                    className="suggestion"
                    disabled={!engine || busy !== null}
                    onClick={() => void probe(row.provider, row.provider === provider ? model : row.model)}
                  >
                    Tester
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
      </section>
    </>
  )
}
