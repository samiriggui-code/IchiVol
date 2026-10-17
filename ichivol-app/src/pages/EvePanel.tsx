/**
 * Fiche Ève — Dossier IchiVol (engine /api/engine/eve/*). Lecture seule : aucune action ici ne déclenche
 * d'appel JEV ni d'ordre ; seule la boucle paper du moteur appelle JEV, une fois par bougie clôturée.
 */

import { useCallback, useEffect, useState } from 'react'
import './EvePanel.css'

type Endpoint = { role: string; provider: string; host: string; model: string; key_set: boolean }
type DossierRow = {
  id: string
  created_at: string
  portfolio_code: string
  symbol: string
  timeframe: string
  price: number | null
  holding: string | null
  battery: string
  engine_decision: string | null
  engine_action: string
  eve_action: string
  eve_label: string
  decisive: boolean
  coherence: number | null
  p_up: number | null
  executed_action: string
  decided_by: string
  executed_result: string | null
  provider: string | null
  model: string | null
  jev_ok: boolean
  jev_error: string | null
  reused: boolean
  reasons: string[]
  outcome_bars: number | null
  outcome_return: number | null
}
type DossierDetail = DossierRow & {
  state: unknown
  state_chars: number | null
  questions: Record<string, { type: string }> | null
  answers: Record<string, Record<string, unknown>> | null
  labels_fr: Record<string, string>
  usage: Record<string, number> | null
  latency_ms: number | null
  jev_errors: string[]
}
type Status = {
  enabled: boolean
  execution: boolean
  portfolios: { code: string; label: string; source: string }[]
  endpoints: Endpoint[]
  calls_today: number
  daily_cap: number
  dossiers_total: number
  last_call: DossierRow | null
  outcome_bars: number
}
type Summary = { n: number; mean: number | null; std: number | null; total: number | null; hit_rate: number | null; in_market: number }
type Calibration = {
  days: number
  dossiers: number
  outcome_bars: number
  calibration: {
    n: number
    brier: number | null
    brier_base_rate: number | null
    base_rate_up: number | null
    ece: number | null
    reliability: { lo: number; hi: number; n: number; mean_p: number; freq_up: number }[]
  }
  comparison: { eve_when_decisive: Summary; engine_alone: Summary; circuit: Summary }
  decided_by: Record<string, number>
  agreement: { agree: number; disagree: number }
}

const ACTION_FR: Record<string, string> = {
  LONG: 'Acheter',
  SHORT: 'Vendre à découvert',
  ABSTAIN: 'Ne rien faire',
  HOLD: 'Garder',
  CLOSE: 'Liquider',
  UNAVAILABLE: 'Pas de réponse',
}
const DECIDED_FR: Record<string, string> = {
  eve: 'Ève a décidé',
  eve_indecise: 'Ève indécise : abstention / maintien',
  observation: 'Observation seule (exécution coupée)',
}
const RESULT_FR: Record<string, string> = {
  opened: 'Position ouverte',
  held: 'Position gardée',
  none: 'Rien exécuté',
}
const PROVIDER_FR: Record<string, string> = {
  typesafe: 'JEV hébergé (TypeSafe)',
  openrouter: 'JEV via OpenRouter',
  jevos: 'jevos4 local',
  custom: 'JEV (adresse personnalisée)',
}

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const r = await fetch(url, { credentials: 'include', signal })
  if (!r.ok) throw new Error(`API ${r.status}`)
  return (await r.json()) as T
}

const pct = (v: number | null | undefined, d = 1) => (typeof v === 'number' ? `${(v * 100).toFixed(d)} %` : '—')
const signedPct = (v: number | null | undefined) =>
  typeof v === 'number' ? `${v > 0 ? '+' : ''}${(v * 100).toFixed(2)} %` : '—'
const num = (v: number | null | undefined, d = 3) => (typeof v === 'number' ? v.toFixed(d) : '—')
const when = (iso: string) => new Date(iso).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })

function resultFr(r: string | null): string {
  if (!r) return '—'
  if (r.startsWith('closed_')) return `Position fermée (${r.slice(7)})`
  return RESULT_FR[r] ?? r
}

function answerFr(name: string, a: Record<string, unknown>): string {
  if (a.type === 'noul' && typeof a.noul === 'number') return `Oui à ${pct(a.noul)}`
  if (a.type === 'choice') {
    const probs = (a.probabilities ?? {}) as Record<string, number>
    const list = Object.entries(probs)
      .sort((x, y) => y[1] - x[1])
      .map(([k, v]) => `${k} ${pct(v, 0)}`)
      .join(' · ')
    return `${String(a.choice)} (confiance ${num(a.confidence as number, 2)}) — ${list}`
  }
  if (a.type === 'score' && typeof a.score === 'number') {
    const max = name === 'position_risk' ? 3 : 4
    return `${a.score.toFixed(2)} / ${max} (confiance ${num(a.confidence as number, 2)})`
  }
  return JSON.stringify(a)
}

function ReliabilityChart({ bins }: { bins: Calibration['calibration']['reliability'] }) {
  const W = 260
  const H = 160
  const pad = 24
  const x = (v: number) => pad + v * (W - pad * 2)
  const y = (v: number) => H - pad - v * (H - pad * 2)
  return (
    <svg className="eve-rel" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Courbe de fiabilité">
      <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} className="eve-rel-diag" />
      <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(0)} className="eve-rel-axis" />
      <line x1={x(0)} y1={y(0)} x2={x(0)} y2={y(1)} className="eve-rel-axis" />
      {bins.map((b) => (
        <circle key={b.lo} cx={x(b.mean_p)} cy={y(b.freq_up)} r={Math.min(9, 3 + Math.sqrt(b.n))} className="eve-rel-dot">
          <title>{`P annoncée ${pct(b.mean_p, 0)} · hausse réelle ${pct(b.freq_up, 0)} · ${b.n} cas`}</title>
        </circle>
      ))}
      <text x={x(0.5)} y={H - 4} textAnchor="middle">P(hausse) annoncée par JEV</text>
      <text x={8} y={y(0.5)} transform={`rotate(-90 8 ${y(0.5)})`} textAnchor="middle">hausse réelle</text>
    </svg>
  )
}

function DossierView({ id, onClose }: { id: string; onClose: () => void }) {
  const [d, setD] = useState<DossierDetail | null>(null)
  const [err, setErr] = useState('')
  useEffect(() => {
    const c = new AbortController()
    getJson<DossierDetail>(`/api/engine/eve/dossiers/${id}`, c.signal)
      .then(setD)
      .catch((e) => !c.signal.aborted && setErr(String(e)))
    return () => c.abort()
  }, [id])
  if (err) return <p role="alert">{err}</p>
  if (!d) return <p className="eve-muted">Chargement du dossier…</p>
  return (
    <div className="eve-dossier">
      <div className="eve-row-head">
        <h3>
          {d.symbol} · {d.timeframe} · {d.portfolio_code}
        </h3>
        <button type="button" onClick={onClose}>
          Retour à la liste
        </button>
      </div>
      <p className="eve-muted">
        Bougie clôturée du {when(d.created_at)} · prix {d.price ?? '—'} ·{' '}
        {d.holding ? `position ${d.holding} détenue` : 'aucune position'}
      </p>
      <dl className="eve-dl">
        <dt>Le moteur proposait</dt>
        <dd>{ACTION_FR[d.engine_action] ?? d.engine_action} ({d.engine_decision ?? '—'})</dd>
        <dt>Ève</dt>
        <dd>
          {ACTION_FR[d.eve_action] ?? d.eve_action}
          {d.decisive ? '' : ' (pas assez sûre pour agir)'}
        </dd>
        <dt>Exécuté</dt>
        <dd>
          {ACTION_FR[d.executed_action] ?? d.executed_action} · {DECIDED_FR[d.decided_by] ?? d.decided_by} ·{' '}
          {resultFr(d.executed_result)}
        </dd>
        <dt>Indice de cohérence</dt>
        <dd>{num(d.coherence, 2)} (accord entre les jugements d'Ève, ce n'est pas une probabilité)</dd>
        <dt>Résultat observé</dt>
        <dd>
          {d.outcome_return == null
            ? `en attente (mesuré ${d.outcome_bars ?? 4} bougies après la décision)`
            : `${signedPct(d.outcome_return)} sur ${d.outcome_bars} bougies`}
        </dd>
      </dl>
      <h4>Pourquoi</h4>
      <ul className="eve-reasons">
        {(d.reasons ?? []).map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ul>
      <h4>Réponses de JEV</h4>
      <p className="eve-muted">
        {d.provider ? PROVIDER_FR[d.provider] ?? d.provider : 'Aucune source n’a répondu'} · {d.model ?? '—'} ·{' '}
        {d.latency_ms != null ? `${Math.round(d.latency_ms)} ms` : '—'}
        {d.usage?.input_tokens ? ` · ${d.usage.input_tokens} jetons lus` : ''}
        {d.reused ? ' · appel partagé avec un autre portefeuille Ève' : ''}
        {d.jev_errors?.length ? ` · erreurs : ${d.jev_errors.join(', ')}` : ''}
      </p>
      {d.answers && Object.keys(d.answers).length ? (
        <table className="eve-table">
          <tbody>
            {Object.entries(d.answers).map(([k, a]) => (
              <tr key={k}>
                <th scope="row">{d.labels_fr?.[k] ?? k}</th>
                <td>{answerFr(k, a)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p>JEV n'a donné aucune réponse exploitable ({d.jev_error ?? 'inconnu'}).</p>
      )}
      <details>
        <summary>Calculs du moteur envoyés à JEV ({d.state_chars ?? '—'} caractères)</summary>
        <pre className="eve-pre">{JSON.stringify(d.state, null, 1)}</pre>
      </details>
      <details>
        <summary>Questions posées (NOUL / CHOICE / SCORE)</summary>
        <pre className="eve-pre">{JSON.stringify(d.questions, null, 1)}</pre>
      </details>
    </div>
  )
}

function SummaryRow({ label, s }: { label: string; s: Summary }) {
  return (
    <tr>
      <th scope="row">{label}</th>
      <td>{s.n}</td>
      <td>{s.in_market}</td>
      <td className={s.mean != null && s.mean > 0 ? 'up' : s.mean != null && s.mean < 0 ? 'down' : ''}>
        {signedPct(s.mean)}
      </td>
      <td>{pct(s.hit_rate, 0)}</td>
      <td>{pct(s.std, 2)}</td>
    </tr>
  )
}

export function EvePanel() {
  const [status, setStatus] = useState<Status | null>(null)
  const [cal, setCal] = useState<Calibration | null>(null)
  const [rows, setRows] = useState<DossierRow[]>([])
  const [portfolio, setPortfolio] = useState('')
  const [open, setOpen] = useState<string | null>(null)
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(
    async (signal?: AbortSignal) => {
      setLoading(true)
      try {
        const q = portfolio ? `portfolio=${encodeURIComponent(portfolio)}` : ''
        const [s, c, l] = await Promise.all([
          getJson<Status>('/api/engine/eve/status', signal),
          getJson<Calibration>(`/api/engine/eve/calibration?${q}`, signal),
          getJson<{ results: DossierRow[] }>(`/api/engine/eve/dossiers?limit=100&${q}`, signal),
        ])
        setStatus(s)
        setCal(c)
        setRows(l.results ?? [])
        setErr('')
      } catch (e) {
        if (!signal?.aborted) setErr(String(e))
      } finally {
        if (!signal?.aborted) setLoading(false)
      }
    },
    [portfolio],
  )

  useEffect(() => {
    const c = new AbortController()
    void load(c.signal)
    return () => c.abort()
  }, [load])

  if (open) {
    return (
      <div className="eve-panel">
        <DossierView id={open} onClose={() => setOpen(null)} />
      </div>
    )
  }

  const cmp = cal?.comparison
  return (
    <div className="eve-panel">
      <section className="eve-block">
        <h3>Comment Ève trade</h3>
        <p>
          Le moteur Python calcule tout (Ichimoku, RVOL, structure, ATR, contexte, preuves, multi-horizons) et
          présente ces calculs à Ève à chaque bougie clôturée. Ève pose ses questions à JEV : <b>Analyst</b> (quel
          trade, quel régime, quelle qualité), <b>Challenger</b> (y a-t-il une contradiction), <b>Guardian</b>{' '}
          (risque d'une position ouverte), <b>Shadow</b> (le moteur a-t-il raison). Le code transforme ces réponses en
          Verdict avec des seuils fixes.
        </p>
        <p>
          Ève décide seule dans ses propres portefeuilles paper : acheter, garder, liquider ou ne rien faire. Quand
          elle n'est pas assez sûre, elle s'abstient (ou garde ce qu'elle détient) : le moteur ne décide jamais à sa
          place. Le Risk Kernel et le kill switch gardent le dernier mot sur chaque ouverture, le stop et l'objectif
          restent actifs. La baseline IchiVol reste la référence « moteur seul ». Aucun ordre réel.
        </p>
      </section>

      {err ? <p role="alert">{err}</p> : null}
      {loading && !status ? <p className="eve-muted">Chargement…</p> : null}

      {status ? (
        <section className="eve-block">
          <h3>État</h3>
          <dl className="eve-dl">
            <dt>Ève</dt>
            <dd>
              {status.enabled ? 'active' : 'coupée (EVE_ENABLED=false)'} ·{' '}
              {status.execution ? 'exécute ses décisions (V2)' : 'dossiers seulement, sans exécution (V1)'}
            </dd>
            {status.endpoints.map((e) => (
              <span key={e.role + e.host} className="eve-contents">
                <dt>{e.role === 'primary' ? 'JEV principal' : 'JEV de secours'}</dt>
                <dd>
                  {PROVIDER_FR[e.provider] ?? e.provider} · {e.model}
                  {e.provider === 'jevos' ? '' : e.key_set ? ' · clé configurée' : ' · clé absente'}
                </dd>
              </span>
            ))}
            {status.endpoints.length === 0 ? (
              <>
                <dt>JEV</dt>
                <dd>Aucune source configurée : Ève s'abstient sur chaque bougie.</dd>
              </>
            ) : null}
            <dt>Appels JEV hébergé aujourd'hui</dt>
            <dd>
              {status.calls_today} / {status.daily_cap} (au-delà, le compte JEV s'abstient jusqu'à minuit UTC ;
              jevos4 n'a pas de plafond)
            </dd>
            <dt>Dossiers enregistrés</dt>
            <dd>{status.dossiers_total}</dd>
            <dt>Portefeuilles d'Ève</dt>
            <dd>{status.portfolios.map((p) => p.label).join(' · ') || '—'}</dd>
          </dl>
        </section>
      ) : null}

      {status ? (
        <div className="eve-filter">
          <label>
            Portefeuille{' '}
            <select value={portfolio} onChange={(e) => setPortfolio(e.target.value)}>
              <option value="">Tous les portefeuilles Ève</option>
              {status.portfolios.map((p) => (
                <option key={p.code} value={p.code}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      ) : null}

      {cal && cmp ? (
        <section className="eve-block">
          <h3>Ève contre le moteur ({cal.days} derniers jours)</h3>
          <p className="eve-muted">
            Rendement mesuré {cal.outcome_bars} bougies après chaque décision, sur les mêmes bougies, hors frais.
            « Écart type » = la variance des résultats : plus il est grand, plus les résultats sont dispersés.
          </p>
          {cal.dossiers === 0 ? (
            <p>Pas encore de résultat observé : il faut {cal.outcome_bars} bougies après les premières décisions.</p>
          ) : (
            <div className="eve-scroll">
              <table className="eve-table">
                <thead>
                  <tr>
                    <th scope="col">Qui décide</th>
                    <th scope="col">Bougies</th>
                    <th scope="col">En position</th>
                    <th scope="col">Moyenne</th>
                    <th scope="col">Gagnantes</th>
                    <th scope="col">Écart type</th>
                  </tr>
                </thead>
                <tbody>
                  <SummaryRow label="Ève, quand elle tranche" s={cmp.eve_when_decisive} />
                  <SummaryRow label="Moteur seul" s={cmp.engine_alone} />
                  <SummaryRow label="Ce qui a été exécuté" s={cmp.circuit} />
                </tbody>
              </table>
            </div>
          )}
          <p className="eve-muted">
            Ève et le moteur d'accord {cal.agreement.agree} fois, en désaccord {cal.agreement.disagree} fois.
          </p>
          <h3>Calibration de JEV</h3>
          <p className="eve-muted">
            JEV annonce une probabilité de hausse. Si elle est bien calibrée, « 70 % » doit monter 7 fois sur 10 : les
            points doivent suivre la diagonale. Brier : plus bas = mieux, à comparer au score obtenu en annonçant
            toujours la fréquence moyenne. Ce n'est pas un réentraînement du modèle, seulement une mesure.
          </p>
          {cal.calibration.n === 0 ? (
            <p>Pas encore assez de décisions mesurées.</p>
          ) : (
            <div className="eve-cal">
              <ReliabilityChart bins={cal.calibration.reliability} />
              <dl className="eve-dl">
                <dt>Décisions mesurées</dt>
                <dd>{cal.calibration.n}</dd>
                <dt>Brier JEV</dt>
                <dd>{num(cal.calibration.brier)}</dd>
                <dt>Brier « fréquence moyenne »</dt>
                <dd>{num(cal.calibration.brier_base_rate)}</dd>
                <dt>Erreur de calibration (ECE)</dt>
                <dd>{num(cal.calibration.ece)}</dd>
                <dt>Hausse réelle moyenne</dt>
                <dd>{pct(cal.calibration.base_rate_up, 0)}</dd>
              </dl>
            </div>
          )}
        </section>
      ) : null}

      <section className="eve-block">
        <div className="eve-row-head">
          <h3>Dossiers IchiVol</h3>
          <button type="button" onClick={() => void load()}>
            Actualiser
          </button>
        </div>
        <p className="eve-muted">Un dossier par bougie clôturée et par portefeuille Ève. Touchez une ligne pour le détail.</p>
        {rows.length === 0 && !loading ? (
          <p>Aucun dossier pour l'instant : Ève décide à la prochaine bougie clôturée.</p>
        ) : (
          <div className="eve-scroll">
            <table className="eve-table eve-list">
              <thead>
                <tr>
                  <th scope="col">Date</th>
                  <th scope="col">Marché</th>
                  <th scope="col">Moteur</th>
                  <th scope="col">Ève</th>
                  <th scope="col">Exécuté</th>
                  <th scope="col">Après</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} onClick={() => setOpen(r.id)} tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && setOpen(r.id)}>
                    <td>{when(r.created_at)}</td>
                    <td>
                      {r.symbol}
                      <span className="eve-sub">{r.portfolio_code}</span>
                    </td>
                    <td>{ACTION_FR[r.engine_action] ?? r.engine_action}</td>
                    <td>
                      {ACTION_FR[r.eve_action] ?? r.eve_action}
                      <span className="eve-sub">{r.provider ? PROVIDER_FR[r.provider] ?? r.provider : 'sans réponse'}</span>
                    </td>
                    <td>
                      {ACTION_FR[r.executed_action] ?? r.executed_action}
                      <span className="eve-sub">{resultFr(r.executed_result)}</span>
                    </td>
                    <td className={r.outcome_return != null ? (r.outcome_return > 0 ? 'up' : r.outcome_return < 0 ? 'down' : '') : ''}>
                      {signedPct(r.outcome_return)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}
