import { useEffect, useMemo, useState } from 'react'
import {
  fetchCorrelations,
  type CorrelationMatrix,
  type CorrelationMethod,
} from '../lib/correlations'
import { getEngineUniverse } from '../lib/universe'

/** Cap matrice lisible + fetch raisonnable (engine aligne TOUS les timestamps). */
const MAX_CORR_SYMBOLS = 12

function cellColor(v: number | null): string {
  if (v == null || Number.isNaN(v)) return 'transparent'
  const clamped = Math.max(-1, Math.min(1, v))
  if (clamped >= 0) {
    const a = 0.1 + clamped * 0.62
    return `color-mix(in srgb, var(--bull) ${Math.round(a * 100)}%, transparent)`
  }
  const a = 0.1 + Math.abs(clamped) * 0.62
  return `color-mix(in srgb, var(--bear) ${Math.round(a * 100)}%, transparent)`
}

function fmtCorr(v: number | null): string {
  if (v == null || Number.isNaN(v)) return '—'
  return v.toFixed(2)
}

function shortSym(symbol: string): string {
  return symbol.replace(/USDT$/i, '').replace(/USD$/i, '')
}

function peerBarWidth(corr: number | null): string {
  if (corr == null) return '0%'
  return `${Math.round(Math.abs(corr) * 100)}%`
}

/** Heatmap Contexte — co-mouvements crypto, jamais un vote. */
export function CorrelationHeatmap() {
  const [data, setData] = useState<CorrelationMatrix | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [method, setMethod] = useState<CorrelationMethod>('log_returns')
  const [timeframe, setTimeframe] = useState('1h')
  const [focus, setFocus] = useState<string | null>(null)
  const [universeSymbols, setUniverseSymbols] = useState<string[] | null>(null)

  useEffect(() => {
    let cancelled = false
    getEngineUniverse()
      .then((u) => {
        if (cancelled) return
        const crypto = u.instruments
          .filter((i) => i.wired && i.enabled && i.asset_class === 'crypto')
          .map((i) => i.id)
          .slice(0, MAX_CORR_SYMBOLS)
        setUniverseSymbols(crypto)
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Erreur univers')
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!universeSymbols) return
    if (universeSymbols.length < 2) {
      setData({
        timeframe,
        method,
        symbols: universeSymbols,
        sample_size: 0,
        matrix: [],
        skipped: [],
      })
      setLoading(false)
      setError(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)
    fetchCorrelations({ timeframe, method, symbols: universeSymbols })
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
  }, [timeframe, method, universeSymbols])

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
  const emptyMatrix = Boolean(data && !loading && n === 0)

  return (
    <div className="corr-panel">
      <header className="corr-head">
        <div className="corr-head-copy">
          <p className="corr-kicker">Crypto · lecture seule</p>
          <h3>Qui bouge avec qui</h3>
          <p className="muted corr-lede">
            Corrélation de Pearson entre cryptos (même horloge Binance). Sert à
            lire le co-mouvement — pas à voter LONG/SHORT. FX / indices exclus :
            horaires différents → overlap trop faible.
          </p>
        </div>
        <div className="corr-controls" role="group" aria-label="Paramètres corrélation">
          <label className="corr-control">
            <span>TF</span>
            <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
              <option value="15m">15m</option>
              <option value="1h">1h</option>
              <option value="4h">4h</option>
              <option value="1d">1d</option>
            </select>
          </label>
          <label className="corr-control">
            <span>Méthode</span>
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

      <div className="corr-legend" aria-hidden>
        <span>−1</span>
        <div className="corr-legend-bar" />
        <span>0</span>
        <div className="corr-legend-bar is-pos" />
        <span>+1</span>
      </div>

      {loading && (
        <div className="corr-loading" aria-live="polite">
          <div className="corr-skeleton" />
          <div className="corr-skeleton corr-skeleton-short" />
          <p className="muted">
            Calcul Pearson sur ~{universeSymbols?.length ?? '…'} cryptos ({timeframe})…
          </p>
        </div>
      )}
      {error && (
        <div className="banner error" role="alert">
          {error}
        </div>
      )}

      {emptyMatrix && (
        <div className="corr-empty">
          <p>
            Pas assez de barres communes pour une matrice honnête
            {data && data.skipped.length > 0 ? ` (${data.skipped.length} ignorés)` : ''}.
          </p>
          <p className="muted">
            Réessaie en 1h / log returns, ou vérifie que le moteur a des klines crypto.
          </p>
          {data && data.skipped.length > 0 && (
            <details className="corr-skipped">
              <summary>Détail ignorés</summary>
              <ul>
                {data.skipped.map((s) => (
                  <li key={s.symbol}>
                    <span className="mono">{s.symbol}</span> — {s.reason}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {data && !loading && n > 0 && (
        <>
          <p className="corr-meta">
            <span>{data.symbols.length} symboles</span>
            <span className="corr-meta-sep" aria-hidden>
              ·
            </span>
            <span>n={data.sample_size}</span>
            <span className="corr-meta-sep" aria-hidden>
              ·
            </span>
            <span>{data.method === 'log_returns' ? 'log returns' : 'prix'}</span>
            <span className="corr-meta-sep" aria-hidden>
              ·
            </span>
            <span>{data.timeframe}</span>
            {data.skipped.length > 0 && (
              <>
                <span className="corr-meta-sep" aria-hidden>
                  ·
                </span>
                <span>{data.skipped.length} ignorés</span>
              </>
            )}
          </p>

          <div className="corr-focus-block">
            <div className="corr-focus-bar">
              <label className="corr-control">
                <span>Focus</span>
                <select value={focus ?? ''} onChange={(e) => setFocus(e.target.value || null)}>
                  {data.symbols.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
              {focus && (
                <p className="muted corr-focus-hint">
                  Top co-mouvements avec <strong>{shortSym(focus)}</strong>
                </p>
              )}
            </div>

            {focus && focusPeers.length > 0 && (
              <ul className="corr-rank">
                {focusPeers.map((p, idx) => (
                  <li key={p.symbol}>
                    <button
                      type="button"
                      className="corr-rank-row"
                      onClick={() => setFocus(p.symbol)}
                    >
                      <span className="corr-rank-idx">{idx + 1}</span>
                      <span className="corr-rank-sym">{p.symbol}</span>
                      <span className="corr-rank-track" aria-hidden>
                        <span
                          className={`corr-rank-fill ${(p.corr ?? 0) >= 0 ? 'is-pos' : 'is-neg'}`}
                          style={{ width: peerBarWidth(p.corr) }}
                        />
                      </span>
                      <span className={`mono corr-rank-val ${(p.corr ?? 0) >= 0 ? 'up' : 'down'}`}>
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
                        <button
                          type="button"
                          className="ghost corr-row-btn"
                          onClick={() => setFocus(rowSym)}
                        >
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
              Matrice dense masquée ({n} symboles) — le classement Focus ci-dessus suffit.
            </p>
          )}

          {data.skipped.length > 0 && (
            <details className="corr-skipped">
              <summary>Symboles ignorés ({data.skipped.length})</summary>
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
