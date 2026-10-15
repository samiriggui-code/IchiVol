import { useEffect, useState } from "react"

type Evaluation = { id: number; created_at: string; symbol: string; timeframe: string; original_decision: string | null; jev_result: string; latency_ms: number | null }

export function EveShadowPanel() {
  const [items, setItems] = useState<Evaluation[]>([])
  const latestScore = (() => { try { const r = JSON.parse(items[0]?.jev_result ?? "{}"); const n = r?.result?.answers?.review?.noul; return typeof n === "number" ? (n * 100).toFixed(2) + " %" : "—" } catch { return "—" } })()
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    const controller = new AbortController()
    fetch("/api/engine/jev-shadow/history?limit=50", { credentials: "include", signal: controller.signal })
      .then(async r => { if (!r.ok) throw new Error(`API ${r.status}`); return r.json() })
      .then(data => { if (!controller.signal.aborted) setItems(Array.isArray(data.results) ? data.results : []) })
      .catch(e => { if (!controller.signal.aborted) setError(String(e)) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [])
  return <section className="card"><div className="card-head"><h2>Ève Shadow — Tableau de bord</h2></div><div className="card-body"><p>Observation uniquement · Aucun ordre exécuté par Shadow</p>{items.length > 0 ? <p>Dernière évaluation : {items[0].symbol} · {items[0].timeframe} · {items[0].original_decision ?? "—"} · NOUL : {latestScore} · Latence : {items[0].latency_ms ?? "—"} ms</p> : null}{loading ? <p>Chargement…</p> : error ? <p role="alert">{error}</p> : items.length === 0 ? <p>Aucune évaluation.</p> : <div style={{overflowX:"auto"}}><table><thead><tr><th>Date</th><th>Instrument</th><th>Décision</th><th>Cohérence</th><th>Détails</th><th>Latence</th></tr></thead><tbody>{items.map(item => { let result: any = {}; try { result = JSON.parse(item.jev_result) } catch {} const value = result?.result?.answers?.review?.noul; return <tr key={item.id}><td>{new Date(item.created_at).toLocaleString("fr-FR")}</td><td>{item.symbol} · {item.timeframe}</td><td><details><summary>Voir le détail</summary><pre>{JSON.stringify(result?.result?.answers ?? {}, null, 2)}</pre></details></td><td>{item.original_decision ?? "—"}</td><td>{typeof value === "number" ? `${(value*100).toFixed(2)} %` : "—"}</td><td>{item.latency_ms == null ? "—" : `${item.latency_ms} ms`}</td></tr> })}</tbody></table></div>}</div></section>
}
