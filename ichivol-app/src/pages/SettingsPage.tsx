/**
 * Paramètres — une page qui s'explique d'elle-même.
 *
 * Sections : Trading automatique · Ève et JEV · Modèles d'IA · Alertes · Graphiques · Connexions et état.
 * Sources : `/api/settings` (compte), `/api/engine/eve/settings/*` (moteur), portefeuilles paper (`loadAllBooks`),
 * Web Push (`pushAlerts`), sondes de connexion (`useLlmStatus`). Argent fictif uniquement.
 */

import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { loadAllBooks, type Book } from '../lib/allBooks'
import { detectPushSupport, disablePushAlerts, enablePushAlerts } from '../lib/pushAlerts'
import { getSettings, patchSettings, type AppSettings } from '../lib/settings'
import {
  getEveSettingsSchema,
  getEveSettingsValues,
  type EveSettingGroup,
} from '../lib/eveSettings'
import { invalidateEngineThresholdsCache } from '../lib/engineThresholds'
import { useLlmStatus, type JevProbeStatus } from '../lib/llmStatus'
import { DEFAULT_ICHI, DEFAULT_VOL } from '../lib/types'
import { AiModelsSettings, connText } from './settings/AiModelsSettings'
import { EveSettings } from './settings/EveSettings'
import './SettingsPage.css'

type SectionId = 'auto' | 'eve' | 'ia' | 'alertes' | 'graphiques' | 'connexions'

const SECTIONS: Array<{ id: SectionId; label: string; sub: string }> = [
  { id: 'auto', label: 'Trading automatique', sub: 'Pilote d’Ève, portefeuilles, limites' },
  { id: 'eve', label: 'Ève et JEV', sub: 'Modes, seuils, actualités' },
  { id: 'ia', label: 'Modèles d’IA', sub: 'Clé et modèle du Copilot' },
  { id: 'alertes', label: 'Alertes', sub: 'Notifications sur vos positions' },
  { id: 'graphiques', label: 'Graphiques', sub: 'Ichimoku et volume' },
  { id: 'connexions', label: 'Connexions et état', sub: 'Ce qui répond, ce qui manque' },
]

type EveValue = string | number | boolean
type Tone = 'green' | 'amber' | 'red' | 'gray' | ''

function Tag({ tone = '', children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`tag ${tone}`.trim()}>{children}</span>
}

function pct(v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return `${(v * 100).toLocaleString('fr-FR', { maximumFractionDigits: digits })} %`
}

function errText(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

/* ------------------------------------------------------------------ */
/* Trading automatique                                                  */
/* ------------------------------------------------------------------ */

function Meter({ value, max, label }: { value: number | null | undefined; max: number | null | undefined; label: string }) {
  const ratio = value != null && max ? Math.min(1, Math.max(0, value / max)) : 0
  const tone = ratio >= 1 ? 'red' : ratio >= 0.8 ? 'amber' : 'green'
  return (
    <div className="meter" role="img" aria-label={label}>
      <span className={tone} style={{ width: `${Math.round(ratio * 100)}%` }} />
    </div>
  )
}

function AutoTradingSection({
  autonomy,
  books,
  booksError,
}: {
  autonomy: boolean | null
  books: Book[] | null
  booksError: string | null
}) {
  return (
    <>
      <section className="card">
        <div className="card-head">
          <h2>Pilote automatique d’Ève</h2>
          {autonomy == null ? (
            <Tag tone="gray">État inconnu</Tag>
          ) : autonomy ? (
            <Tag tone="green">Actif</Tag>
          ) : (
            <Tag tone="amber">Arrêté</Tag>
          )}
        </div>
        <div className="card-body">
          <p className="state-line">
            {autonomy == null
              ? 'Le moteur ne répond pas : impossible de savoir si Ève trade seule en ce moment.'
              : autonomy
                ? 'Ève décide seule des ouvertures et fermetures sur tous les portefeuilles actifs ci-dessous.'
                : 'Ève ne trade pas seule. Chaque portefeuille applique uniquement sa propre méthode, sans l’avis d’Ève.'}
          </p>
          <ol className="steps">
            <li>
              <b>Le moteur repère un signal</b> à la clôture d’une bougie, selon la méthode du portefeuille.
            </li>
            <li>
              <b>Ève accepte ou refuse</b> après l’avis de ses modes et de JEV. Dans le doute, elle ne fait rien.
            </li>
            <li>
              <b>Le garde-fou de risque (Risk Kernel) a le dernier mot</b> : il bloque tout ordre qui dépasse les
              limites du portefeuille. Les stops et objectifs restent appliqués dans tous les cas.
            </li>
          </ol>
          <p className="hint">
            Ce pilote s’allume et s’éteint uniquement sur le serveur du moteur, pas depuis le navigateur : un clic
            ne doit jamais pouvoir le lancer par erreur. Tout se passe en argent fictif.
          </p>
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Portefeuilles et limites de risque</h2>
          {books ? <small>{books.length} actif{books.length > 1 ? 's' : ''}</small> : null}
        </div>
        <div className="card-body">
          <p className="lede">
            Les portefeuilles fictifs suivis par le moteur, et ce que le garde-fou de risque leur autorise. Le{' '}
            <b>risque engagé</b> est ce que vous perdriez si tous les stops étaient touchés, en part du capital.
            Ces limites viennent de la méthode de chaque portefeuille et ne se modifient pas ici.
          </p>
          {booksError ? <p className="notice err">Portefeuilles indisponibles : {booksError}</p> : null}
          {books == null && !booksError ? <p className="hint">Chargement…</p> : null}
          {books && books.length === 0 ? <p className="hint">Aucun portefeuille actif.</p> : null}
          <div className="books">
            {books?.map((b) => {
              const r = b.overview.risk
              const blocked = b.row.kill_switch_armed || b.row.daily_loss_locked
              const refusals = r?.recent_refusals?.length ?? 0
              return (
                <article className="book" key={b.code}>
                  <header>
                    <h3>{b.label}</h3>
                    {b.row.kill_switch_armed ? (
                      <Tag tone="red">Arrêt d’urgence</Tag>
                    ) : b.row.daily_loss_locked ? (
                      <Tag tone="red">Perte du jour atteinte</Tag>
                    ) : (
                      <Tag tone="green">Ouvert aux entrées</Tag>
                    )}
                  </header>
                  {r ? (
                    <>
                      <div className="limit">
                        <div className="limit-head">
                          <span>Risque engagé</span>
                          <b>
                            {pct(r.open_risk_pct)} <small>sur {pct(r.max_open_risk_pct)} max</small>
                          </b>
                        </div>
                        <Meter
                          value={r.open_risk_pct}
                          max={r.max_open_risk_pct}
                          label={`Risque engagé ${pct(r.open_risk_pct)} sur ${pct(r.max_open_risk_pct)}`}
                        />
                      </div>
                      <div className="limit">
                        <div className="limit-head">
                          <span>Positions ouvertes</span>
                          <b>
                            {r.open_positions} <small>sur {r.max_open_positions} max</small>
                          </b>
                        </div>
                        <Meter
                          value={r.open_positions}
                          max={r.max_open_positions}
                          label={`${r.open_positions} positions sur ${r.max_open_positions}`}
                        />
                      </div>
                      <p className="book-foot">
                        {blocked
                          ? 'Aucune nouvelle position tant que le verrou est en place ; les positions ouvertes restent gérées.'
                          : refusals > 0
                            ? `${refusals} ordre${refusals > 1 ? 's' : ''} refusé${refusals > 1 ? 's' : ''} récemment par le garde-fou.`
                            : 'Aucun refus récent du garde-fou.'}
                      </p>
                    </>
                  ) : (
                    <p className="book-foot">Limites non communiquées par le moteur pour ce portefeuille.</p>
                  )}
                </article>
              )
            })}
          </div>
          <p className="hint">
            L’arrêt d’urgence est dans le bandeau du haut ; le détail des refus, dans le <Link to="/app/portefeuille?tab=risque">Portefeuille</Link>.
          </p>
        </div>
      </section>
    </>
  )
}

/* ------------------------------------------------------------------ */
/* Alertes                                                              */
/* ------------------------------------------------------------------ */

type AlertPrefs = NonNullable<AppSettings['pushAlertPrefs']>

const DEFAULT_ALERTS: AlertPrefs = {
  enabled: false,
  targetStop: true,
  accel: true,
  directionFlip: true,
  nearPct: 0.2,
  cooldownMin: 30,
}

async function deviceSubscribed(): Promise<boolean> {
  try {
    if (!('serviceWorker' in navigator)) return false
    const reg = await navigator.serviceWorker.getRegistration()
    return Boolean(await reg?.pushManager.getSubscription())
  } catch {
    return false
  }
}

function AlertsSection({ engine, onSaved }: { engine: AppSettings | null; onSaved: (s: AppSettings) => void }) {
  const saved = { ...DEFAULT_ALERTS, ...(engine?.pushAlertPrefs ?? {}) }
  const [prefs, setPrefs] = useState<AlertPrefs>(saved)
  const [nearText, setNearText] = useState(String(Math.round(saved.nearPct * 100)))
  const [coolText, setCoolText] = useState(String(saved.cooldownMin))
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [device, setDevice] = useState<boolean | null>(null)
  const [deviceBusy, setDeviceBusy] = useState(false)
  const [deviceMsg, setDeviceMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const support = detectPushSupport()

  useEffect(() => {
    if (!engine) return
    const s = { ...DEFAULT_ALERTS, ...(engine.pushAlertPrefs ?? {}) }
    setPrefs(s)
    setNearText(String(Math.round(s.nearPct * 100)))
    setCoolText(String(s.cooldownMin))
  }, [engine])

  useEffect(() => {
    void deviceSubscribed().then(setDevice)
  }, [])

  const near = Number(nearText)
  const cool = Number(coolText)
  const nearOk = Number.isFinite(near) && near >= 1 && near <= 100
  const coolOk = Number.isFinite(cool) && cool >= 1 && cool <= 1440

  async function save() {
    if (!engine || !nearOk || !coolOk) return
    setBusy(true)
    setMsg(null)
    try {
      const updated = await patchSettings({
        pushAlertPrefs: { ...prefs, nearPct: near / 100, cooldownMin: Math.floor(cool) },
      })
      onSaved(updated)
      setMsg({ ok: true, text: 'Préférences enregistrées.' })
    } catch (err: unknown) {
      setMsg({ ok: false, text: errText(err) })
    } finally {
      setBusy(false)
    }
  }

  const kinds: Array<[keyof Pick<AlertPrefs, 'targetStop' | 'accel' | 'directionFlip'>, string, string]> = [
    ['targetStop', 'Objectif ou stop proche', 'Quand le prix a parcouru l’essentiel du chemin vers l’objectif ou le stop.'],
    ['accel', 'Accélération confirmée', 'Volume nettement au-dessus de la normale et cassure dans le sens de votre position.'],
    ['directionFlip', 'Tendance qui se retourne', 'Quand la lecture Ichimoku passe dans le sens opposé à votre position.'],
  ]

  return (
    <>
      <section className="card">
        <div className="card-head">
          <h2>Alertes sur vos positions</h2>
          <Tag tone={saved.enabled ? 'green' : 'gray'}>{saved.enabled ? 'Activées' : 'Désactivées'}</Tag>
        </div>
        <div className="card-body">
          <p className="lede">
            IchiVol surveille les positions fictives que vous avez confirmées vous-même et vous prévient dans
            l’application (et par notification si cet appareil est abonné). Ce sont des informations : aucune alerte
            ne passe d’ordre.
          </p>
          {!engine ? <p className="notice err">Serveur IchiVol injoignable : préférences non modifiables.</p> : null}
          <label className="checkrow strong">
            <span className="check-copy">
              Recevoir les alertes
              <small>Interrupteur général. Désactivé, aucune alerte n’est envoyée, quels que soient les choix dessous.</small>
            </span>
            <span className="switch">
              <input
                type="checkbox"
                checked={prefs.enabled}
                disabled={!engine}
                onChange={(e) => setPrefs((p) => ({ ...p, enabled: e.target.checked }))}
              />
              <span aria-hidden="true" />
            </span>
          </label>
          <div className={prefs.enabled ? '' : 'dimmed'}>
            {kinds.map(([key, label, help]) => (
              <label className="checkrow" key={key}>
                <span className="check-copy">
                  {label}
                  <small>{help}</small>
                </span>
                <span className="switch">
                  <input
                    type="checkbox"
                    checked={prefs[key]}
                    disabled={!engine}
                    onChange={(e) => setPrefs((p) => ({ ...p, [key]: e.target.checked }))}
                  />
                  <span aria-hidden="true" />
                </span>
              </label>
            ))}
            <div className="field-row two">
              <div className="field">
                <label htmlFor="nearPct">Prévenir quand il reste</label>
                <div className={`num-input${nearOk ? '' : ' bad'}`}>
                  <input
                    id="nearPct"
                    type="number"
                    inputMode="numeric"
                    min={1}
                    max={100}
                    step={1}
                    value={nearText}
                    disabled={!engine}
                    onChange={(e) => setNearText(e.target.value)}
                  />
                  <span>%</span>
                </div>
                <small>
                  … de la distance vers l’objectif ou le stop. Par défaut : 20 %. Plus haut = prévenu plus tôt, plus
                  souvent.
                </small>
              </div>
              <div className="field">
                <label htmlFor="cooldown">Délai entre deux alertes identiques</label>
                <div className={`num-input${coolOk ? '' : ' bad'}`}>
                  <input
                    id="cooldown"
                    type="number"
                    inputMode="numeric"
                    min={1}
                    max={1440}
                    step={1}
                    value={coolText}
                    disabled={!engine}
                    onChange={(e) => setCoolText(e.target.value)}
                  />
                  <span>min</span>
                </div>
                <small>Évite d’être prévenu en boucle pour la même position. Par défaut : 30 min.</small>
              </div>
            </div>
          </div>
          <div className="btn-row">
            <button type="button" className="primary" disabled={!engine || busy || !nearOk || !coolOk} onClick={() => void save()}>
              {busy ? 'Enregistrement…' : 'Enregistrer'}
            </button>
          </div>
          {msg ? <p className={`notice ${msg.ok ? 'ok' : 'err'}`}>{msg.text}</p> : null}
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Notifications sur cet appareil</h2>
          {device == null ? null : <Tag tone={device ? 'green' : 'gray'}>{device ? 'Abonné' : 'Non abonné'}</Tag>}
        </div>
        <div className="card-body">
          <p className="lede">
            Pour recevoir les alertes même quand IchiVol est fermé. À faire sur chaque téléphone ou ordinateur.
          </p>
          {!support.ok ? <p className="notice err">{support.message}</p> : null}
          <div className="btn-row">
            <button
              type="button"
              className="suggestion"
              disabled={deviceBusy || !support.ok}
              onClick={() => {
                setDeviceBusy(true)
                void enablePushAlerts().then(async (r) => {
                  setDeviceBusy(false)
                  setDevice(await deviceSubscribed())
                  setDeviceMsg(
                    r.ok ? { ok: true, text: 'Cet appareil recevra les notifications.' } : { ok: false, text: r.message },
                  )
                })
              }}
            >
              {deviceBusy ? 'Activation…' : 'Activer sur cet appareil'}
            </button>
            <button
              type="button"
              className="suggestion"
              disabled={deviceBusy || !device}
              onClick={() => {
                setDeviceBusy(true)
                void disablePushAlerts().then(async () => {
                  setDeviceBusy(false)
                  setDevice(await deviceSubscribed())
                  setDeviceMsg({ ok: true, text: 'Cet appareil ne recevra plus de notifications.' })
                })
              }}
            >
              Désactiver sur cet appareil
            </button>
          </div>
          {deviceMsg ? <p className={`notice ${deviceMsg.ok ? 'ok' : 'err'}`}>{deviceMsg.text}</p> : null}
          {device && !saved.enabled ? (
            <p className="hint">Cet appareil est abonné, mais l’interrupteur « Recevoir les alertes » est coupé.</p>
          ) : null}
        </div>
      </section>
    </>
  )
}

/* ------------------------------------------------------------------ */
/* Graphiques                                                           */
/* ------------------------------------------------------------------ */

function ChartsSection({ engine, onSaved }: { engine: AppSettings | null; onSaved: (s: AppSettings) => void }) {
  const [vals, setVals] = useState({ tenkan: '9', kijun: '26', senkouB: '52', rvol: '1.5' })
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)

  useEffect(() => {
    if (!engine) return
    setVals({
      tenkan: String(engine.ichimokuParams?.tenkan ?? DEFAULT_ICHI.tenkan),
      kijun: String(engine.ichimokuParams?.kijun ?? DEFAULT_ICHI.kijun),
      senkouB: String(engine.ichimokuParams?.senkouB ?? DEFAULT_ICHI.senkouB),
      rvol: String(engine.volumeParams?.rvolConfirm ?? DEFAULT_VOL.rvolConfirm),
    })
  }, [engine])

  const vol = { ...DEFAULT_VOL, ...(engine?.volumeParams ?? {}) }
  const n = {
    tenkan: Number(vals.tenkan),
    kijun: Number(vals.kijun),
    senkouB: Number(vals.senkouB),
    rvol: Number(vals.rvol.replace(',', '.')),
  }
  const periodsOk = [n.tenkan, n.kijun, n.senkouB].every((x) => Number.isInteger(x) && x >= 1 && x <= 300)
  // Le moteur exige seuil bas < seuil significatif < seuil fort.
  const rvolOk = Number.isFinite(n.rvol) && n.rvol > vol.rvolLow && n.rvol < vol.rvolStrong

  async function save() {
    if (!engine || !periodsOk || !rvolOk) return
    setBusy(true)
    setMsg(null)
    try {
      const updated = await patchSettings({
        ichimokuParams: { ...engine.ichimokuParams, tenkan: n.tenkan, kijun: n.kijun, senkouB: n.senkouB },
        volumeParams: { ...engine.volumeParams, rvolConfirm: n.rvol, rvolSignificant: n.rvol },
      })
      onSaved(updated)
      invalidateEngineThresholdsCache()
      setMsg({ ok: true, text: 'Enregistré. Les graphiques et analyses utilisent ces valeurs dès le prochain chargement.' })
    } catch (err: unknown) {
      setMsg({ ok: false, text: errText(err) })
    } finally {
      setBusy(false)
    }
  }

  const periods: Array<[keyof typeof vals, string, number, string]> = [
    ['tenkan', 'Ligne rapide (Tenkan)', DEFAULT_ICHI.tenkan, 'Réagit vite aux mouvements récents.'],
    ['kijun', 'Ligne de référence (Kijun)', DEFAULT_ICHI.kijun, 'Équilibre de moyen terme.'],
    ['senkouB', 'Bord lent du nuage (Senkou B)', DEFAULT_ICHI.senkouB, 'Support ou résistance de fond.'],
  ]

  return (
    <section className="card">
      <div className="card-head">
        <h2>Ichimoku et volume</h2>
      </div>
      <div className="card-body">
        <p className="lede">
          Réglages de vos graphiques et des analyses que vous lancez vous-même (opportunités, tests de stratégie).
          Ils ne changent pas les méthodes des portefeuilles ni les décisions automatiques d’Ève.
        </p>
        {!engine ? <p className="notice err">Serveur IchiVol injoignable : réglages non modifiables.</p> : null}
        <h3 className="sub">Périodes Ichimoku (en bougies)</h3>
        <div className="field-row">
          {periods.map(([key, label, def, help]) => (
            <div className="field" key={key}>
              <label htmlFor={`ichi-${key}`}>{label}</label>
              <input
                id={`ichi-${key}`}
                type="number"
                inputMode="numeric"
                min={1}
                max={300}
                step={1}
                value={vals[key]}
                disabled={!engine}
                onChange={(e) => setVals((v) => ({ ...v, [key]: e.target.value }))}
              />
              <small>
                {help} Par défaut : {def}.
              </small>
            </div>
          ))}
        </div>
        <p className="hint">Périodes plus longues = lignes plus lisses, signaux plus rares et plus tardifs.</p>
        {!periodsOk ? <p className="knob-bad">Chaque période doit être un nombre entier entre 1 et 300.</p> : null}

        <h3 className="sub">Volume</h3>
        <div className="field">
          <label htmlFor="rvol">Volume « significatif » à partir de</label>
          <div className={`num-input short${rvolOk ? '' : ' bad'}`}>
            <input
              id="rvol"
              type="number"
              inputMode="decimal"
              min={vol.rvolLow}
              max={vol.rvolStrong}
              step={0.1}
              value={vals.rvol}
              disabled={!engine}
              onChange={(e) => setVals((v) => ({ ...v, rvol: e.target.value }))}
            />
            <span>× la normale</span>
          </div>
          <small>
            Un volume est jugé significatif quand il dépasse ce multiple du volume habituel. Par défaut : 1,5×. Plus haut =
            moins de signaux, mais plus solides. Doit rester entre{' '}
            {vol.rvolLow.toLocaleString('fr-FR')}× (volume faible) et {vol.rvolStrong.toLocaleString('fr-FR')}× (volume fort).
          </small>
        </div>
        <div className="btn-row">
          <button type="button" className="primary" disabled={!engine || busy || !periodsOk || !rvolOk} onClick={() => void save()}>
            {busy ? 'Enregistrement…' : 'Enregistrer'}
          </button>
        </div>
        {msg ? <p className={`notice ${msg.ok ? 'ok' : 'err'}`}>{msg.text}</p> : null}
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ */
/* Connexions et état                                                   */
/* ------------------------------------------------------------------ */

function jevText(p: JevProbeStatus): { text: string; tone: Tone } {
  switch (p.state) {
    case 'ok':
      return { text: p.latencyMs != null ? `Joignable · ${p.latencyMs} ms` : 'Joignable', tone: 'green' }
    case 'idle':
    case 'checking':
      return { text: 'Vérification…', tone: 'amber' }
    case 'no_key':
      return { text: 'Non configuré', tone: 'gray' }
    case 'disabled':
      return { text: 'Désactivé', tone: 'gray' }
    case 'unreachable':
      return { text: 'Injoignable', tone: 'red' }
    case 'error':
      return { text: 'Erreur', tone: 'red' }
    default: {
      const _exhaustive: never = p.state
      return _exhaustive
    }
  }
}

function ConnectionsSection({
  engine,
  engineHealth,
  onRecheck,
  onSaved,
}: {
  engine: AppSettings | null
  engineHealth: boolean | null
  onRecheck: () => void
  onSaved: (s: AppSettings) => void
}) {
  const llm = useLlmStatus()
  const [tdKey, setTdKey] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null)

  async function saveTd(clear: boolean) {
    setBusy(true)
    setMsg(null)
    try {
      const updated = await patchSettings({ twelveDataApiKey: clear ? '' : tdKey.trim() })
      onSaved(updated)
      setTdKey('')
      setMsg({ ok: true, text: clear ? 'Clé supprimée.' : 'Clé enregistrée.' })
    } catch (err: unknown) {
      setMsg({ ok: false, text: errText(err) })
    } finally {
      setBusy(false)
    }
  }

  const chat = connText(llm.state)
  const rows: Array<{ name: string; help: string; status: { text: string; tone: Tone } }> = [
    {
      name: 'Moteur de trading',
      help: 'Calcule les signaux, tient les portefeuilles fictifs, fait tourner Ève.',
      status:
        engineHealth == null
          ? { text: 'Vérification…', tone: 'amber' }
          : engineHealth
            ? { text: 'Joignable', tone: 'green' }
            : { text: 'Injoignable', tone: 'red' },
    },
    {
      name: 'Serveur IchiVol',
      help: 'Votre compte, vos réglages et vos alertes.',
      status: engine ? { text: 'Joignable', tone: 'green' } : { text: 'Injoignable', tone: 'red' },
    },
    { name: 'JEV · Cloud', help: 'Service principal du modèle de jugement d’Ève.', status: jevText(llm.typesafe) },
    { name: 'JEV · Local', help: 'Secours quand les crédits du service Cloud sont épuisés.', status: jevText(llm.jevos) },
    { name: 'Copilot', help: 'Le chat d’Ève (voir « Modèles d’IA »).', status: { text: chat.text, tone: chat.tone } },
    {
      name: 'Cours crypto (Binance, Bybit, OKX)',
      help: 'Données publiques, aucune clé nécessaire.',
      status: engine ? { text: 'Sans clé', tone: 'green' } : { text: '—', tone: 'gray' },
    },
    {
      name: 'Courtier réel',
      help: 'IchiVol ne passe jamais d’ordre réel. Aucun courtier n’est branché, et ce n’est pas prévu.',
      status: { text: 'Aucun · argent fictif', tone: 'gray' },
    },
  ]

  return (
    <>
      <section className="card">
        <div className="card-head">
          <h2>État des services</h2>
          <button type="button" className="suggestion" onClick={onRecheck} disabled={llm.state === 'checking'}>
            {llm.state === 'checking' ? 'Vérification…' : 'Revérifier'}
          </button>
        </div>
        <div className="card-body">
          <ul className="rows">
            {rows.map((r) => (
              <li key={r.name}>
                <div className="row-main">
                  <b>{r.name}</b>
                  <Tag tone={r.status.tone}>{r.status.text}</Tag>
                </div>
                <p className="row-sub">{r.help}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Clé Twelve Data</h2>
          <Tag tone={engine?.twelveDataApiKeySet ? 'green' : 'gray'}>
            {engine?.twelveDataApiKeySet ? 'Clé enregistrée' : 'Aucune clé ici'}
          </Tag>
        </div>
        <div className="card-body">
          <p className="lede">
            Facultatif. Sert uniquement aux cours des actions Apple et Tesla ; forex, métaux, indices et énergie sont déjà
            gratuits. Sans clé ici, IchiVol utilise celle du serveur.
          </p>
          <div className="field">
            <label htmlFor="tdKey">{engine?.twelveDataApiKeySet ? 'Remplacer la clé' : 'Votre clé'}</label>
            <input
              id="tdKey"
              type="password"
              autoComplete="off"
              value={tdKey}
              disabled={!engine}
              onChange={(e) => setTdKey(e.target.value)}
            />
            <small>Chiffrée sur le serveur, jamais réaffichée.</small>
          </div>
          <div className="btn-row">
            <button type="button" className="primary" disabled={!engine || busy || !tdKey.trim()} onClick={() => void saveTd(false)}>
              Enregistrer
            </button>
            {engine?.twelveDataApiKeySet ? (
              <button type="button" className="suggestion" disabled={busy} onClick={() => void saveTd(true)}>
                Supprimer la clé
              </button>
            ) : null}
          </div>
          {msg ? <p className={`notice ${msg.ok ? 'ok' : 'err'}`}>{msg.text}</p> : null}
        </div>
      </section>
    </>
  )
}

/* ------------------------------------------------------------------ */
/* Page                                                                 */
/* ------------------------------------------------------------------ */

export function SettingsPage() {
  const llm = useLlmStatus()
  const [params, setParams] = useSearchParams()
  const requested = params.get('section')
  const section: SectionId = SECTIONS.some((s) => s.id === requested) ? (requested as SectionId) : 'auto'

  const [engine, setEngine] = useState<AppSettings | null>(null)
  const [books, setBooks] = useState<Book[] | null>(null)
  const [booksError, setBooksError] = useState<string | null>(null)
  const [eveSchema, setEveSchema] = useState<Record<string, EveSettingGroup> | null>(null)
  const [eveValues, setEveValues] = useState<Record<string, EveValue>>({})
  const [eveError, setEveError] = useState<string | null>(null)
  const [engineHealth, setEngineHealth] = useState<boolean | null>(null)

  const checkHealth = useCallback(() => {
    setEngineHealth(null)
    fetch('/api/engine/health', { credentials: 'include' })
      .then(async (res) => {
        const j = (await res.json().catch(() => null)) as { status?: string; ok?: boolean } | null
        // Même critère que le Desk : le moteur dit « ok » ou « healthy ».
        setEngineHealth(res.ok && (j?.ok === true || j?.status === 'ok' || j?.status === 'healthy'))
      })
      .catch(() => setEngineHealth(false))
  }, [])

  useEffect(() => {
    getSettings()
      .then(setEngine)
      .catch(() => setEngine(null))
    loadAllBooks()
      .then(setBooks)
      .catch((err: unknown) => setBooksError(errText(err)))
    Promise.all([getEveSettingsSchema(), getEveSettingsValues()])
      .then(([s, v]) => {
        setEveSchema(s.schema)
        setEveValues(v.values)
      })
      .catch((err: unknown) => setEveError(errText(err)))
    checkHealth()
  }, [checkHealth])

  const autonomy = eveError || !eveSchema ? null : Boolean(eveValues.EVE_PAPER_AUTONOMY)
  const current = SECTIONS.find((s) => s.id === section)!

  return (
    <div className="params-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">IchiVol · Système</div>
          <h1>Paramètres</h1>
          <p className="subtitle">
            Tout ce qui pilote IchiVol, expliqué simplement. Argent fictif uniquement : aucun ordre réel n’est jamais
            passé.
          </p>
        </div>
        <div className="actions">
          <Tag tone="gray">Argent fictif</Tag>
          {autonomy == null ? null : (
            <Tag tone={autonomy ? 'green' : 'amber'}>{autonomy ? 'Pilote Ève actif' : 'Pilote Ève arrêté'}</Tag>
          )}
          {engineHealth === false ? <Tag tone="red">Moteur injoignable</Tag> : null}
        </div>
      </div>

      <div className="params-layout">
        <nav className="params-nav" aria-label="Sections des réglages">
          {SECTIONS.map((s) => (
            <button
              key={s.id}
              type="button"
              className={s.id === section ? 'active' : ''}
              aria-current={s.id === section ? 'page' : undefined}
              onClick={() => setParams({ section: s.id }, { replace: true })}
            >
              <b>{s.label}</b>
              <small>{s.sub}</small>
            </button>
          ))}
        </nav>

        <div className="params-content">
          <h2 className="section-heading">{current.label}</h2>
          {section === 'auto' ? <AutoTradingSection autonomy={autonomy} books={books} booksError={booksError} /> : null}
          {section === 'eve' ? (
            <EveSettings schema={eveSchema} values={eveValues} loadError={eveError} onSaved={setEveValues} />
          ) : null}
          {section === 'ia' ? <AiModelsSettings engine={engine} onSaved={setEngine} /> : null}
          {section === 'alertes' ? <AlertsSection engine={engine} onSaved={setEngine} /> : null}
          {section === 'graphiques' ? <ChartsSection engine={engine} onSaved={setEngine} /> : null}
          {section === 'connexions' ? (
            <ConnectionsSection
              engine={engine}
              engineHealth={engineHealth}
              onSaved={setEngine}
              onRecheck={() => {
                checkHealth()
                void llm.refresh()
              }}
            />
          ) : null}
        </div>
      </div>
    </div>
  )
}
