import { Fragment, useCallback, useEffect, useState } from "react"
import { EVE_MODES, JEV_PRIMITIVES_EXPLAIN } from "../../lib/eveModes"
import { jevServiceLabel } from "../../pages/settings/eveCopy"
import { eveActionFr } from "../../lib/eveDecisions"
import "./EveDossiersPanel.css"

type TimelineEvent = {
  kind?: string
  at?: string | null
  action?: string | null
  baseline?: string | null
  detail?: string | null
  phase?: string | null
  realized_pnl?: number | null
  realized_pnl_pct?: number | null
}

type DossierRow = {
  id: string
  symbol: string
  timeframe: string
  eve_action: string | null
  baseline_decision: string | null
  execution_status: string
  created_at: string | null
  coherence?: { score?: number }
  timeline?: TimelineEvent[]
  decision_time?: {
    event_radar?: {
      enabled?: boolean
      direction?: string | null
      impact?: string | null
      relevance?: string | null
      provider?: string | null
      event_count?: number | null
    } | null
    degradation?: { level?: string; source?: string; mean_confidence?: number | null }
    heuristic?: { label?: string; stand_in?: boolean }
    entry_gate?: { decision?: string; reason?: string; allowed?: boolean }
    engine_proposals?: Array<{
      portfolio_code?: string
      engine_action?: string
      engine_direction?: string | null
      eve_accepts?: boolean
      status?: string | null
      executed?: boolean
    }>
  }
  verdict?: {
    action?: string
    status?: string
    coherence_score?: number | null
    body?: { risk_authorization?: string; paper_submit_status?: string }
  }
}

type Health = {
  shadow_enabled?: boolean
  configured_provider?: string
  key_present?: boolean
  probe?: { ok?: boolean; error?: string }
}

type Calibration = {
  policy?: {
    version?: string
    routing?: {
      analyst_primitives?: string[]
      challenger_primitives?: string[]
      guardian_primitives?: string[]
      shadow_primitives?: string[]
    }
    primitive_study?: {
      cells?: Array<{ mode: string; primitive: string; verdict: string }>
    }
  }
  observed?: {
    n?: number
    abstain_rate?: number | null
    mean_coherence?: number | null
    closed_n?: number
    win_rate?: number | null
    mean_realized_pnl?: number | null
    brier?: number | null
    ece?: { ece?: number; n?: number; applied?: boolean } | null
    calibration_pairs_n?: number
  }
  proposal?: {
    changes?: Array<{ path?: string; reason?: string }>
    applied?: boolean
  }
}

const EXECUTION_LABELS: Record<string, string> = {
  not_executed: "rien d'exécuté",
  opened: "position ouverte",
  already_open: "déjà ouverte",
  closed: "position fermée",
  skipped_abstain: "Ève s'abstient",
  skipped_hold: "Ève garde",
  gate_rejected: "refusé par le contrôle d'entrée",
  risk_kernel_refused: "refusé par le Risk Kernel",
  dry_run_autonomy_off: "essai à blanc (rien ouvert)",
  dry_run_close: "essai à blanc de fermeture",
  close_no_position: "rien à fermer",
  open_refused: "ouverture refusée",
}

/** Ce que le moteur seul aurait fait, en français. */
function baselineFr(d: string | null | undefined): string {
  const v = (d ?? "").toUpperCase()
  if (!v) return "—"
  if (v === "BUY") return "Acheter"
  if (v === "SELL") return "Vendre à découvert"
  if (v === "NO_TRADE" || v === "WAIT" || v === "HOLD") return "Attendre"
  return v
}

function executionLabel(code: string | null | undefined): string {
  if (!code) return "—"
  return EXECUTION_LABELS[code] ?? code
}

function proposalSummary(d: DossierRow): string {
  const props = d.decision_time?.engine_proposals
  if (!Array.isArray(props) || props.length === 0) return "—"
  return props
    .map((p) => {
      const what = p.engine_action === "CLOSE" ? "fermer" : `ouvrir ${p.engine_direction === "SHORT" ? "à la baisse" : "à la hausse"}`
      const eve = p.eve_accepts ? (p.executed ? "Ève accepte, exécuté" : "Ève accepte, non exécuté") : "Ève refuse"
      return `${p.portfolio_code ?? "?"} : ${what} → ${eve}`
    })
    .join(" · ")
}

/** Dossiers d'Ève, suivi des positions et questions posées à JEV. `refreshKey` force un rechargement. */
export function EveDossiersPanel({ autonomy, refreshKey = 0 }: { autonomy: boolean | null; refreshKey?: number }) {
  const [items, setItems] = useState<DossierRow[]>([])
  const [health, setHealth] = useState<Health | null>(null)
  const [calibration, setCalibration] = useState<Calibration | null>(null)
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [lastSubmit, setLastSubmit] = useState<string>("")
  const [followupInfo, setFollowupInfo] = useState<string>("")
  const [trackedOpen, setTrackedOpen] = useState(0)
  const [openTimelineId, setOpenTimelineId] = useState<string | null>(null)
  const [tab, setTab] = useState<"dossiers" | "suivi" | "jev" | "etat">("dossiers")

  const reloadDossiers = useCallback(async (signal?: AbortSignal) => {
    const r = await fetch("/api/engine/eve/dossiers?limit=20", {
      credentials: "include",
      signal,
    })
    if (!r.ok) throw new Error(`dossiers ${r.status}`)
    const data = await r.json()
    setItems(Array.isArray(data?.results) ? data.results : [])
  }, [])

  const reloadFollowup = useCallback(async (signal?: AbortSignal) => {
    const r = await fetch("/api/engine/eve/followup?limit=30", {
      credentials: "include",
      signal,
    })
    if (!r.ok) return
    const data = await r.json()
    setTrackedOpen(Array.isArray(data?.open_eve_positions) ? data.open_eve_positions.length : 0)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    const { signal } = controller
    Promise.all([
      reloadDossiers(signal),
      reloadFollowup(signal),
      fetch("/api/engine/jev-shadow/health", { credentials: "include", signal }).then(async (r) => {
        if (!r.ok) return null
        return r.json()
      }),
      fetch("/api/engine/eve/calibration", { credentials: "include", signal }).then(async (r) => {
        if (!r.ok) return null
        return r.json()
      }),
    ])
      .then(([, , h, cal]) => {
        if (controller.signal.aborted) return
        setHealth(h)
        setCalibration(cal)
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(String(e))
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [reloadDossiers, reloadFollowup, refreshKey])

  async function runDrySubmit(dossierId: string) {
    setBusyId(dossierId)
    setLastSubmit("")
    try {
      const r = await fetch(`/api/engine/eve/dossiers/${dossierId}/paper-submit?execute=false`, {
        method: "POST",
        credentials: "include",
      })
      const data = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(data?.detail || `submit ${r.status}`)
      setLastSubmit(
        `${data.symbol ?? dossierId} : ${executionLabel(data.status)} · Risk Kernel : ${data.risk_authorization ?? "—"}`,
      )
      await reloadDossiers()
    } catch (e) {
      setLastSubmit(String(e))
    } finally {
      setBusyId(null)
    }
  }

  async function runFollowup(dossierId: string) {
    setBusyId(`fu-${dossierId}`)
    setFollowupInfo("")
    try {
      const r = await fetch(
        `/api/engine/eve/dossiers/${dossierId}/followup`,
        { method: "POST", credentials: "include" },
      )
      const data = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(data?.detail || `followup ${r.status}`)
      setFollowupInfo(
        `${data.symbol ?? dossierId}: ${data.proposed_action ?? "?"} — ${data.rationale ?? data.status}`,
      )
      await Promise.all([reloadDossiers(), reloadFollowup()])
    } catch (e) {
      setFollowupInfo(String(e))
    } finally {
      setBusyId(null)
    }
  }

  async function syncOutcomes() {
    setBusyId("sync")
    setFollowupInfo("")
    try {
      const r = await fetch("/api/engine/eve/outcomes/sync", {
        method: "POST",
        credentials: "include",
      })
      const data = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(data?.detail || `sync ${r.status}`)
      setFollowupInfo(`Résultats mis à jour : ${data.updated_count ?? 0} dossier(s)`)
      await reloadDossiers()
    } catch (e) {
      setFollowupInfo(String(e))
    } finally {
      setBusyId(null)
    }
  }

  const tabs: Array<{ id: typeof tab; label: string }> = [
    { id: "dossiers", label: "Dossiers d’Ève" },
    { id: "suivi", label: "Suivi des positions" },
    { id: "jev", label: "Questions posées à JEV" },
    { id: "etat", label: "État d’Ève" },
  ]

  return (
    <section className="iv-card eve-dossiers">
      <div className="iv-card-head">
        <div className="iv-card-tabs" role="tablist" aria-label="Dossiers d’Ève">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              className={`iv-card-tab${tab === t.id ? " is-on" : ""}`}
              aria-selected={tab === t.id}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="iv-card-tools">{items.length} dossiers récents</div>
      </div>

      {tab === "dossiers" ? (
        <>
          <p className="iv-note ed-intro">
            Un dossier est écrit à chaque fois qu'Ève évalue un instrument : ce que le moteur seul aurait
            fait, ce que chaque mode a répondu, le contrôle d'entrée et le Risk Kernel. Avec le pilote
            automatique, un dossier naît à chaque proposition d'un portefeuille et Ève l'accepte ou le refuse
            sans intervention humaine. Tout reste en paper, jamais d'argent réel.
          </p>
          {lastSubmit ? (
            <p className="iv-note ed-status" role="status">
              Dernier essai à blanc : {lastSubmit}
            </p>
          ) : null}
          {loading ? (
            <p className="iv-empty">Chargement…</p>
          ) : error ? (
            <p className="iv-empty is-error" role="alert">
              {error}
            </p>
          ) : items.length === 0 ? (
            <p className="iv-empty">
              Aucun Dossier pour l'instant. Ève en écrit un à chaque fois qu'un portefeuille propose un
              trade (autonomie activée) ou quand on lui demande d'évaluer un instrument.
            </p>
          ) : (
            <div className="iv-table-wrap ed-table-wrap">
              <table className="iv-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Instrument</th>
                    <th>Moteur seul</th>
                    <th>Ève</th>
                    <th>Propositions des portefeuilles</th>
                    <th className="n">Cohérence</th>
                    <th>Résultat</th>
                    <th>Historique</th>
                    <th>Essai à blanc</th>
                    <th>Suivi</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((d) => {
                    const coh = d.verdict?.coherence_score ?? d.coherence?.score ?? null
                    const timelineOpen = openTimelineId === d.id
                    const timeline = Array.isArray(d.timeline) ? d.timeline : []
                    return (
                      <Fragment key={d.id}>
                        <tr>
                          <td className="mono muted">
                            {d.created_at ? new Date(d.created_at).toLocaleString("fr-FR") : "—"}
                          </td>
                          <td className="sym">
                            {d.symbol} <small>{d.timeframe}</small>
                          </td>
                          <td>{baselineFr(d.baseline_decision)}</td>
                          <td>
                            <b className="ed-eve">{eveActionFr(d.eve_action ?? d.verdict?.action)}</b>
                            {d.decision_time?.degradation?.level &&
                            d.decision_time.degradation.level !== "healthy" ? (
                              <span className="iv-tag is-amber ed-flag">
                                {d.decision_time.heuristic?.stand_in
                                  ? d.decision_time.heuristic.label ?? "heuristic"
                                  : d.decision_time.degradation.level}
                              </span>
                            ) : null}
                            {d.decision_time?.entry_gate?.decision === "reject" ? (
                              <span className="iv-tag is-amber ed-flag">
                                refus contrôle d'entrée : {d.decision_time.entry_gate.reason ?? "?"}
                              </span>
                            ) : null}
                            {d.decision_time?.event_radar?.enabled ? (
                              <span className="iv-tag is-muted ed-flag">
                                radar:{d.decision_time.event_radar.direction ?? "?"}·
                                {d.decision_time.event_radar.impact ?? "?"}·n=
                                {d.decision_time.event_radar.event_count ?? 0}
                              </span>
                            ) : null}
                          </td>
                          <td className="ed-props">{proposalSummary(d)}</td>
                          <td className="n">{typeof coh === "number" ? coh.toFixed(2) : "—"}</td>
                          <td>{executionLabel(d.execution_status)}</td>
                          <td>
                            <button
                              type="button"
                              className="iv-btn iv-btn--sm iv-btn--ghost"
                              aria-expanded={timelineOpen}
                              onClick={() => setOpenTimelineId(timelineOpen ? null : d.id)}
                            >
                              {timelineOpen ? "Masquer" : `Voir (${timeline.length})`}
                            </button>
                          </td>
                          <td>
                            <button
                              type="button"
                              className="iv-btn iv-btn--sm"
                              disabled={busyId === d.id}
                              onClick={() => runDrySubmit(d.id)}
                            >
                              {busyId === d.id ? "…" : "Tester sans trader"}
                            </button>
                          </td>
                          <td>
                            <button
                              type="button"
                              className="iv-btn iv-btn--sm"
                              disabled={busyId === `fu-${d.id}`}
                              onClick={() => runFollowup(d.id)}
                            >
                              {busyId === `fu-${d.id}` ? "…" : "Avis d'Ève"}
                            </button>
                          </td>
                        </tr>
                        {timelineOpen ? (
                          <tr className="ed-timeline-row">
                            <td colSpan={10}>
                              <ol className="ed-timeline">
                                {timeline.length === 0 ? (
                                  <li>Aucun événement</li>
                                ) : (
                                  timeline.map((ev, i) => (
                                    <li key={`${d.id}-ev-${i}`}>
                                      <b>{ev.kind ?? "?"}</b>
                                      {ev.at ? ` · ${new Date(ev.at).toLocaleString("fr-FR")}` : ""}
                                      {ev.action ? ` · ${ev.action}` : ""}
                                      {ev.baseline ? ` (baseline ${ev.baseline})` : ""}
                                      {typeof ev.realized_pnl === "number" ? ` · PnL ${ev.realized_pnl}` : ""}
                                      {ev.detail ? ` — ${ev.detail}` : ""}
                                    </li>
                                  ))
                                )}
                              </ol>
                            </td>
                          </tr>
                        ) : null}
                      </Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      ) : null}

      {tab === "suivi" ? (
        <div className="iv-card-body">
          <p className="iv-note ed-p">
            Pour chaque position ouverte, Ève dit si elle la garde, la ferme ou s'abstient. Le résultat
            (gain ou perte, frais déduits) est rangé à part de ce qu'Ève savait au moment de décider.
          </p>
          <div className="iv-row">
            <span>Positions ouvertes par Ève</span>
            <span className="iv-row-v">{trackedOpen}</span>
          </div>
          <div className="ed-actions">
            <button type="button" className="iv-btn" disabled={busyId === "sync"} onClick={() => syncOutcomes()}>
              {busyId === "sync" ? "Mise à jour…" : "Mettre à jour les résultats"}
            </button>
          </div>
          {followupInfo ? (
            <p className="iv-note ed-status" role="status">
              Suivi : {followupInfo}
            </p>
          ) : null}
        </div>
      ) : null}

      {tab === "jev" ? (
        <div className="iv-card-body">
          <p className="iv-note ed-p">
            {JEV_PRIMITIVES_EXPLAIN} Si le service cloud n'a plus de crédit, le service local prend le relais.
          </p>
          {calibration?.policy?.routing ? (
            <div className="iv-table-wrap ed-inset">
              <table className="iv-table is-compact ed-routing">
                <thead>
                  <tr>
                    <th>Mode</th>
                    <th>NOUL</th>
                    <th>CHOICE</th>
                    <th>SCORE</th>
                  </tr>
                </thead>
                <tbody>
                  {EVE_MODES.map((m) => {
                    const key = `${m.id}_primitives` as keyof NonNullable<
                      NonNullable<Calibration["policy"]>["routing"]
                    >
                    const prims = (calibration.policy?.routing?.[key] as string[] | undefined) ?? []
                    const has = (p: string) => prims.includes(p)
                    return (
                      <tr key={m.id}>
                        <td className="sym">Ève {m.name}</td>
                        {(["noul", "choice", "score"] as const).map((p) => (
                          <td key={p} className={has(p) ? "cy" : "dim"}>
                            {has(p) ? "●" : "—"}
                          </td>
                        ))}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="iv-empty">—</p>
          )}
        </div>
      ) : null}

      {tab === "etat" ? (
        <div className="iv-card-body ed-state">
          <div className="iv-row">
            <span>Service JEV</span>
            <span className="iv-row-v">{jevServiceLabel(health?.configured_provider)}</span>
          </div>
          <div className="iv-row">
            <span>Clé JEV présente</span>
            <span className={`iv-row-v ${health?.key_present ? "ok" : "warn"}`}>{health?.key_present ? "oui" : "non"}</span>
          </div>
          <div className="iv-row">
            <span>Shadow JEV activé</span>
            <span className={`iv-row-v ${health?.shadow_enabled ? "ok" : ""}`}>{health?.shadow_enabled ? "oui" : "non"}</span>
          </div>
          <div className="iv-row">
            <span>Version des réglages d'Ève</span>
            <span className="iv-row-v">{calibration?.policy?.version ?? "—"}</span>
          </div>
          <div className="iv-row">
            <span>Dossiers suivis / trades gagnants</span>
            <span className="iv-row-v">
              {calibration?.observed?.n ?? 0} ·{" "}
              {typeof calibration?.observed?.win_rate === "number"
                ? `${(calibration.observed.win_rate * 100).toFixed(0)}%`
                : "—"}
            </span>
          </div>
          <div className="iv-row">
            <span>Justesse des probabilités (Brier / ECE, plus bas = mieux)</span>
            <span className="iv-row-v">
              {typeof calibration?.observed?.brier === "number" ? calibration.observed.brier.toFixed(3) : "—"} /{" "}
              {typeof calibration?.observed?.ece?.ece === "number" ? calibration.observed.ece.ece.toFixed(3) : "—"}{" "}
              <span className="muted">(sur {calibration?.observed?.calibration_pairs_n ?? 0} trades)</span>
            </span>
          </div>
          <div className="iv-row">
            <span>Ajustements de réglages suggérés</span>
            <span className="iv-row-v">{calibration?.proposal?.changes?.length ?? 0} (jamais appliqués tout seuls)</span>
          </div>
          <div className="iv-row">
            <span>Pilote automatique</span>
            <span className="iv-row-v">
              {autonomy == null
                ? "—"
                : autonomy
                  ? "activé : Ève juge chaque proposition du moteur à la clôture de la bougie"
                  : "coupé : le moteur trade seul, Ève observe"}
            </span>
          </div>
          <div className="iv-row">
            <span>Positions ouvertes par Ève</span>
            <span className="iv-row-v">{trackedOpen}</span>
          </div>
        </div>
      ) : null}
    </section>
  )
}
