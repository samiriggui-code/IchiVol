import { useEffect, useState } from "react"

type Evaluation = {
  id: number
  created_at: string
  symbol: string
  timeframe: string
  original_decision: string | null
  jev_result: string
  latency_ms: number | null
}

type ShadowAnswers = {
  noul: number | null
  choice: string | null
  score: number | null
  primitives: string[]
  raw: Record<string, unknown>
}

function parseAnswers(jevResult: string): ShadowAnswers {
  try {
    const r = JSON.parse(jevResult ?? "{}")
    const answers = (r?.result?.answers ?? {}) as Record<string, { noul?: number; choice?: string; score?: number }>
    const primitives = Array.isArray(r?.primitives) ? (r.primitives as string[]) : []
    const noul = answers?.review?.noul
    const choice = answers?.independent_action?.choice
    const score = answers?.audit_confidence?.score
    return {
      noul: typeof noul === "number" ? noul : null,
      choice: typeof choice === "string" ? choice : null,
      score: typeof score === "number" ? score : null,
      primitives,
      raw: answers as Record<string, unknown>,
    }
  } catch {
    return { noul: null, choice: null, score: null, primitives: [], raw: {} }
  }
}

function fmtNoul(n: number | null): string {
  return n == null ? "—" : `${(n * 100).toFixed(2)} %`
}

function fmtScore(s: number | null): string {
  return s == null ? "—" : String(s)
}

export function EveShadowPanel() {
  const [items, setItems] = useState<Evaluation[]>([])
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const controller = new AbortController()
    fetch("/api/engine/jev-shadow/history?limit=50", {
      credentials: "include",
      signal: controller.signal,
    })
      .then(async (r) => {
        if (!r.ok) throw new Error(`API ${r.status}`)
        return r.json()
      })
      .then((data) => {
        if (!controller.signal.aborted) {
          setItems(Array.isArray(data.results) ? data.results : [])
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(String(e))
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [])

  const latest = items[0] ? parseAnswers(items[0].jev_result) : null

  return (
    <section className="card">
      <div className="card-head">
        <h2>Ève Shadow — Tableau de bord</h2>
      </div>
      <div className="card-body">
        <p>Observation uniquement · Aucun ordre exécuté par Shadow · ≠ ShadowBroker</p>
        <p style={{ fontSize: 12, color: "var(--muted)" }}>
          Primitives JEV : NOUL (cohérence) · CHOICE (action indépendante) · SCORE (confiance
          d’audit)
        </p>
        {items.length > 0 && latest ? (
          <p>
            Dernière évaluation : {items[0].symbol} · {items[0].timeframe} ·{" "}
            {items[0].original_decision ?? "—"} · NOUL : {fmtNoul(latest.noul)} · CHOICE :{" "}
            {latest.choice ?? "—"} · SCORE : {fmtScore(latest.score)} · Latence :{" "}
            {items[0].latency_ms ?? "—"} ms
            {latest.primitives.length ? (
              <>
                {" "}
                · primitives : <code>{latest.primitives.join(" + ")}</code>
              </>
            ) : null}
          </p>
        ) : null}
        {loading ? (
          <p>Chargement…</p>
        ) : error ? (
          <p role="alert">{error}</p>
        ) : items.length === 0 ? (
          <p>Aucune évaluation.</p>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Instrument</th>
                  <th>Décision</th>
                  <th>NOUL</th>
                  <th>CHOICE</th>
                  <th>SCORE</th>
                  <th>Détails</th>
                  <th>Latence</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const a = parseAnswers(item.jev_result)
                  return (
                    <tr key={item.id}>
                      <td>{new Date(item.created_at).toLocaleString("fr-FR")}</td>
                      <td>
                        {item.symbol} · {item.timeframe}
                      </td>
                      <td>{item.original_decision ?? "—"}</td>
                      <td>{fmtNoul(a.noul)}</td>
                      <td>{a.choice ?? "—"}</td>
                      <td>{fmtScore(a.score)}</td>
                      <td>
                        <details>
                          <summary>Voir le détail</summary>
                          <pre>{JSON.stringify(a.raw, null, 2)}</pre>
                        </details>
                      </td>
                      <td>{item.latency_ms == null ? "—" : `${item.latency_ms} ms`}</td>
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
