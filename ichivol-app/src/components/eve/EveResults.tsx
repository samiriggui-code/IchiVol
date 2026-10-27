/**
 * Résultats d'Ève (page Ève) : qui a décidé quoi et avec quel résultat, ce que le moteur a proposé et ce
 * qu'Ève a répondu, ses refus suivis à blanc, les refus des filtres d'indicateurs.
 * Le moteur calcule et propose ; Ève (avec JEV) accepte ou refuse ; le Risk Kernel garde le dernier mot.
 */

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
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
  decisionRuleFr,
  engineProposalFr,
  eveActionFr,
  getEveDecisions,
  JUDGE_LABEL,
  proposalStatusFr,
  proposalVerdict,
  rightness,
  type EngineProposalOutcome,
  type EveDecision,
  type Judge,
  type ProposalVerdict,
} from '../../lib/eveDecisions'
import { eveModeById } from '../../lib/eveModes'
import {
  loadAccountLots,
  getShadowStats,
  type PaperPosition,
  type ShadowBucket,
  type ShadowStats,
} from '../../lib/paper'
import { MAIN_PORTFOLIO_CODE, portfolioLabel } from '../../lib/mainPortfolio'
import {
  activeRows,
  assetClassLabel,
  deciderScores,
  getPortfolioBreakdown,
  type PortfolioBreakdown,
} from '../../lib/breakdown'
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

/** Ton de l'étiquette d'issue : menthe = passe, ambre = Ève ou l'audit s'y opposent, rouge = bloquée. */
const VERDICT_TONE: Record<ProposalVerdict, string> = {
  executed: 'is-mint',
  engine_over_eve: 'is-amber',
  blocked_by_audit: 'is-amber',
  refused_by_eve: 'is-muted',
  blocked_after: 'is-sell',
  pending: 'is-muted',
}

const DECIDER_CLASS: Record<Decider, string> = {
  engine: '',
  eve: 'is-eve',
  engine_over_eve: 'is-vs',
  manual: 'is-manual',
}

/** Juge d'Ève → mode d'Ève (pour l'icône). L'audit indépendant est le mode Shadow. */
const JUDGE_MODE: Record<Judge, string> = {
  analyst: 'analyst',
  challenger: 'challenger',
  guardian: 'guardian',
  audit: 'shadow',
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
    <div className="dv-sub-block">
      <div className="iv-cap dv-cap">{caption}</div>
      <div className="iv-table-wrap dv-inset">
        <table className="iv-table is-compact">
          <thead>
            <tr>
              <th>{head}</th>
              <th className="n">Refus</th>
              <th className="n">Auraient gagné</th>
              <th className="n">Résultat moyen</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(buckets).map(([key, b]) => (
              <tr key={key}>
                <td>{labelOf(key)}</td>
                <td className="n">{b.n}</td>
                <td className="n">{b.win_rate != null ? fmtPct(b.win_rate, 0, false) : '—'}</td>
                <td className={`n ${toneOf(b.mean_pnl_r)}`}>{fmtR(b.mean_pnl_r)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="iv-cap dv-foot">
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

/** Couleur d'une action : achat en bleu, vente à découvert en rouge, le reste neutre. */
function actionTone(label: string): string {
  if (label === 'Acheter') return 'is-buy'
  if (label === 'Vendre à découvert') return 'is-sell'
  return 'is-neutral'
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

function DeciderTag({ decider }: { decider: Decider }) {
  return (
    <span className={`iv-decider ${DECIDER_CLASS[decider]}`.trim()} title={DECIDER_EXPLAIN[decider]}>
      <i aria-hidden="true" />
      {DECIDER_LABEL[decider]}
    </span>
  )
}

/** Jauge « combien sur combien », barre rouge pour ce qui a perdu, bleue pour ce qui a gagné. */
function Meter({ label, value, part, total, tone }: { label: string; value: string; part: number; total: number; tone: 'buy' | 'sell' }) {
  const pct = total > 0 ? Math.round((part / total) * 100) : 0
  return (
    <div className="dv-meter">
      <span className="dv-meter-t">{label}</span>
      <span className={`dv-meter-v ${tone === 'sell' ? 'neg' : 'pos'}`}>{value}</span>
      <div className={`iv-bar is-${tone}`}>
        <i style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

type Row = { key: string; d: EveDecision; p: EngineProposalOutcome; verdict: ProposalVerdict }

/** Le dossier d'une proposition, en carte signature : moteur → Ève, pourquoi, les quatre avis, qui avait raison. */
function DossierCard({ row }: { row: Row }) {
  const { d, p, verdict } = row
  const engine = engineProposalFr(p)
  const eve = eveActionFr(p.eve_action)
  const r = rightness(p)
  const decider: Decider | null =
    p.decided_by === 'engine_over_eve' ? 'engine_over_eve' : p.decided_by === 'eve' ? 'eve' : null
  const pnlR = p.result?.status === 'CLOSED' ? (p.result.pnl_r ?? null) : null
  return (
    <>
      <div className="dv-d-top">
        <div className="iv-meta dv-d-meta">
          Dossier #{d.id.slice(0, 8)} · {d.symbol} · {d.timeframe} · {portfolioLabel(p.portfolio_code)} · {fmtWhen(d.created_at)}
          {decisionRuleFr(d.decision_rule) ? ` · règle d’Ève : ${decisionRuleFr(d.decision_rule)}` : ''}
        </div>
        {decider ? <DeciderTag decider={decider} /> : null}
      </div>

      <div className="dv-verdict">
        <span className="dv-v-box">
          <span className="dv-v-k">Moteur</span>
          <b className={actionTone(engine)}>{engine}</b>
        </span>
        <span className="dv-v-ar" aria-hidden="true">
          →
        </span>
        <span className={`dv-v-box is-eve${p.eve_accepts ? ' is-agree' : ' is-refuse'}`}>
          <span className="dv-v-k">Ève</span>
          <b>{eve}</b>
        </span>
        <span className={`iv-tag ${VERDICT_TONE[verdict]}`}>{VERDICT_LABEL[verdict]}</span>
        {d.coherence != null ? <span className="iv-chip">Cohérence {fmtPct(d.coherence, 0, false)}</span> : null}
      </div>

      {d.why ? (
        <>
          <div className="iv-label dv-d-label">Pourquoi</div>
          <p className="dv-why">{d.why}</p>
        </>
      ) : d.reasoning ? (
        <>
          <div className="iv-label dv-d-label">Raison technique</div>
          <p className="dv-why is-tech">{d.reasoning}</p>
        </>
      ) : null}

      {d.opinions && d.opinions.length > 0 ? (
        <ul className="dv-opinions" aria-label="Avis des juges d’Ève">
          {d.opinions.map((o) => (
            <li key={o.who} className={`is-${o.stance}`}>
              <div className="dv-op-head">
                <span className="dv-op-ic" aria-hidden="true">
                  {eveModeById(JUDGE_MODE[o.who])?.icon ?? '◇'}
                </span>
                <span className="dv-op-who">{JUDGE_LABEL[o.who]}</span>
                <span className="dv-op-stance">
                  {o.stance === 'pour' ? 'Pour' : o.stance === 'contre' ? 'Contre' : 'Neutre'}
                </span>
              </div>
              <div className="dv-op-said">
                {o.action ? <b>{eveActionFr(o.action)}</b> : null}
                {o.details.length > 0 ? (
                  <ul>
                    {o.details.map((t, i) => (
                      <li key={i}>{t}</li>
                    ))}
                  </ul>
                ) : null}
                {!o.action && o.details.length === 0 ? <span className="muted">pas de réponse de JEV</span> : null}
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="dv-outcome">
        <div className="iv-label dv-d-label is-mint">Résultat</div>
        {r ? (
          <p className={`dv-right is-${r.tone}`}>
            <b>Qui avait raison :</b> {r.text}
          </p>
        ) : null}
        <div className="dv-outcome-rows">
          <div className="iv-row">
            <span className="muted">Ce qui s’est passé</span>
            <span className="iv-row-v">{proposalStatusFr(p)}</span>
          </div>
          <div className="iv-row">
            <span className="muted">Audit indépendant</span>
            <span className="iv-row-v">
              {p.audit
                ? `${p.audit.verdict === 'block' ? 'a bloqué le trade' : 'a laissé passer le trade'}${
                    p.audit.reason === 'no_audit' ? ' (pas de réponse de l’audit)' : ''
                  }`
                : '—'}
            </span>
          </div>
          <div className="iv-row">
            <span className="muted">
              Résultat{p.result?.kind === 'shadow' ? ' (rejoué sans argent)' : ''}
            </span>
            <span className={`iv-row-v ${toneOf(pnlR)}`}>
              {pnlR != null ? fmtR(pnlR) : p.result && p.result.status !== 'CLOSED' ? 'en cours' : '—'}
            </span>
          </div>
        </div>
      </div>

      <div className="apex-card-foot">
        <span className="apex-card-sig">ichivol</span>
        {d.opinions && d.opinions.length > 0 ? <span className="iv-chip is-cyan">{d.opinions.length} avis</span> : null}
        {d.degradation && d.degradation !== 'healthy' ? (
          <span className="iv-chip is-amber">JEV dégradé ({d.degradation}) : aucune ouverture possible</span>
        ) : null}
        {d.entry_gate?.decision === 'reject' ? (
          <span className="iv-chip is-amber">La porte d’entrée de JEV a refusé</span>
        ) : null}
        {d.coherence != null ? (
          <span className="dv-foot-note">
            Cohérence des indices : {fmtPct(d.coherence, 0, false)} (qualité et accord des données, ce n’est pas un avis
            pour ou contre).
          </span>
        ) : null}
      </div>
    </>
  )
}

export function EveResults({
  autonomy,
  refreshKey = 0,
  aside,
}: {
  autonomy: boolean | null
  refreshKey?: number
  /** Colonne de droite, à côté des propositions (formulaires de la page). */
  aside?: ReactNode
}) {
  const [positions, setPositions] = useState<PaperPosition[]>([])
  const [breakdown, setBreakdown] = useState<PortfolioBreakdown | null>(null)
  const [decisions, setDecisions] = useState<EveDecision[]>([])
  const [shadow, setShadow] = useState<ShadowStats | null>(null)
  const [eveShadow, setEveShadow] = useState<ShadowStats | null>(null)
  const [auditShadow, setAuditShadow] = useState<ShadowStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [errors, setErrors] = useState<string[]>([])
  const [filter, setFilter] = useState<VerdictFilter>('all')
  const [openRow, setOpenRow] = useState<string | null>(null)
  const [scoreTab, setScoreTab] = useState<'decider' | 'asset'>('decider')
  const dossierRef = useRef<HTMLElement | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    const errs: string[] = []
    const [pos, bd, dec, sh, esh, ash] = await Promise.all([
      // Lots du portefeuille unique (ICHIVOL_MAIN_V1) : tous les ouverts + les 200 plus récents.
      loadAccountLots(200).catch(() => {
          errs.push('les trades')
          return [] as PaperPosition[]
        }),
      getPortfolioBreakdown(MAIN_PORTFOLIO_CODE).catch(() => null),
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
    setBreakdown(bd)
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

  /** Bilan par décideur : celui du moteur (/breakdown) ; repli sur les lots chargés si la route ne répond pas. */
  const scores = useMemo(
    () => (breakdown ? deciderScores(breakdown.by_decider) : scoreByDecider(positions)),
    [breakdown, positions],
  )
  const byAsset = useMemo(() => activeRows(breakdown?.by_asset_class ?? []), [breakdown])

  const rows = useMemo<Row[]>(
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
  const selected = shown.find((r) => r.key === openRow) ?? shown[0] ?? null

  function openDossier(key: string) {
    setOpenRow(key)
    dossierRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const latestEveTrades = useMemo(
    () =>
      positions
        .filter((p) => deciderOf(p) === 'eve')
        .sort((a, b) => +new Date(b.entry_time) - +new Date(a.entry_time))
        .slice(0, 6),
    [positions],
  )

  const overEve = scores.engine_over_eve
  const sumWins = overEve.avgWin != null ? overEve.avgWin * overEve.wins : null
  const sumLosses = overEve.avgLoss != null ? overEve.avgLoss * overEve.losses : null
  const auditClosed = auditShadow ? auditShadow.n_wins + auditShadow.n_losses : 0

  return (
    <div className="dv-page">
      {errors.length > 0 ? (
        <p className="iv-empty is-error dv-alert" role="alert">
          Impossible de charger {errors.join(', ')} pour le moment.
        </p>
      ) : null}

      <article className="apex-card dv-dossier" ref={dossierRef} aria-live="polite">
        {selected ? (
          <DossierCard row={selected} />
        ) : (
          <>
            <div className="iv-label">Dossier d’Ève</div>
            <p className="dv-why is-empty">
              {loading
                ? 'Chargement…'
                : rows.length === 0
                  ? autonomy
                    ? 'Aucune proposition jugée par Ève pour l’instant. Elles apparaissent à chaque clôture de bougie où le moteur veut agir.'
                    : 'L’autonomie d’Ève est coupée : le moteur trade seul, il n’y a donc pas de proposition à juger.'
                  : 'Aucune proposition dans ce filtre.'}
            </p>
          </>
        )}
      </article>

      <div className="iv-grid">
        <section className="iv-card iv-glow iv-s6 iv-m-s12">
          <div className="iv-card-head">
            <div className="iv-card-tabs" role="tablist" aria-label="Qui gagne le plus ?">
              <button
                type="button"
                role="tab"
                className={`iv-card-tab${scoreTab === 'decider' ? ' is-on' : ''}`}
                aria-selected={scoreTab === 'decider'}
                onClick={() => setScoreTab('decider')}
              >
                Qui gagne le plus ?
              </button>
              <button
                type="button"
                role="tab"
                className={`iv-card-tab${scoreTab === 'asset' ? ' is-on' : ''}`}
                aria-selected={scoreTab === 'asset'}
                onClick={() => setScoreTab('asset')}
              >
                Par classe d’actifs
              </button>
            </div>
            <div className="iv-card-tools">Trades clôturés · net de frais</div>
          </div>
          <p className="dv-lead">{loading ? 'Chargement…' : verdictSentence(scores)}</p>
          {scoreTab === 'decider' ? (
            <div className="iv-card-body is-flush iv-table-wrap">
              <table className="iv-table">
                <thead>
                  <tr>
                    <th>Décideur</th>
                    <th className="n">Trades</th>
                    <th className="n">Réussite</th>
                    <th className="n">Gain moy.</th>
                    <th className="n">Perte moy.</th>
                    <th className="n">Frais</th>
                    <th className="n">Net</th>
                    <th className="n">Ouvertes</th>
                  </tr>
                </thead>
                <tbody>
                  {DECIDERS.map((d) => {
                    const s = scores[d]
                    return (
                      <tr key={d}>
                        <td>
                          <DeciderTag decider={d} />
                        </td>
                        <td className="n" title={s.trades > 0 ? `${s.wins} gagnés / ${s.losses} perdus` : undefined}>
                          {s.trades}
                        </td>
                        <td className="n">{s.winRate != null ? fmtPct(s.winRate, 0, false) : '—'}</td>
                        <td className="n up">{s.avgWin != null ? signedEur(s.avgWin) : '—'}</td>
                        <td className="n down">{s.avgLoss != null ? signedEur(s.avgLoss) : '—'}</td>
                        <td className="n muted">{s.trades > 0 ? fmtEur(s.fees, 2) : '—'}</td>
                        <td className={`n dv-strong ${toneOf(s.net)}`}>{s.trades > 0 ? signedEur(s.net) : '—'}</td>
                        <td className="n">{s.open}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          ) : byAsset.length > 0 ? (
            <div className="iv-card-body is-flush iv-table-wrap">
              <table className="iv-table">
                <thead>
                  <tr>
                    <th>Classe d’actifs</th>
                    <th className="n">Trades</th>
                    <th className="n">Réussite</th>
                    <th className="n">Frais</th>
                    <th className="n">Net</th>
                    <th className="n">Ouvertes</th>
                  </tr>
                </thead>
                <tbody>
                  {byAsset.map((a) => (
                    <tr key={a.asset_class}>
                      <td className="sym">{assetClassLabel(a)}</td>
                      <td className="n">{a.trades}</td>
                      <td className="n">{a.win_rate != null && a.trades > 0 ? fmtPct(a.win_rate, 0, false) : '—'}</td>
                      <td className="n muted">{a.trades > 0 ? fmtEur(a.fees, 2) : '—'}</td>
                      <td className={`n dv-strong ${toneOf(a.net)}`}>{a.trades > 0 ? signedEur(a.net) : '—'}</td>
                      <td className="n">{a.open}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="iv-empty">
              {loading ? 'Chargement…' : breakdown ? 'Aucun trade pour l’instant.' : 'Bilan par classe indisponible.'}
            </p>
          )}
          <details className="dv-legend">
            <summary>Qui est qui ?</summary>
            <dl>
              {DECIDERS.map((d) => (
                <div key={d}>
                  <dt>
                    <DeciderTag decider={d} />
                  </dt>
                  <dd>{DECIDER_EXPLAIN[d]}</dd>
                </div>
              ))}
            </dl>
          </details>
          <div className="iv-card-foot dv-card-foot">
            Moteur contre Ève · quand Ève refuse, le moteur trade quand même ; quand ils sont d’accord, l’audit
            indépendant tranche
          </div>
        </section>

        <section className="iv-card iv-s6 iv-m-s12">
          <div className="iv-card-head">
            <div className="iv-card-tabs">
              <span className="iv-card-tab is-on">Ève a-t-elle eu raison de refuser ?</span>
            </div>
            <div className="iv-card-tools">
              {overEve.trades} trade{overEve.trades > 1 ? 's' : ''} clôturé{overEve.trades > 1 ? 's' : ''}
            </div>
          </div>
          <div className="iv-card-body">
            <p className="iv-note dv-intro">
              Quand Ève refuse, le moteur trade quand même (« Moteur contre Ève »). Chaque trade perdant de ce côté est
              un refus juste d’Ève, chaque trade gagnant un refus à tort.
            </p>
            <Meter
              label="Refus justes · le trade a perdu"
              value={`${overEve.losses} · ${signedEur(sumLosses)}`}
              part={overEve.losses}
              total={overEve.trades}
              tone="sell"
            />
            <Meter
              label="Refus à tort · le trade a gagné"
              value={`${overEve.wins} · ${signedEur(sumWins)}`}
              part={overEve.wins}
              total={overEve.trades}
              tone="buy"
            />
            <p className={`dv-bilan${overEve.trades > 0 && overEve.net < 0 ? ' is-ok' : ''}`}>
              ◆ {overEveSentence(overEve)}
            </p>
            {eveShadow && eveShadow.n_total > 0 ? (
              <div className="dv-before">
                <div className="iv-cap dv-cap">Avant ce changement : refus suivis à blanc</div>
                <p className="iv-note">
                  Avant, un refus d’Ève empêchait le trade. Il était suivi à blanc, sans argent, avec le même stop et
                  le même objectif.
                </p>
                <div className="dv-counts">
                  <span>
                    <b>{eveShadow.n_total}</b> refus suivis
                  </span>
                  <span>
                    <b>{eveShadow.n_open}</b> encore en cours
                  </span>
                  <span>
                    <b className="neg">{eveShadow.n_losses}</b> refus justes (auraient perdu)
                  </span>
                  <span>
                    <b className="pos">{eveShadow.n_wins}</b> refus à tort (auraient gagné)
                  </span>
                </div>
                <p className="iv-note">{eveRefusalVerdict(eveShadow, scores.eve)}</p>
                {Object.keys(eveShadow.by_block_reason ?? {}).length > 0 ? (
                  <ShadowTable
                    caption="Selon ce qu’Ève a répondu (refus terminés)"
                    head="Réponse d’Ève"
                    buckets={eveShadow.by_block_reason ?? {}}
                    labelOf={eveRefusalFr}
                  />
                ) : null}
              </div>
            ) : null}
          </div>
        </section>
      </div>

      <div className="iv-grid">
        <section className="iv-card iv-s8 iv-m-s12 dv-props">
          <div className="iv-card-head">
            <div className="iv-card-tabs">
              <span className="iv-card-tab is-on">Ce que le moteur a proposé, et ce qu’Ève a répondu</span>
            </div>
            <div className="iv-card-tools">
              {rows.length} proposition{rows.length > 1 ? 's' : ''}
            </div>
          </div>
          <div className="iv-kpis dv-kpis">
            <div className="iv-kpi">
              <div className="iv-kpi-k">Exécutées</div>
              <div className="iv-kpi-v ok">{counts.executed}</div>
            </div>
            <div className="iv-kpi">
              <div className="iv-kpi-k">Contre l’avis d’Ève</div>
              <div className="iv-kpi-v warn">{counts.engine_over_eve}</div>
            </div>
            <div className="iv-kpi">
              <div className="iv-kpi-k">Bloquées par l’audit</div>
              <div className="iv-kpi-v warn">{counts.blocked_by_audit}</div>
            </div>
            <div className="iv-kpi">
              <div className="iv-kpi-k">Bloquées ensuite</div>
              <div className="iv-kpi-v">{counts.blocked_after}</div>
              <div className="iv-kpi-s">Risk Kernel, données</div>
            </div>
            {counts.refused_by_eve > 0 ? (
              <div className="iv-kpi">
                <div className="iv-kpi-k">Refusées (ancienne règle)</div>
                <div className="iv-kpi-v">{counts.refused_by_eve}</div>
              </div>
            ) : null}
          </div>
          <details className="dv-legend dv-howto">
            <summary>Comment lire ce tableau</summary>
            <p className="iv-note">
              Chaque ligne est une proposition du moteur sur le portefeuille (acheter, vendre à découvert ou clôturer).
              Si Ève n’est pas d’accord, le moteur trade quand même et la réponse d’Ève est gardée : le résultat du
              trade dira qui avait raison. Si Ève est d’accord, l’audit indépendant tranche : il laisse passer le trade
              ou le bloque. Le Risk Kernel garde toujours le dernier mot. Les stops et objectifs ferment les positions
              sans passer par Ève.
            </p>
          </details>
          <div className="dv-toolbar">
            <div className="iv-seg dv-seg" role="tablist" aria-label="Filtrer les propositions">
              {VERDICT_FILTERS.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  role="tab"
                  aria-selected={filter === f.id}
                  className={filter === f.id ? 'is-on' : ''}
                  onClick={() => setFilter(f.id)}
                >
                  {f.label}
                </button>
              ))}
            </div>
            <button type="button" className="iv-btn iv-btn--sm" onClick={() => void load()} disabled={loading}>
              {loading ? 'Chargement…' : 'Actualiser les résultats'}
            </button>
          </div>
          {shown.length === 0 ? (
            <p className="iv-empty">
              {loading
                ? 'Chargement…'
                : rows.length === 0
                  ? autonomy
                    ? 'Aucune proposition jugée par Ève pour l’instant. Elles apparaissent à chaque clôture de bougie où le moteur veut agir.'
                    : 'L’autonomie d’Ève est coupée : le moteur trade seul, il n’y a donc pas de proposition à juger.'
                  : 'Aucune proposition dans ce filtre.'}
            </p>
          ) : (
            <div className="iv-card-body is-flush iv-table-wrap dv-props-wrap">
              <table className="iv-table dv-props-table">
                <thead>
                  <tr>
                    <th>Heure</th>
                    <th>Actif</th>
                    <th>Moteur → Ève</th>
                    <th className="n">Cohérence</th>
                    <th>Issue</th>
                    <th className="n">Résultat</th>
                    <th>Dossier</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.slice(0, 80).map((row) => {
                    const { key, d, p, verdict } = row
                    const isSel = selected?.key === key
                    const engine = engineProposalFr(p)
                    const pnlR = p.result?.status === 'CLOSED' ? (p.result.pnl_r ?? null) : null
                    return (
                      <tr key={key} className={isSel ? 'is-selected' : undefined} onClick={() => setOpenRow(key)}>
                        <td className="mono muted">{fmtWhen(d.created_at)}</td>
                        <td className="sym">{d.symbol}</td>
                        <td className="dv-flow">
                          <span className={actionTone(engine)}>{engine}</span>
                          <span className="dv-flow-ar" aria-label="puis Ève :">
                            →
                          </span>
                          <b className={p.eve_accepts ? 'is-agree' : 'is-refuse'}>{eveActionFr(p.eve_action)}</b>
                          {decisionRuleFr(d.decision_rule) ? (
                            <small className="muted"> · {decisionRuleFr(d.decision_rule)}</small>
                          ) : null}
                        </td>
                        <td className="n">{d.coherence != null ? fmtPct(d.coherence, 0, false) : '—'}</td>
                        <td>
                          <span className={`iv-tag ${VERDICT_TONE[verdict]}`}>{VERDICT_LABEL[verdict]}</span>
                        </td>
                        <td className={`n ${toneOf(pnlR)}`}>
                          {pnlR != null ? fmtR(pnlR) : p.result && p.result.status !== 'CLOSED' ? 'en cours' : '—'}
                        </td>
                        <td>
                          <button
                            type="button"
                            className="iv-btn iv-btn--sm iv-btn--ghost"
                            aria-pressed={isSel}
                            onClick={(e) => {
                              e.stopPropagation()
                              openDossier(key)
                            }}
                          >
                            {isSel ? 'Affiché ↑' : 'Voir ↑'}
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
        <div className="iv-s4 iv-m-s12 dv-aside">{aside}</div>
      </div>

      <div className="iv-grid">
        <section className="iv-card iv-s6 iv-m-s12">
          <div className="iv-card-head">
            <div className="iv-card-tabs">
              <span className="iv-card-tab is-on">L’audit a-t-il eu raison de bloquer ?</span>
            </div>
            {auditShadow ? <div className="iv-card-tools">{auditShadow.n_total} blocages suivis</div> : null}
          </div>
          <div className="iv-card-body">
            <p className="iv-note dv-intro">
              Quand le moteur et Ève sont d’accord, l’audit indépendant tranche. S’il bloque, le trade est suivi à
              blanc, sans argent, avec le même stop et le même objectif. S’il touche son stop, l’audit a eu raison.
            </p>
            {!auditShadow || auditShadow.n_total === 0 ? (
              <p className="iv-empty">{loading ? 'Chargement…' : 'Aucun blocage de l’audit pour l’instant.'}</p>
            ) : (
              <>
                <Meter
                  label="Blocages justes · auraient perdu"
                  value={String(auditShadow.n_losses)}
                  part={auditShadow.n_losses}
                  total={auditClosed}
                  tone="sell"
                />
                <Meter
                  label="Blocages à tort · auraient gagné"
                  value={String(auditShadow.n_wins)}
                  part={auditShadow.n_wins}
                  total={auditClosed}
                  tone="buy"
                />
                <div className="dv-counts">
                  <span>
                    <b>{auditShadow.n_total}</b> blocages suivis
                  </span>
                  <span>
                    <b>{auditShadow.n_open}</b> encore en cours
                  </span>
                </div>
              </>
            )}
          </div>
        </section>

        <section className="iv-card iv-s6 iv-m-s12">
          <div className="iv-card-head">
            <div className="iv-card-tabs">
              <span className="iv-card-tab is-on">Trades refusés par les filtres d’indicateurs</span>
            </div>
          </div>
          <div className="iv-card-body">
            <p className="iv-note dv-intro">
              Dans l’ancien portefeuille à filtres « Tout combiné » (retiré le 27/10/2026, historique conservé), un signal du
              moteur pouvait être refusé par la structure, Fibonacci ou le RSI avant même d’arriver à Ève. Chaque refus est suivi à blanc : on regarde
              s’il aurait gagné ou perdu. Si les trades refusés auraient surtout gagné, le filtre est trop sévère.
            </p>
            {!shadow || shadow.n_total === 0 ? (
              <p className="iv-empty">{loading ? 'Chargement…' : 'Aucun trade refusé par un filtre pour l’instant.'}</p>
            ) : (
              <>
                <div className="dv-counts">
                  <span>
                    <b>{shadow.n_total}</b> refus suivis
                  </span>
                  <span>
                    <b>{shadow.n_open}</b> encore en cours
                  </span>
                  <span>
                    <b>{shadow.n_closed}</b> terminés
                  </span>
                  <span>
                    <b>{shadow.win_rate != null ? fmtPct(shadow.win_rate, 0, false) : '—'}</b> auraient gagné
                  </span>
                </div>
                <p className={`dv-bilan${shadow.filter_verdict === 'filter_helpful' ? ' is-ok' : ''}`}>
                  ◆{' '}
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
      </div>

      {latestEveTrades.length > 0 ? (
        <section className="iv-card dv-last">
          <div className="iv-card-head">
            <div className="iv-card-tabs">
              <span className="iv-card-tab is-on">Derniers trades d’Ève</span>
            </div>
          </div>
          <div className="iv-card-body is-flush iv-table-wrap">
            <table className="iv-table is-compact">
              <thead>
                <tr>
                  <th>Actif</th>
                  <th>Sens</th>
                  <th>Entrée</th>
                  <th className="n">Résultat</th>
                </tr>
              </thead>
              <tbody>
                {latestEveTrades.map((p) => (
                  <tr key={p.id}>
                    <td className="sym">{p.symbol}</td>
                    <td>
                      <span className={`iv-side ${p.direction === 'SHORT' ? 'is-short' : 'is-long'}`}>
                        {p.direction === 'SHORT' ? 'Vente à découvert' : 'Achat'}
                      </span>
                    </td>
                    <td className="mono muted">{fmtWhen(p.entry_time)}</td>
                    <td className={`n ${p.status === 'OPEN' ? 'muted' : toneOf(p.realized_pnl)}`}>
                      {p.status === 'OPEN' ? 'En cours' : signedEur(p.realized_pnl)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  )
}
