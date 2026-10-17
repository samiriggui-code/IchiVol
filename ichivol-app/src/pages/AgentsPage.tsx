/**
 * Ève — la page de l'IA qui décide : son état, ses quatre modes, ses résultats face au moteur seul,
 * ses dossiers, et une évaluation à la demande. Le Copilot (son chat) a sa propre page.
 * Fiches des modes = FicheHost / `?fiche=agent:eve:<mode>`.
 */

import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { EveDossiersPanel } from '../components/eve/EveDossiersPanel'
import { EveResults } from '../components/eve/EveResults'
import { createAgentMission, fetchAgents, fmtDue, type AgentsListResponse } from '../lib/agentsRuntime'
import { evaluateWithEve, getPaperAutonomy } from '../lib/eveApi'
import { eveActionFr } from '../lib/eveDecisions'
import { EVE_MODES, JEV_PRIMITIVES } from '../lib/eveModes'
import { useFicheNav } from '../lib/useFicheNav'
import './AgentsPage.css'

type BadgeTone = 'green' | 'amber' | 'red' | 'gray' | ''

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

function badge(text: string, tone: BadgeTone = 'gray'): ReactNode {
  return <span className={`tag ${tone}`.trim()}>{text}</span>
}

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

  return (
    <div className="agents-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">09 / ICHIVOL WORKSPACE</div>
          <h1>Ève</h1>
          <p className="subtitle">
            Le moteur calcule et propose un trade. Ève, avec JEV, l’accepte ou le refuse. Le Risk Kernel garde le
            dernier mot. Tout est en paper, jamais d’argent réel.
          </p>
        </div>
        <div className="actions">
          {autonomy == null
            ? badge('PILOTE : ÉTAT INCONNU', 'gray')
            : autonomy
              ? badge('PILOTE AUTOMATIQUE ACTIF', 'green')
              : badge('PILOTE COUPÉ · MOTEUR SEUL', 'amber')}
          <Link to="/app/settings?section=auto" className="link">
            Régler ↗
          </Link>
        </div>
      </div>

      <div className="notice blue">
        ⬡{' '}
        <span>
          {autonomy == null
            ? 'Impossible de lire l’état du pilote automatique pour le moment.'
            : autonomy
              ? 'Pilote automatique actif : à chaque bougie clôturée où un portefeuille veut ouvrir ou fermer, Ève juge la proposition et l’exécute en paper si elle l’accepte, sans confirmation humaine.'
              : 'Pilote automatique coupé : le moteur ouvre et ferme seul, Ève observe. Vous pouvez quand même lui demander son avis ci-dessous.'}
        </span>
      </div>

      <div className="agents-section-head">
        <h2>Comment elle décide</h2>
        <p>
          Une seule intelligence, quatre modes. Chacun pose à JEV les mêmes trois types de questions ({JEV_PRIMITIVES}),
          puis la synthèse d’Ève tranche : acheter, vendre à découvert, attendre, s’abstenir ou clôturer.
        </p>
      </div>

      <div className="grid eve-modes">
        {EVE_MODES.map((m) => (
          <section className="card agent-card" key={m.id}>
            {badge('MODE', m.id === 'guardian' ? 'amber' : 'green')}
            <div className="agent-icon">{m.icon}</div>
            <h2>Ève {m.name}</h2>
            <p>{m.blurb}</p>
            <div className="statline">
              <span>Quand il n’est pas d’accord</span>
              <b>{m.effect}</b>
            </div>
            <button type="button" onClick={() => openFiche({ kind: 'agent', id: `eve:${m.id}` })}>
              Ouvrir la fiche →
            </button>
          </section>
        ))}
      </div>

      <section className="card">
        <div className="card-head">
          <h2>Demander l’avis d’Ève</h2>
          <small>crée un dossier, n’ouvre rien</small>
        </div>
        <div className="card-body">
          <form className="toolbar eve-evaluate" onSubmit={onEvaluate}>
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              placeholder="BTCUSDT"
              aria-label="Instrument à évaluer"
            />
            <select value={timeframe} onChange={(e) => setTimeframe(e.target.value as (typeof TIMEFRAMES)[number])} aria-label="Unité de temps">
              {TIMEFRAMES.map((tf) => (
                <option key={tf} value={tf}>
                  {tf}
                </option>
              ))}
            </select>
            <button type="submit" className="primary" disabled={evaluating || !symbol.trim()}>
              {evaluating ? 'Ève réfléchit…' : 'Évaluer maintenant'}
            </button>
          </form>
          <p className="eve-hint" role={evalMsg ? 'status' : undefined} style={evalMsg ? { color: evalMsg.ok ? 'var(--green)' : 'var(--red)' } : undefined}>
            {evalMsg
              ? evalMsg.text
              : 'Ève lit les calculs du moteur, interroge JEV avec ses quatre modes et passe le Risk Kernel en essai à blanc. Une dizaine de secondes.'}
          </p>
        </div>
      </section>

      <EveResults autonomy={autonomy} refreshKey={refreshKey} />

      <EveDossiersPanel autonomy={autonomy} refreshKey={refreshKey} />

      <section className="card">
        <div className="card-head">
          <h2>La chaîne de décision</h2>
          <small>dans l’ordre où elle s’applique</small>
        </div>
        <div className="card-body">
          <ol className="eve-chain">
            {CHAIN.map((c, i) => (
              <li key={c.step}>
                <span className="eve-chain-n mono">{String(i + 1).padStart(2, '0')}</span>
                <div>
                  <b>{c.step}</b>
                  <p>{c.detail}</p>
                </div>
                {c.to !== '/app/agents' ? (
                  <Link to={c.to} className="link">
                    {c.link} ↗
                  </Link>
                ) : (
                  <span className="muted">{c.link}</span>
                )}
              </li>
            ))}
          </ol>
          <p className="eve-hint">
            Les stops et les objectifs ferment les positions sans repasser par Ève. L’arrêt d’urgence, dans le bandeau du
            haut, coupe tout.
          </p>
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Surveiller un instrument avec le Copilot d’Ève</h2>
          <small>paper · une ouverture attend votre confirmation</small>
        </div>
        <div className="card-body">
          <form className="toolbar" onSubmit={onMission} style={{ flexWrap: 'wrap' }}>
            <input
              type="text"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              placeholder="BTCUSDT"
              aria-label="Instrument à surveiller"
              style={{ minWidth: 140 }}
            />
            <button type="submit" className="primary" disabled={missionBusy || !!runtimeError}>
              {missionBusy ? 'Création…' : 'Surveiller'}
            </button>
            <Link to="/app/agent" className="link">
              Ouvrir le Copilot →
            </Link>
          </form>
          <div className="statline">
            <span>Prochain contrôle</span>
            <b>
              {watcher?.nextTaskDue
                ? `${watcher.nextTaskSymbol ? `${watcher.nextTaskSymbol} · ` : ''}${fmtDue(watcher.nextTaskDue)}`
                : 'Aucune surveillance en cours'}
            </b>
          </div>
          <p className="eve-hint" style={missionMsg ? { color: missionMsg.ok ? 'var(--green)' : 'var(--red)' } : undefined}>
            {missionMsg
              ? missionMsg.text
              : runtimeError
                ? 'Le Copilot est injoignable pour le moment.'
                : 'Le Copilot d’Ève relit l’instrument à intervalles réguliers et vous propose une ouverture paper quand les conditions sont réunies. Rien ne s’ouvre sans votre accord.'}
          </p>
        </div>
      </section>
    </div>
  )
}
