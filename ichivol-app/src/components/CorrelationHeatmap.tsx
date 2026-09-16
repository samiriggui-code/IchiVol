import { useEffect, useMemo, useState } from 'react'
import {
  fetchCorrelations,
  type CorrelationMatrix,
  type CorrelationMethod,
} from '../lib/correlations'

function cellColor(v: number | null): string {
  if (v == null || Number.isNaN(v)) return 'transparent'
  const clamped = Math.max(-1, Math.min(1, v))
  if (clamped >= 0) {
    const a = 0.08 + clamped * 0.55
    return `color-mix(in srgb, var(--bull) ${Math.round(a * 100)}%, transparent)`
  }
  const a = 0.08 + Math.abs(clamped) * 0.55
  return `color-mix(in srgb, var(--bear) ${Math.round(a * 100)}%, transparent)`
}

function fmtCorr(v: number | null): string {
  if (v == null || Number.isNaN(v)) return '—'
  return v.toFixed(2)
}

function shortSym(symbol: string): string {
  return symbol.replace(/USDT$/i, '').replace(/USD$/i, '')
}

/** Heatmap dense — « qu’est-ce qui bouge avec X ? » (pas un vote). */
export function CorrelationHeatmap() {
  const [data, setData] = useState<CorrelationMatrix | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [method, setMethod] = useState<CorrelationMethod>('log_returns')
  const [timeframe, setTimeframe] = useState('1h')
  const [focus, setFocus] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchCorrelations({ timeframe, method })
      .then((m) => {
        if (cancelled) return
        setData(m)
        setFocus((prev) => (prev && m.symbols.includes(prev) ? prev : (m.symbols[0] ?? null)))
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Erreur corrélations')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [timeframe, method])

  const focusPeers = useMemo(() => {
    if (!data || !focus) return []
    const i = data.symbols.indexOf(focus)
    if (i < 0) return []
    return data.symbols
      .map((sym, j) => ({
        symbol: sym,
        corr: data.matrix[i]?.[j] ?? null,
      }))
      .filter((r) => r.symbol !== focus && r.corr != null)
      .sort((a, b) => Math.abs(b.corr ?? 0) - Math.abs(a.corr ?? 0))
      .slice(0, 8)
  }, [data, focus])

  const n = data?.symbols.length ?? 0
  const showFullGrid = n > 0 && n <= 16

  return (
    <div className="corr-panel">
      <header className="panel-head corr-head">
        <div>
          <h3>Corrélations</h3>
          <p className="muted corr-lede">
            Lecture seule — « qui bouge avec qui » sur les rendements. Ne vote pas LONG/SHORT.
          </p>
        </div>
        <div className="corr-controls">
          <label className="corr-control">
            <span className="muted">TF</span>
            <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
              <option value="15m">15m</option>
              <option value="1h">1h</option>
              <option value="4h">4h</option>
              <option value="1d">1d</option>
            </select>
          </label>
          <label className="corr-control">
            <span className="muted">Méthode</span>
            <select
              value={method}
              onChange={(e) => setMethod(e.target.value as CorrelationMethod)}
            >
              <option value="log_returns">log returns</option>
              <option value="price">prix</option>
            </select>
          </label>
        </div>
      </header>

      {loading && <p className="muted">Calcul corrélations…</p>}
      {error && (
        <div className="banner error" role="alert">
          {error}
        </div>
      )}

      {data && !loading && (
        <>
          <p className="corr-meta muted">
            {data.symbols.length} symboles · n={data.sample_size} barres · {data.method} ·{' '}
            {data.timeframe}
            {data.skipped.length > 0 && ` · ${data.skipped.length} skip`}
          </p>

          <div className="corr-focus">
            <label className="corr-control">
              <span className="muted">Focus</span>
              <select value={focus ?? ''} onChange={(e) => setFocus(e.target.value || null)}>
                {data.symbols.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
            {focus && focusPeers.length > 0 && (
              <ul className="corr-peers">
                {focusPeers.map((p) => (
                  <li key={p.symbol}>
                    <button
                      type="button"
                      className="ghost corr-peer-btn"
                      onClick={() => setFocus(p.symbol)}
                    >
                      <span>{p.symbol}</span>
                      <span
                        className={`mono ${(p.corr ?? 0) >= 0 ? 'up' : 'down'}`}
                        title="corrélation"
                      >
                        {fmtCorr(p.corr)}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {showFullGrid ? (
            <div className="corr-grid-wrap">
              <table className="corr-grid" aria-label="Matrice de corrélation">
                <thead>
                  <tr>
                    <th scope="col" />
                    {data.symbols.map((s) => (
                      <th key={s} scope="col" title={s}>
                        {shortSym(s)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.symbols.map((rowSym, i) => (
                    <tr key={rowSym} className={rowSym === focus ? 'is-focus' : undefined}>
                      <th scope="row" title={rowSym}>
                        <button type="button" className="ghost corr-row-btn" onClick={() => setFocus(rowSym)}>
                          {shortSym(rowSym)}
                        </button>
                      </th>
                      {data.symbols.map((colSym, j) => {
                        const v = data.matrix[i]?.[j] ?? null
                        return (
                          <td
                            key={colSym}
                            style={{ background: cellColor(v) }}
                            title={`${rowSym} × ${colSym} = ${fmtCorr(v)}`}
                          >
                            <span className="mono corr-cell">{fmtCorr(v)}</span>
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted corr-grid-hint">
              Matrice complète masquée ({n} symboles) — utilise le focus + top corrélés ci-dessus.
            </p>
          )}

          {data.skipped.length > 0 && (
            <details className="corr-skipped">
              <summary className="muted">Symboles ignorés ({data.skipped.length})</summary>
              <ul>
                {data.skipped.map((s) => (
                  <li key={s.symbol}>
                    <span className="mono">{s.symbol}</span> — {s.reason}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
    </div>
  )
}
