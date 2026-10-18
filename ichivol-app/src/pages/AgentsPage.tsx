/**
 * Ève — la page de l'IA qui décide : son état, ses quatre modes, ses résultats face au moteur seul,
 * ses dossiers, et une évaluation à la demande. Le Copilot (son chat) a sa propre page.
 * Fiches des modes = FicheHost / `?fiche=agent:eve:<mode>`.
 */

import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { EveDossiersPanel } from '../components/eve/EveDossiersPanel'
import { EveResults } from '../components/eve/EveResults'
import { createAgentMission, fetchAgents, fmtDue, type AgentsListResponse } from '../lib/agentsRuntime'
import { evaluateWithEve, getPaperAutonomy } from '../lib/eveApi'
import { eveActionFr } from '../lib/eveDecisions'
import { EVE_MODES, JEV_PRIMITIVES } from '../lib/eveModes'
import { useFicheNav } from '../lib/useFicheNav'
import './AgentsPage.css'

const TIMEFRAMES = ['15m', '1h', '4h', '1d'] as const

/** La chaîne de décision, dans l'ordre où elle s'applique, avec la page qui montre chaque étape. */
const CHAIN: Array<{ step: string; detail: string; to: string; link: string }> = [
  { step: 'Marché', detail: 'Le moteur lit le prix et le volume, bougie par bougie.', to: '/app/market', link: 'Marché' },
  { step: 'Signal', detail: 'Ses cinq portes disent s’il y a un trade à faire.', to: '/app/opportunites', link: 'Opportunités' },
  { step: 'Ève', detail: 'Elle accepte ou refuse la proposition, avec ses quatre modes et JEV.', to: '/app/agents', link: 'Cette page' },
  { step: 'Risk Kernel', detail: 'Il autorise ou bloque, selon les limites du portefeuille.', to: '/app/portefeuille', link: 'Portefeuille' },
  { step: 'Position paper', detail: 'Ouverte avec de l’argent fictif, suivie jusqu’au stop ou à l’objectif.', to: '/app/portefeuille', link: 'Portefeuille' },
  { step: 'Journal', detail: 'Chaque action est enregistrée et relisible.', to: '/app/operations', link: 'Opérations' },
]

export function AgentsPage() {
  const { openFiche } = useFicheNav()
  const [params] = useSearchParams()
  const [autonomy, setAutonomy] = useState<boolean | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  const [symbol, setSymbol] = useState(() => (params.get('symbol') ?? 'BTCUSDT').toUpperCase())
  const [timeframe, setTimeframe] = useState<(typeof TIMEFRAMES)[number]>('1h')
  const [evaluating, setEvaluating] = useState(false)
  const [evalMsg, setEvalMsg] = useState<{ ok: boolean; text: string } | null>(null)

  const [runtime, setRuntime] = useState<AgentsListResponse | null>(null)
  const [runtimeError, setRuntimeError] = useState<string | null>(null)
  const [missionBusy, setMissionBusy] = useState(false)
  const [missionMsg, setMissionMsg] = useState<{ ok: boolean; text: string } | null>(null)

  const loadAutonomy = useCallback(async () => {
    setAutonomy(await getPaperAutonomy().catch(() => null))
  }, [])

  const loadRuntime = useCallback(async () => {
    try {
      setRuntime(await fetchAgents())
      setRuntimeError(null)
    } catch (err) {
      setRuntime(null)
      setRuntimeError(err instanceof Error ? err.message : String(err))
    }
  }, [])

  useEffect(() => {
    void loadAutonomy()
    void loadRuntime()
  }, [loadAutonomy, loadRuntime])

  async function onEvaluate(e: FormEvent) {
    e.preventDefault()
    const sym = symbol.trim().toUpperCase()
    if (!sym || evaluating) return
    setEvaluating(true)
    setEvalMsg(null)
    try {
      const res = await evaluateWithEve(sym, timeframe)
      const action = res.synthesis?.action ?? res.verdict?.action ?? null
      const level = res.degradation?.level
      setEvalMsg({
        ok: true,
        text: `${sym} · ${timeframe} : Ève répond « ${eveActionFr(action)} »${
          level && level !== 'healthy' ? ` (JEV dégradé : ${level})` : ''
        }. Le dossier est dans la liste ci-dessous.`,
      })
      setRefreshKey((k) => k + 1)
    } catch (err) {
      setEvalMsg({ ok: false, text: err instanceof Error ? err.message : String(err) })
    } finally {
      setEvaluating(false)
    }
  }

  async function onMission(e: FormEvent) {
    e.preventDefault()
    const sym = symbol.trim().toUpperCase()
    if (!sym) return
    setMissionBusy(true)
    setMissionMsg(null)
    try {
      const res = await createAgentMission({ symbol: sym, timeframe: '1h', reason: `Surveiller ${sym} avec le Copilot d’Ève` })
      setMissionMsg({ ok: true, text: `Surveillance de ${res.mission.symbol} lancée · prochain contrôle ${fmtDue(res.mission.dueAt)}.` })
      void loadRuntime()
    } catch (err) {
      setMissionMsg({ ok: false, text: err instanceof Error ? err.message : String(err) })
    } finally {
      setMissionBusy(false)
    }
  }

  const watcher = runtime?.agents?.find((a) => a.id === 'opportunities')
  const nextCheck = watcher?.nextTaskDue
    ? `${watcher.nextTaskSymbol ? `${watcher.nextTaskSymbol} · ` : ''}${fmtDue(watcher.nextTaskDue)}`
    : null

  const aside = (
    <>
      <section className="iv-card">
        <div className="iv-card-head">
          <div className="iv-card-tabs">
            <span className="iv-card-tab is-on">Demander l’avis d’Ève</span>
          </div>
          <div className="iv-card-tools">crée un dossier, n’ouvre rien</div>
        </div>
        <div className="iv-card-body">
          <form className="ag-form" onSubmit={onEvaluate}>
            <div className="ag-form-row">
              <div className="iv-field">
                <label htmlFor="ag-eval-symbol">Instrument à évaluer</label>
                <input
                  id="ag-eval-symbol"
                  className="iv-input"
                  type="text"
                  value={symbol}
                  onChange={(e) => setSymbol(e.target.value)}
                  placeholder="BTCUSDT"
                />
              </div>
              <div className="iv-field">
                <label htmlFor="ag-eval-tf">Unité de temps</label>
                <select
                  id="ag-eval-tf"
                  className="iv-input"
                  value={timeframe}
                  onChange={(e) => setTimeframe(e.target.value as (typeof TIMEFRAMES)[number])}
                >
                  {TIMEFRAMES.map((tf) => (
                    <option key={tf} value={tf}>
                      {tf}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <p
              className={`iv-note ag-hint${evalMsg ? (evalMsg.ok ? ' is-ok' : ' is-ko') : ''}`}
              role={evalMsg ? 'status' : undefined}
            >
              {evalMsg
                ? evalMsg.text
                : 'Ève lit les calculs du moteur, interroge JEV avec ses quatre modes et passe le Risk Kernel en essai à blanc. Une dizaine de secondes.'}
            </p>
            <button type="submit" className="iv-btn iv-btn--primary ag-wide" disabled={evaluating || !symbol.trim()}>
              {evaluating ? 'Ève réfléchit…' : 'Évaluer maintenant'}
            </button>
          </form>
        </div>
      </section>

      <section className="iv-card">
        <div className="iv-card-head">
          <div className="iv-card-tabs">
            <span className="iv-card-tab is-on">Surveiller un instrument avec le Copilot d’Ève</span>
          </div>
        </div>
        <div className="iv-card-body">
          <p className="iv-cap ag-sub">paper · une ouverture attend votre confirmation</p>
          <form className="ag-inline" onSubmit={onMission}>
            <input
              className="iv-input"
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              placeholder="BTCUSDT"
              aria-label="Instrument à surveiller"
            />
            <button type="submit" className="iv-btn iv-btn--primary" disabled={missionBusy || !!runtimeError}>
              {missionBusy ? 'Création…' : 'Surveiller'}
            </button>
          </form>
          <div className="iv-row ag-next">
            <span>Prochain contrôle</span>
            <span className={`iv-row-v${nextCheck ? '' : ' muted'}`}>{nextCheck ?? 'Aucune surveillance en cours'}</span>
          </div>
          <p className={`iv-note ag-hint${missionMsg ? (missionMsg.ok ? ' is-ok' : ' is-ko') : ''}`}>
            {missionMsg
              ? missionMsg.text
              : runtimeError
                ? 'Le Copilot est injoignable pour le moment.'
                : 'Le Copilot d’Ève relit l’instrument à intervalles réguliers et vous propose une ouverture paper quand les conditions sont réunies. Rien ne s’ouvre sans votre accord.'}
          </p>
          <Link to="/app/agent" className="ag-link">
            Ouvrir le Copilot →
          </Link>
        </div>
      </section>
    </>
  )

  return (
    <div className="agents-page">
      <header className="iv-ph">
        <div>
          <div className="iv-meta">Ève · l’IA qui décide · paper</div>
          <h1>Ève</h1>
          <p>
            Le moteur calcule et propose un trade. Ève, avec JEV, l’accepte ou le refuse. Le Risk Kernel garde le
            dernier mot. Tout est en paper, jamais d’argent réel.
          </p>
        </div>
        <div className="iv-ph-act">
          {autonomy == null ? (
            <span className="iv-tag is-muted">
              <i className="iv-dot is-off" aria-hidden="true" />
              Pilote : état inconnu
            </span>
          ) : autonomy ? (
            <span className="iv-tag is-mint">
              <i className="iv-dot" aria-hidden="true" />
              Pilote automatique actif
            </span>
          ) : (
            <span className="iv-tag is-amber">
              <i className="iv-dot is-amber" aria-hidden="true" />
              Pilote coupé · moteur seul
            </span>
          )}
          {nextCheck ? <span className="iv-chip">Prochain contrôle · {nextCheck}</span> : null}
          <Link to="/app/settings?section=auto" className="iv-btn">
            Régler ↗
          </Link>
          <Link to="/app/agent" className="iv-btn">
            Ouvrir le Copilot
          </Link>
        </div>
      </header>

      <p className={`ag-pilot${autonomy === false ? ' is-off' : ''}`}>
        <span className="ag-pilot-mark" aria-hidden="true">
          ◆
        </span>
        <span>
          {autonomy == null
            ? 'Impossible de lire l’état du pilote automatique pour le moment.'
            : autonomy
              ? 'Pilote automatique actif : à chaque bougie clôturée où un portefeuille veut ouvrir ou fermer, Ève juge la proposition et l’exécute en paper si elle l’accepte, sans confirmation humaine.'
              : 'Pilote automatique coupé : le moteur ouvre et ferme seul, Ève observe. Vous pouvez quand même lui demander son avis ci-dessous.'}
        </span>
      </p>

      <nav className="ag-steps" aria-label="La chaîne de décision">
        <ol>
          {CHAIN.map((c, i) => {
            const here = c.to === '/app/agents'
            return (
              <li key={c.step} className={here ? 'is-cur' : undefined} aria-current={here ? 'step' : undefined}>
                <span className="ag-step-n">
                  {String(i + 1).padStart(2, '0')} · {c.step}
                </span>
                <p>{c.detail}</p>
                {here ? (
                  <span className="ag-step-link is-here">{c.link}</span>
                ) : (
                  <Link to={c.to} className="ag-step-link">
                    {c.link} ↗
                  </Link>
                )}
              </li>
            )
          })}
        </ol>
        <p className="ag-steps-foot">
          <span className="iv-cap">dans l’ordre où elle s’applique</span>
          <span>
            Les stops et les objectifs ferment les positions sans repasser par Ève. L’arrêt d’urgence, dans le bandeau
            du haut, coupe tout.
          </span>
        </p>
      </nav>

      <EveResults autonomy={autonomy} refreshKey={refreshKey} aside={aside} />

      <EveDossiersPanel autonomy={autonomy} refreshKey={refreshKey} />

      <section className="iv-card ag-modes-card">
        <div className="iv-card-head">
          <div className="iv-card-tabs">
            <span className="iv-card-tab is-on">Comment elle décide</span>
          </div>
          <div className="iv-card-tools">{JEV_PRIMITIVES}</div>
        </div>
        <div className="iv-card-body">
          <p className="iv-note ag-modes-lead">
            Une seule intelligence, quatre modes. Chacun pose à JEV les mêmes trois types de questions ({JEV_PRIMITIVES}),
            puis la synthèse d’Ève tranche : acheter, vendre à découvert, attendre, s’abstenir ou clôturer.
          </p>
          <div className="ag-modes">
            {EVE_MODES.map((m) => (
              <article className={`ag-mode is-${m.id}`} key={m.id}>
                <h3>
                  <span className="ag-ic" aria-hidden="true">
                    {m.icon}
                  </span>
                  {m.name}
                </h3>
                <p>{m.blurb}</p>
                <div className="ag-mode-effect">
                  <span className="iv-cap">Quand il n’est pas d’accord</span>
                  <p>{m.effect}</p>
                </div>
                <button
                  type="button"
                  className="iv-btn iv-btn--sm ag-mode-btn"
                  onClick={() => openFiche({ kind: 'agent', id: `eve:${m.id}` })}
                >
                  Ouvrir la fiche →
                </button>
              </article>
            ))}
          </div>
        </div>
      </section>
    </div>
  )
}
