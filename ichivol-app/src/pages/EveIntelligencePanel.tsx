import { Fragment, useCallback, useEffect, useState } from "react"

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

type PaperAutonomy = {
  autonomy_enabled?: boolean
  env?: string
  default?: boolean
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

const MODES = [
  { id: "analyst", name: "Ève Analyst", mission: "Interprète calculs et scénarios" },
  { id: "challenger", name: "Ève Challenger", mission: "Cherche contradictions et alternatives" },
  { id: "guardian", name: "Ève Guardian", mission: "Risques et anomalies (advisory)" },
  { id: "shadow", name: "Ève Shadow", mission: "Contre-évaluation indépendante (≠ ShadowBroker)" },
] as const

export function EveIntelligencePanel() {
  const [items, setItems] = useState<DossierRow[]>([])
  const [health, setHealth] = useState<Health | null>(null)
  const [calibration, setCalibration] = useState<Calibration | null>(null)
  const [paperAutonomy, setPaperAutonomy] = useState<PaperAutonomy | null>(null)
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [lastSubmit, setLastSubmit] = useState<string>("")
  const [followupInfo, setFollowupInfo] = useState<string>("")
  const [trackedOpen, setTrackedOpen] = useState(0)
  const [openTimelineId, setOpenTimelineId] = useState<string | null>(null)

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
      fetch("/api/engine/eve/paper-autonomy", { credentials: "include", signal }).then(async (r) => {
        if (!r.ok) return null
        return r.json()
      }),
    ])
      .then(([, , h, cal, auto]) => {
        if (controller.signal.aborted) return
        setHealth(h)
        setCalibration(cal)
        setPaperAutonomy(auto)
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(String(e))
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [reloadDossiers, reloadFollowup])

  async function runDrySubmit(dossierId: string) {
    setBusyId(dossierId)
    setLastSubmit("")
    try {
      const r = await fetch(`/api/engine/eve/dossiers/${dossierId}/paper-submit`, {
        method: "POST",
        credentials: "include",
      })
      const data = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(data?.detail || `submit ${r.status}`)
      setLastSubmit(
        `${data.symbol ?? dossierId}: ${data.status ?? "?"} · RK ${data.risk_authorization ?? "—"}`,
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
        `/api/engine/eve/dossiers/${dossierId}/followup?apply=true`,
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
      setFollowupInfo(`Outcomes sync: ${data.updated_count ?? 0} mis à jour`)
      await reloadDossiers()
    } catch (e) {
      setFollowupInfo(String(e))
    } finally {
      setBusyId(null)
    }
  }

  return (
    <section className="card">
      <div className="card-head">
        <h2>Ève Intelligence — Dossiers & modes</h2>
      </div>
      <div className="card-body">
        <p>
          Une seule intelligence Ève. Modes Analyst / Challenger / Guardian / Shadow. Sur
          portefeuilles paper existants : Risk Kernel décide ; autonomie on = Ève peut ouvrir
          / fermer (jamais live).
        </p>

        <div className="statline">
          <span>Provider JEV</span>
          <b>{health?.configured_provider ?? "—"}</b>
        </div>
        <div className="statline">
          <span>Clé présente</span>
          <b>{health?.key_present ? "oui" : "non"}</b>
        </div>
        <div className="statline">
          <span>Shadow enabled</span>
          <b>{health?.shadow_enabled ? "oui" : "non"}</b>
        </div>
        <div className="statline">
          <span>Politique calibration</span>
          <b>{calibration?.policy?.version ?? "—"}</b>
        </div>
        <div className="statline">
          <span>Obs. dossiers / win-rate</span>
          <b>
            {calibration?.observed?.n ?? 0} ·{" "}
            {typeof calibration?.observed?.win_rate === "number"
              ? `${(calibration.observed.win_rate * 100).toFixed(0)}%`
              : "—"}
          </b>
        </div>
        <div className="statline">
          <span>Brier / ECE (observe)</span>
          <b>
            {typeof calibration?.observed?.brier === "number"
              ? calibration.observed.brier.toFixed(3)
              : "—"}{" "}
            /{" "}
            {typeof calibration?.observed?.ece?.ece === "number"
              ? calibration.observed.ece.ece.toFixed(3)
              : "—"}{" "}
            <span style={{ color: "var(--muted)", fontWeight: 400 }}>
              (n={calibration?.observed?.calibration_pairs_n ?? 0}, jamais Platt)
            </span>
          </b>
        </div>
        <div className="statline">
          <span>Propositions calib.</span>
          <b>{calibration?.proposal?.changes?.length ?? 0} (jamais auto)</b>
        </div>
        <div className="statline">
          <span>Paper autonomy (V2)</span>
          <b>{paperAutonomy?.autonomy_enabled ? "oui" : "non (dry-run Risk Kernel)"}</b>
        </div>
        <div className="statline">
          <span>Positions Eve ouvertes (J/K)</span>
          <b>{trackedOpen}</b>
        </div>

        <h3 style={{ marginTop: 16 }}>Modes</h3>
        <ul>
          {MODES.map((m) => {
            const key = `${m.id}_primitives` as keyof NonNullable<
              NonNullable<Calibration["policy"]>["routing"]
            >
            const prims = calibration?.policy?.routing?.[key]
            return (
              <li key={m.id}>
                <b>{m.name}</b> — {m.mission}
                {Array.isArray(prims) ? (
                  <>
                    {" "}
                    · JEV : <code>{prims.length ? prims.join(" + ") : "aucun"}</code>
                  </>
                ) : null}
              </li>
            )
          })}
        </ul>
        <p style={{ fontSize: 12, color: "var(--muted)" }}>
          Routage NOUL/CHOICE/SCORE issu de l’étude{" "}
          <code>GET /api/engine/eve/primitive-study</code> — pas d’appel systématique des 3
          primitives sur chaque mode.
        </p>

        <h3 style={{ marginTop: 16 }}>Suivi (Phase J)</h3>
        <p style={{ fontSize: 12, color: "var(--muted)" }}>
          HOLD / CLOSE / ABSTAIN + audit Shadow (Phase K). Outcomes (PnL net frais)
          séparés de <code>decision_time</code>. Autonomie off → dry-run seulement.
        </p>
        <button type="button" className="ghost" disabled={busyId === "sync"} onClick={() => syncOutcomes()}>
          {busyId === "sync" ? "Sync…" : "Sync outcomes"}
        </button>
        {followupInfo ? (
          <p style={{ fontSize: 12 }} role="status">
            Suivi : {followupInfo}
          </p>
        ) : null}

        <h3 style={{ marginTop: 16 }}>Dossiers récents</h3>
        {lastSubmit ? (
          <p style={{ fontSize: 12 }} role="status">
            Dernier dry-run : {lastSubmit}
          </p>
        ) : null}
        {loading ? (
          <p>Chargement…</p>
        ) : error ? (
          <p role="alert">{error}</p>
        ) : items.length === 0 ? (
          <p>
            Aucun dossier. Déclencher{" "}
            <code>POST /api/engine/eve/evaluate/{"{symbol}"}</code> (persiste + dry-run RK).
          </p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Instrument</th>
                  <th>Baseline</th>
                  <th>Ève</th>
                  <th>Cohérence</th>
                  <th>Exécution</th>
                  <th>Timeline</th>
                  <th>RK</th>
                  <th>Suivi</th>
                </tr>
              </thead>
              <tbody>
                {items.map((d) => {
                  const coh =
                    d.verdict?.coherence_score ?? d.coherence?.score ?? null
                  const timelineOpen = openTimelineId === d.id
                  const timeline = Array.isArray(d.timeline) ? d.timeline : []
                  return (
                    <Fragment key={d.id}>
                      <tr>
                        <td>
                          {d.created_at
                            ? new Date(d.created_at).toLocaleString("fr-FR")
                            : "—"}
                        </td>
                        <td>
                          {d.symbol} · {d.timeframe}
                        </td>
                        <td>{d.baseline_decision ?? "—"}</td>
                      <td>
                        {d.eve_action ?? d.verdict?.action ?? "—"}
                        {d.verdict?.status ? ` (${d.verdict.status})` : ""}
                        {d.decision_time?.degradation?.level &&
                        d.decision_time.degradation.level !== "healthy" ? (
                          <span style={{ marginLeft: 6, fontSize: 11, opacity: 0.8 }}>
                            [{d.decision_time.heuristic?.stand_in
                              ? d.decision_time.heuristic.label ?? "heuristic"
                              : d.decision_time.degradation.level}]
                          </span>
                        ) : null}
                        {d.decision_time?.entry_gate?.decision === "reject" ? (
                          <span style={{ marginLeft: 6, fontSize: 11, opacity: 0.8 }}>
                            [gate:{d.decision_time.entry_gate.reason ?? "reject"}]
                          </span>
                        ) : null}
                        {d.decision_time?.event_radar?.enabled ? (
                          <span style={{ marginLeft: 6, fontSize: 11, opacity: 0.8 }}>
                            [radar:{d.decision_time.event_radar.direction ?? "?"}·
                            {d.decision_time.event_radar.impact ?? "?"}·n=
                            {d.decision_time.event_radar.event_count ?? 0}]
                          </span>
                        ) : null}
                      </td>
                        <td>{typeof coh === "number" ? coh.toFixed(2) : "—"}</td>
                        <td>{d.execution_status}</td>
                        <td>
                          <button
                            type="button"
                            className="ghost"
                            onClick={() =>
                              setOpenTimelineId(timelineOpen ? null : d.id)
                            }
                          >
                            {timelineOpen ? "Masquer" : `Voir (${timeline.length})`}
                          </button>
                        </td>
                        <td>
                          <button
                            type="button"
                            className="ghost"
                            disabled={busyId === d.id}
                            onClick={() => runDrySubmit(d.id)}
                          >
                            {busyId === d.id ? "…" : "Dry-run"}
                          </button>
                        </td>
                        <td>
                          <button
                            type="button"
                            className="ghost"
                            disabled={busyId === `fu-${d.id}`}
                            onClick={() => runFollowup(d.id)}
                          >
                            {busyId === `fu-${d.id}` ? "…" : "Follow-up"}
                          </button>
                        </td>
                      </tr>
                      {timelineOpen ? (
                        <tr>
                          <td colSpan={9}>
                            <ol style={{ margin: 0, paddingLeft: 18, fontSize: 12 }}>
                              {timeline.length === 0 ? (
                                <li>Aucun événement</li>
                              ) : (
                                timeline.map((ev, i) => (
                                  <li key={`${d.id}-ev-${i}`}>
                                    <b>{ev.kind ?? "?"}</b>
                                    {ev.at
                                      ? ` · ${new Date(ev.at).toLocaleString("fr-FR")}`
                                      : ""}
                                    {ev.action ? ` · ${ev.action}` : ""}
                                    {ev.baseline ? ` (baseline ${ev.baseline})` : ""}
                                    {typeof ev.realized_pnl === "number"
                                      ? ` · PnL ${ev.realized_pnl}`
                                      : ""}
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
      </div>
    </section>
  )
}
