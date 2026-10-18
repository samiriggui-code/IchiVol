/**
 * Résultats d'Ève (page Ève) : qui a décidé quoi et avec quel résultat, ce que le moteur a proposé et ce
 * qu'Ève a répondu, ses refus suivis à blanc, les refus des filtres d'indicateurs.
 * Le moteur calcule et propose ; Ève (avec JEV) accepte ou refuse ; le Risk Kernel garde le dernier mot.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { DeciderBadge } from '../decider/DeciderBadge'
import {
  DECIDER_EXPLAIN,
  DECIDER_LABEL,
  DECIDERS,
  deciderOf,
  scoreByDecider,
  type Decider,
  type DeciderScore,
} from '../../lib/decider'
import {
  engineProposalFr,
  eveActionFr,
  getEveDecisions,
  JUDGE_LABEL,
  proposalStatusFr,
  proposalVerdict,
  rightness,
  type EveDecision,
  type ProposalVerdict,
} from '../../lib/eveDecisions'
import {
  getShadowStats,
  listPaperPortfolios,
  listPaperPositions,
  type PaperPortfolioRow,
  type PaperPosition,
  type ShadowBucket,
  type ShadowStats,
} from '../../lib/paper'
import { portfolioLabel } from '../../lib/rsPortfolio'
import { fmtEur, fmtPct } from '../../pages/desk/deskFormat'
import './EveResults.css'

type VerdictFilter = 'all' | ProposalVerdict

const VERDICT_FILTERS: Array<{ id: VerdictFilter; label: string }> = [
  { id: 'all', label: 'Tout' },
  { id: 'executed', label: 'Ève et moteur d’accord' },
  { id: 'engine_over_eve', label: 'Moteur contre Ève' },
  { id: 'blocked_by_audit', label: 'Bloquées par l’audit' },
  { id: 'blocked_after', label: 'Bloquées ensuite' },
  { id: 'refused_by_eve', label: 'Refus (ancienne règle)' },
]

const VERDICT_LABEL: Record<ProposalVerdict, string> = {
  executed: 'Exécutée',
  engine_over_eve: 'Ève a refusé, le moteur a tradé',
  blocked_by_audit: 'Bloquée par l’audit',
  refused_by_eve: 'Refusée par Ève',
  blocked_after: 'Acceptée, puis bloquée',
  pending: 'En attente',
}

const FILTER_SOURCE_FR: Record<string, string> = {
  structure: 'Structure (sommets et creux)',
  fibonacci: 'Fibonacci',
  context: 'RSI, flux et régime',
  unknown: 'Autre filtre',
}

/** Ce qu'Ève a répondu à la place d'accepter (motif enregistré sur le trade fantôme). */
function eveRefusalFr(action: string): string {
  const a = action.toUpperCase()
  if (a === 'ABSTAIN') return 'Elle s’est abstenue'
  if (a === 'HOLD') return 'Elle a préféré attendre'
  if (a === 'LONG') return 'Elle voulait acheter (sens inverse)'
  if (a === 'SHORT') return 'Elle voulait vendre à découvert (sens inverse)'
  if (a === 'CLOSE') return 'Elle voulait clôturer'
  return action
}

function fmtR(v: number): string {
  return `${v > 0 ? '+' : ''}${v.toFixed(2).replace('.', ',')} R`
}

/** Ève a-t-elle eu raison de refuser ? Compare ses refus (à blanc) à ses trades acceptés. */
function eveRefusalVerdict(sh: ShadowStats, accepted: DeciderScore): string {
  if (sh.n_closed < 5) return 'Bilan : moins de 5 refus terminés, trop tôt pour juger.'
  const refusedWin = sh.win_rate ?? 0
  const mean = sh.mean_pnl_r ?? 0
  const vs =
    accepted.winRate != null && accepted.trades > 0
      ? ` Ses trades acceptés gagnent ${fmtPct(accepted.winRate, 0, false)} du temps, ses refus auraient gagné ${fmtPct(refusedWin, 0, false)} du temps.`
      : ''
  if (mean < -0.1) return `Bilan : Ève a surtout écarté des trades perdants, ses refus lui ont évité des pertes.${vs}`
  if (mean > 0.1) return `Bilan : Ève a refusé trop de trades qui auraient gagné, elle est trop prudente.${vs}`
  return `Bilan : pas de tendance nette, ses refus auraient autant gagné que perdu.${vs}`
}

/** Ève avait-elle raison de refuser ? Se lit sur les trades que le moteur a pris contre son avis. */
function overEveSentence(s: DeciderScore): string {
  if (s.trades === 0) {
    return s.open > 0
      ? `${s.open} trade${s.open > 1 ? 's' : ''} du moteur contre Ève en cours : pas encore de verdict.`
      : 'Aucun trade du moteur contre Ève clôturé pour l’instant.'
  }
  const few = s.trades < 10 ? ' Moins de 10 trades : trop tôt pour conclure.' : ''
  const head = `${s.losses} refus juste${s.losses > 1 ? 's' : ''} et ${s.wins} refus à tort sur ${s.trades} trades clôturés.`
  if (s.net < 0) return `${head} Ces trades ont perdu ${signedEur(s.net)} : Ève avait plutôt raison de refuser.${few}`
  if (s.net > 0) return `${head} Ces trades ont gagné ${signedEur(s.net)} : Ève refuse trop.${few}`
  return `${head} Ni gain ni perte nette : pas de tendance.${few}`
}

function ShadowTable({
  caption,
  head,
  buckets,
  labelOf,
}: {
  caption: string
  head: string
  buckets: Record<string, ShadowBucket>
  labelOf: (key: string) => string
}) {
  return (
    <div className="dv-table-wrap">
      <table className="dv-table">
        <caption>{caption}</caption>
        <thead>
          <tr>
            <th>{head}</th>
            <th>Refus</th>
            <th>Auraient gagné</th>
            <th>Résultat moyen</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(buckets).map(([key, b]) => (
            <tr key={key}>
              <th scope="row">{labelOf(key)}</th>
              <td data-label="Refus" className="mono">
                {b.n}
              </td>
              <td data-label="Auraient gagné" className="mono">
                {b.win_rate != null ? fmtPct(b.win_rate, 0, false) : '—'}
              </td>
              <td data-label="Résultat moyen" className={`mono ${toneOf(b.mean_pnl_r)}`}>
                {fmtR(b.mean_pnl_r)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted dv-foot">
        R = multiple du risque pris : +1 R veut dire que le trade aurait gagné autant que ce qu’il risquait.
      </p>
    </div>
  )
}

function fmtWhen(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(+d)) return '—'
  return d.toLocaleString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

function signedEur(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${fmtEur(Math.abs(v), 2)}`
}

function toneOf(v: number | null | undefined): string {
  return v == null || v === 0 ? '' : v > 0 ? 'up' : 'down'
}

/** Une phrase qui dit qui s'en sort le mieux, ou pourquoi on ne peut pas encore le dire. */
function verdictSentence(scores: Record<Decider, DeciderScore>): string {
  const eve = scores.eve
  const engine = scores.engine
  if (eve.trades === 0 && engine.trades === 0) return 'Aucun trade clôturé pour l’instant : rien à comparer.'
  if (eve.trades === 0) return 'Ève n’a encore clôturé aucun trade : seul le moteur a un bilan pour l’instant.'
  if (engine.trades === 0) return 'Seule Ève a des trades clôturés : le moteur seul n’a pas de bilan à comparer.'
  const few = eve.trades < 20 || engine.trades < 20
  const leader = eve.net >= engine.net ? 'Ève' : 'Le moteur seul'
  return `${leader} gagne le plus d’argent pour l’instant (${signedEur(eve.net)} pour Ève, ${signedEur(engine.net)} pour le moteur seul).${
    few ? ' Moins de 20 trades d’un côté : trop tôt pour conclure.' : ''
  }`
}

function ScoreTile({ s }: { s: DeciderScore }) {
  return (
    <div className={`dv-tile is-${s.decider}`}>
      <div className="dv-tile-head">
        <DeciderBadge decider={s.decider} />
        <small>{DECIDER_EXPLAIN[s.decider]}</small>
      </div>
      <div className={`dv-tile-net mono ${toneOf(s.net)}`}>{s.trades > 0 ? signedEur(s.net) : '—'}</div>
      <dl>
        <div>
          <dt>Trades clôturés</dt>
          <dd className="mono">{s.trades > 0 ? `${s.trades} · ${s.wins} gagnés / ${s.losses} perdus` : '0'}</dd>
        </div>
        <div>
          <dt>Taux de réussite</dt>
          <dd className="mono">{s.winRate != null ? fmtPct(s.winRate, 0, false) : '—'}</dd>
        </div>
        <div>
          <dt>Gain moyen / perte moyenne</dt>
          <dd className="mono">
            {s.avgWin != null ? signedEur(s.avgWin) : '—'} / {s.avgLoss != null ? signedEur(s.avgLoss) : '—'}
          </dd>
        </div>
        <div>
          <dt>Frais payés</dt>
          <dd className="mono">{s.trades > 0 ? fmtEur(s.fees, 2) : '—'}</dd>
        </div>
        <div>
          <dt>Positions ouvertes</dt>
          <dd className="mono">{s.open}</dd>
        </div>
      </dl>
    </div>
  )
}

export function EveResults({ autonomy, refreshKey = 0 }: { autonomy: boolean | null; refreshKey?: number }) {
  const [positions, setPositions] = useState<PaperPosition[]>([])
  const [portfolios, setPortfolios] = useState<PaperPortfolioRow[]>([])
  const [decisions, setDecisions] = useState<EveDecision[]>([])
  const [shadow, setShadow] = useState<ShadowStats | null>(null)
  const [eveShadow, setEveShadow] = useState<ShadowStats | null>(null)
  const [auditShadow, setAuditShadow] = useState<ShadowStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [errors, setErrors] = useState<string[]>([])
  const [filter, setFilter] = useState<VerdictFilter>('all')
  const [openRow, setOpenRow] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    const errs: string[] = []
    const [pos, pfs, dec, sh, esh, ash] = await Promise.all([
      listPaperPositions().catch(() => {
        errs.push('les trades')
        return [] as PaperPosition[]
      }),
      listPaperPortfolios().catch(() => [] as PaperPortfolioRow[]),
      getEveDecisions(200).catch(() => {
        errs.push('les décisions d’Ève')
        return null
      }),
      getShadowStats(undefined, 'filters').catch(() => {
        errs.push('les trades refusés par les filtres')
        return null
      }),
      getShadowStats(undefined, 'eve').catch(() => {
        errs.push('les refus d’Ève')
        return null
      }),
      getShadowStats(undefined, 'audit').catch(() => {
        errs.push('les blocages de l’audit')
        return null
      }),
    ])
    setPositions(pos)
    setPortfolios(pfs)
    setDecisions(dec?.results ?? [])
    setShadow(sh)
    setEveShadow(esh)
    setAuditShadow(ash)
    setErrors(errs)
    setLoading(false)
  }, [])

  useEffect(() => {
    void load()
  }, [load, refreshKey])

  const bookLabelById = useMemo(
    () => Object.fromEntries(portfolios.map((p) => [p.id, portfolioLabel(p.code, p.label)])),
    [portfolios],
  )
  const bookLabelByCode = useMemo(
    () => Object.fromEntries(portfolios.map((p) => [p.code, portfolioLabel(p.code, p.label)])),
    [portfolios],
  )

  const scores = useMemo(() => scoreByDecider(positions), [positions])

  /** Par livre : bilan clôturé d'Ève et du moteur seul côte à côte. */
  const perBook = useMemo(() => {
    const ids = [...new Set(positions.map((p) => p.portfolio_id ?? ''))]
    return ids
      .map((id) => {
        const own = positions.filter((p) => (p.portfolio_id ?? '') === id)
        return { id, label: bookLabelById[id] ?? 'Portefeuille', scores: scoreByDecider(own) }
      })
      .filter((b) => DECIDERS.some((d) => b.scores[d].trades > 0 || b.scores[d].open > 0))
      .sort((a, b) => a.label.localeCompare(b.label, 'fr'))
  }, [positions, bookLabelById])

  const rows = useMemo(
    () =>
      decisions.flatMap((d) =>
        d.engine_proposals.map((p, i) => ({ key: `${d.id}-${i}`, d, p, verdict: proposalVerdict(p) })),
      ),
    [decisions],
  )
  const counts = useMemo(() => {
    const c: Record<ProposalVerdict, number> = {
      executed: 0,
      engine_over_eve: 0,
      blocked_by_audit: 0,
      refused_by_eve: 0,
      blocked_after: 0,
      pending: 0,
    }
    for (const r of rows) c[r.verdict] += 1
    return c
  }, [rows])
  const shown = filter === 'all' ? rows : rows.filter((r) => r.verdict === filter)

  const latestEveTrades = useMemo(
    () =>
      positions
        .filter((p) => deciderOf(p) === 'eve')
        .sort((a, b) => +new Date(b.entry_time) - +new Date(a.entry_time))
        .slice(0, 6),
    [positions],
  )

  return (
    <div className="dv-page">
      <div className="dv-toolbar">
        <button type="button" onClick={() => void load()} disabled={loading}>
          {loading ? 'Chargement…' : 'Actualiser les résultats'}
        </button>
      </div>

      {errors.length > 0 ? (
        <p className="notice dv-notice">Impossible de charger {errors.join(', ')} pour le moment.</p>
      ) : null}

      <section className="card">
        <div className="card-head">
          <h2>Qui gagne le plus ?</h2>
        </div>
        <div className="card-body">
          <p className="dv-lead">{loading ? 'Chargement…' : verdictSentence(scores)}</p>
          <div className="dv-tiles">
            {DECIDERS.map((d) => (
              <ScoreTile key={d} s={scores[d]} />
            ))}
          </div>
          {perBook.length > 0 ? (
            <div className="dv-table-wrap">
              <table className="dv-table">
                <caption>Par portefeuille : résultat net des trades clôturés (nombre de trades)</caption>
                <thead>
                  <tr>
                    <th>Portefeuille</th>
                    {DECIDERS.map((d) => (
                      <th key={d}>{DECIDER_LABEL[d]}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {perBook.map((b) => (
                    <tr key={b.id}>
                      <th scope="row">{b.label}</th>
                      {DECIDERS.map((d) => {
                        const s = b.scores[d]
                        return (
                          <td key={d} data-label={DECIDER_LABEL[d]}>
                            {s.trades > 0 ? (
                              <span className={`mono ${toneOf(s.net)}`}>
                                {signedEur(s.net)} <small>({s.trades})</small>
                              </span>
                            ) : (
                              <span className="muted">{s.open > 0 ? `${s.open} ouverte${s.open > 1 ? 's' : ''}` : '—'}</span>
                            )}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Ce que le moteur a proposé, et ce qu’Ève a répondu</h2>
        </div>
        <div className="card-body">
          <p className="dv-lead">
            Chaque ligne est une proposition du moteur sur un portefeuille (acheter, vendre à découvert ou
            clôturer). Si Ève n’est pas d’accord, le moteur trade quand même et la réponse d’Ève est gardée : le
            résultat du trade dira qui avait raison. Si Ève est d’accord, l’audit indépendant tranche : il laisse
            passer le trade ou le bloque. Le Risk Kernel garde toujours le dernier mot. Les stops et objectifs
            ferment les positions sans passer par Ève.
          </p>
          <div className="dv-counts">
            <span>
              <b className="mono">{rows.length}</b> propositions
            </span>
            <span>
              <b className="mono">{counts.executed}</b> exécutées
            </span>
            <span>
              <b className="mono">{counts.engine_over_eve}</b> tradées contre l’avis d’Ève
            </span>
            <span>
              <b className="mono">{counts.blocked_by_audit}</b> bloquées par l’audit
            </span>
            {counts.refused_by_eve > 0 ? (
              <span>
                <b className="mono">{counts.refused_by_eve}</b> refusées (ancienne règle)
              </span>
            ) : null}
            <span>
              <b className="mono">{counts.blocked_after}</b> bloquées ensuite (Risk Kernel, données)
            </span>
          </div>
          <div className="dv-filters" role="tablist" aria-label="Filtrer les propositions">
            {VERDICT_FILTERS.map((f) => (
              <button
                key={f.id}
                type="button"
                role="tab"
                aria-selected={filter === f.id}
                className={filter === f.id ? 'active' : ''}
                onClick={() => setFilter(f.id)}
              >
                {f.label}
              </button>
            ))}
          </div>
          {shown.length === 0 ? (
            <p className="muted dv-empty">
              {loading
                ? 'Chargement…'
                : rows.length === 0
                  ? autonomy
                    ? 'Aucune proposition jugée par Ève pour l’instant. Elles apparaissent à chaque clôture de bougie où le moteur veut agir.'
                    : 'L’autonomie d’Ève est coupée : le moteur trade seul, il n’y a donc pas de proposition à juger.'
                  : 'Aucune proposition dans ce filtre.'}
            </p>
          ) : (
            <ol className="dv-proposals">
              {shown.slice(0, 80).map(({ key, d, p, verdict }) => {
                const open = openRow === key
                return (
                  <li key={key} className={`is-${verdict}`}>
                    <button type="button" aria-expanded={open} onClick={() => setOpenRow(open ? null : key)}>
                      <span className="dv-p-when">{fmtWhen(d.created_at)}</span>
                      <span className="dv-p-main">
                        <b>{d.symbol}</b> · {bookLabelByCode[p.portfolio_code] ?? p.portfolio_code}
                      </span>
                      <span className="dv-p-flow">
                        Moteur : <b>{engineProposalFr(p)}</b> → Ève : <b>{eveActionFr(p.eve_action)}</b>
                      </span>
                      <span className={`dv-p-verdict is-${verdict}`}>{VERDICT_LABEL[verdict]}</span>
                    </button>
                    {open ? (
                      <div className="dv-p-detail">
                        <p>
                          <b>Résultat :</b> {proposalStatusFr(p)}.
                        </p>
                        {d.why ? (
                          <p>
                            <b>Pourquoi :</b> {d.why}
                          </p>
                        ) : d.reasoning ? (
                          <p>
                            <b>Raison technique :</b> {d.reasoning}
                          </p>
                        ) : null}
                        {d.opinions && d.opinions.length > 0 ? (
                          <ul className="dv-opinions" aria-label="Avis des juges d’Ève">
                            {d.opinions.map((o) => (
                              <li key={o.who} className={`is-${o.stance}`}>
                                <span className="dv-op-who">{JUDGE_LABEL[o.who]}</span>
                                <span className="dv-op-stance">
                                  {o.stance === 'pour' ? 'Pour' : o.stance === 'contre' ? 'Contre' : 'Neutre'}
                                </span>
                                <span className="dv-op-said">
                                  {o.action ? eveActionFr(o.action) : ''}
                                  {o.action && o.details.length > 0 ? ' · ' : ''}
                                  {o.details.join(' · ')}
                                  {!o.action && o.details.length === 0 ? 'pas de réponse de JEV' : ''}
                                </span>
                              </li>
                            ))}
                          </ul>
                        ) : null}
                        {p.audit ? (
                          <p>
                            <b>Audit indépendant :</b>{' '}
                            {p.audit.verdict === 'block' ? 'a bloqué le trade' : 'a laissé passer le trade'}
                            {p.audit.reason === 'no_audit' ? ' (pas de réponse de l’audit)' : ''}.
                          </p>
                        ) : null}
                        {(() => {
                          const r = rightness(p)
                          return r ? (
                            <p className={`dv-right is-${r.tone}`}>
                              <b>Qui avait raison :</b> {r.text}
                            </p>
                          ) : null
                        })()}
                        <p className="muted">
                          {d.coherence != null
                            ? `Cohérence des indices : ${fmtPct(d.coherence, 0, false)} (qualité et accord des données, ce n’est pas un avis pour ou contre). `
                            : ''}
                          {d.degradation && d.degradation !== 'healthy'
                            ? `JEV dégradé (${d.degradation}) : aucune ouverture possible. `
                            : ''}
                          {d.entry_gate?.decision === 'reject' ? 'La porte d’entrée de JEV a refusé. ' : ''}
                        </p>
                      </div>
                    ) : null}
                  </li>
                )
              })}
            </ol>
          )}
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Ève a-t-elle eu raison de refuser ?</h2>
        </div>
        <div className="card-body">
          <p className="dv-lead">
            Quand Ève refuse, le moteur trade quand même (« Moteur contre Ève »). Chaque trade perdant de ce côté
            est un refus juste d’Ève, chaque trade gagnant un refus à tort.
          </p>
          <p className="dv-lead">{overEveSentence(scores.engine_over_eve)}</p>
          {eveShadow && eveShadow.n_total > 0 ? (
            <>
              <h3 className="dv-sub">Avant ce changement : refus suivis à blanc</h3>
              <p className="muted">
                Avant, un refus d’Ève empêchait le trade. Il était suivi à blanc, sans argent, avec le même stop
                et le même objectif.
              </p>
              <div className="dv-counts">
                <span>
                  <b className="mono">{eveShadow.n_total}</b> refus suivis
                </span>
                <span>
                  <b className="mono">{eveShadow.n_open}</b> encore en cours
                </span>
                <span>
                  <b className="mono">{eveShadow.n_losses}</b> refus justes (auraient perdu)
                </span>
                <span>
                  <b className="mono">{eveShadow.n_wins}</b> refus à tort (auraient gagné)
                </span>
              </div>
              <p className="dv-lead">{eveRefusalVerdict(eveShadow, scores.eve)}</p>
              {Object.keys(eveShadow.by_block_reason ?? {}).length > 0 ? (
                <ShadowTable
                  caption="Selon ce qu’Ève a répondu (refus terminés)"
                  head="Réponse d’Ève"
                  buckets={eveShadow.by_block_reason ?? {}}
                  labelOf={eveRefusalFr}
                />
              ) : null}
            </>
          ) : null}
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>L’audit a-t-il eu raison de bloquer ?</h2>
        </div>
        <div className="card-body">
          <p className="dv-lead">
            Quand le moteur et Ève sont d’accord, l’audit indépendant tranche. S’il bloque, le trade est suivi à
            blanc, sans argent, avec le même stop et le même objectif. S’il touche son stop, l’audit a eu raison.
          </p>
          {!auditShadow || auditShadow.n_total === 0 ? (
            <p className="muted dv-empty">{loading ? 'Chargement…' : 'Aucun blocage de l’audit pour l’instant.'}</p>
          ) : (
            <div className="dv-counts">
              <span>
                <b className="mono">{auditShadow.n_total}</b> blocages suivis
              </span>
              <span>
                <b className="mono">{auditShadow.n_open}</b> encore en cours
              </span>
              <span>
                <b className="mono">{auditShadow.n_losses}</b> blocages justes (auraient perdu)
              </span>
              <span>
                <b className="mono">{auditShadow.n_wins}</b> blocages à tort (auraient gagné)
              </span>
            </div>
          )}
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Trades refusés par les filtres d’indicateurs</h2>
        </div>
        <div className="card-body">
          <p className="dv-lead">
            Dans les portefeuilles à filtres (comme « Tout combiné »), un signal du moteur peut être refusé par la
            structure, Fibonacci ou le RSI avant même d’arriver à Ève. Chaque refus est suivi à blanc : on regarde
            s’il aurait gagné ou perdu. Si les trades refusés auraient surtout gagné, le filtre est trop sévère.
          </p>
          {!shadow || shadow.n_total === 0 ? (
            <p className="muted dv-empty">
              {loading ? 'Chargement…' : 'Aucun trade refusé par un filtre pour l’instant.'}
            </p>
          ) : (
            <>
              <div className="dv-counts">
                <span>
                  <b className="mono">{shadow.n_total}</b> refus suivis
                </span>
                <span>
                  <b className="mono">{shadow.n_open}</b> encore en cours
                </span>
                <span>
                  <b className="mono">{shadow.n_closed}</b> terminés
                </span>
                <span>
                  <b className="mono">{shadow.win_rate != null ? fmtPct(shadow.win_rate, 0, false) : '—'}</b> auraient
                  gagné
                </span>
              </div>
              <p className="dv-lead">
                {shadow.filter_verdict === 'filter_helpful'
                  ? 'Bilan : les filtres ont surtout évité des trades perdants.'
                  : shadow.filter_verdict === 'filter_too_aggressive'
                    ? 'Bilan : les filtres ont surtout bloqué des trades qui auraient gagné. Ils sont trop sévères.'
                    : shadow.filter_verdict === 'inconclusive'
                      ? 'Bilan : pas de tendance nette, les refus auraient autant gagné que perdu.'
                      : 'Bilan : moins de 5 refus terminés, trop tôt pour juger.'}
              </p>
              {Object.keys(shadow.by_block_source ?? {}).length > 0 ? (
                <ShadowTable
                  caption="Par filtre (refus terminés)"
                  head="Filtre"
                  buckets={shadow.by_block_source}
                  labelOf={(k) => FILTER_SOURCE_FR[k] ?? k}
                />
              ) : null}
            </>
          )}
        </div>
      </section>

      {latestEveTrades.length > 0 ? (
        <section className="card">
          <div className="card-head">
            <h2>Derniers trades d’Ève</h2>
          </div>
          <div className="card-body">
            <ul className="dv-eve-trades">
              {latestEveTrades.map((p) => (
                <li key={p.id}>
                  <span>
                    <b>{p.symbol}</b> · {p.direction === 'SHORT' ? 'Vente à découvert' : 'Achat'} ·{' '}
                    {bookLabelById[p.portfolio_id ?? ''] ?? 'Portefeuille'}
                  </span>
                  <span className="muted">{fmtWhen(p.entry_time)}</span>
                  <span className={`mono ${toneOf(p.realized_pnl)}`}>
                    {p.status === 'OPEN' ? 'En cours' : signedEur(p.realized_pnl)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}
    </div>
  )
}
