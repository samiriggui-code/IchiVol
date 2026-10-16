import { useEffect, useState } from "react"

type DossierRow = {
  id: string
  symbol: string
  timeframe: string
  eve_action: string | null
  baseline_decision: string | null
  execution_status: string
  created_at: string | null
  coherence?: { score?: number }
  verdict?: { action?: string; status?: string; coherence_score?: number | null }
}

type Health = {
  shadow_enabled?: boolean
  configured_provider?: string
  key_present?: boolean
  probe?: { ok?: boolean; error?: string }
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
  const [calibration, setCalibration] = useState<{ policy?: { version?: string } } | null>(null)
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const controller = new AbortController()
    const { signal } = controller
    Promise.all([
      fetch("/api/engine/eve/dossiers?limit=20", { credentials: "include", signal }).then(async (r) => {
        if (!r.ok) throw new Error(`dossiers ${r.status}`)
        return r.json()
      }),
      fetch("/api/engine/jev-shadow/health", { credentials: "include", signal }).then(async (r) => {
        if (!r.ok) return null
        return r.json()
      }),
      fetch("/api/engine/eve/calibration", { credentials: "include", signal }).then(async (r) => {
        if (!r.ok) return null
        return r.json()
      }),
    ])
      .then(([dossiers, h, cal]) => {
        if (controller.signal.aborted) return
        setItems(Array.isArray(dossiers?.results) ? dossiers.results : [])
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
  }, [])

  return (
    <section className="card">
      <div className="card-head">
        <h2>Ève Intelligence — Dossiers & modes</h2>
      </div>
      <div className="card-body">
        <p>
          Une seule intelligence Ève. Modes Analyst / Challenger / Guardian / Shadow. Verdicts{" "}
          <b>potentiels</b> uniquement — aucune exécution autonome.
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

        <h3 style={{ marginTop: 16 }}>Modes</h3>
        <ul>
          {MODES.map((m) => (
            <li key={m.id}>
              <b>{m.name}</b> — {m.mission}
            </li>
          ))}
        </ul>

        <h3 style={{ marginTop: 16 }}>Dossiers récents</h3>
        {loading ? (
          <p>Chargement…</p>
        ) : error ? (
          <p role="alert">{error}</p>
        ) : items.length === 0 ? (
          <p>Aucun dossier. Déclencher POST /api/engine/eve/evaluate/{"{symbol}"} (paper non touché).</p>
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
                </tr>
              </thead>
              <tbody>
                {items.map((d) => {
                  const coh =
                    d.verdict?.coherence_score ?? d.coherence?.score ?? null
                  return (
                    <tr key={d.id}>
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
                      </td>
                      <td>{typeof coh === "number" ? coh.toFixed(2) : "—"}</td>
                      <td>{d.execution_status}</td>
                    </tr>
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
