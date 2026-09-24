import { useEffect, useMemo, useState } from 'react'
import { Tag } from './maquette'
import {
  fetchCorrelations,
  type CorrelationMatrix,
  type CorrelationMethod,
} from '../lib/correlations'
import { CLASS_LABELS, getEngineUniverse, type EngineAssetClass } from '../lib/universe'

const MAX_CORR_SYMBOLS = 12

function fmtCorr(v: number | null): string {
  if (v == null || Number.isNaN(v)) return '—'
  return v.toFixed(2)
}

function shortSym(symbol: string): string {
  return symbol.replace(/USDT$/i, '').replace(/USD$/i, '')
}

function defaultTf(assetClass: EngineAssetClass): string {
  return assetClass === 'crypto' ? '1h' : '1d'
}

type Props = {
  assetClass: EngineAssetClass
}

/** Heatmap — co-mouvements dans une classe d’actifs. Lecture seule. */
export function CorrelationHeatmap({ assetClass }: Props) {
  const [data, setData] = useState<CorrelationMatrix | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [method, setMethod] = useState<CorrelationMethod>('log_returns')
  const [timeframe, setTimeframe] = useState(() => defaultTf(assetClass))
  const [focus, setFocus] = useState<string | null>(null)
  const [universeSymbols, setUniverseSymbols] = useState<string[] | null>(null)

  useEffect(() => {
    setTimeframe(defaultTf(assetClass))
    setFocus(null)
  }, [assetClass])

  useEffect(() => {
    let cancelled = false
    getEngineUniverse()
      .then((u) => {
        if (cancelled) return
        const list = u.instruments
          .filter((i) => i.wired && i.enabled && i.asset_class === assetClass)
          .map((i) => i.id)
          .slice(0, MAX_CORR_SYMBOLS)
        setUniverseSymbols(list)
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
  }, [assetClass])

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
  const emptyMatrix = Boolean(data && !loading && (n < 2 || data.matrix.length === 0))
  const classLabel = CLASS_LABELS[assetClass]

  return (
    <section className="card">
      <div className="card-head">
        <h2>Corrélations · {classLabel}</h2>
        <Tag tone="gray">LIVE</Tag>
      </div>
      <div className="card-body">
        <div className="toolbar" role="group" aria-label="Paramètres corrélation">
          <label className="field" style={{ marginBottom: 0, minWidth: 100 }}>
            <span style={{ fontSize: 11 }}>TF</span>
            <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)}>
              <option value="15m">15m</option>
              <option value="1h">1h</option>
              <option value="4h">4h</option>
              <option value="1d">1d</option>
            </select>
          </label>
          <label className="field" style={{ marginBottom: 0, minWidth: 140 }}>
            <span style={{ fontSize: 11 }}>Méthode</span>
            <select
              value={method}
              onChange={(e) => setMethod(e.target.value as CorrelationMethod)}
            >
              <option value="log_returns">rendements</option>
              <option value="price">prix</option>
            </select>
          </label>
        </div>

      {loading && (
        <p style={{ fontSize: 12, color: 'var(--muted)' }}>
          Calcul sur {universeSymbols?.length ?? '…'} symboles ({timeframe})…
        </p>
      )}
      {error && (
        <div className="notice" role="alert">
          <span>△</span>
          <span>{error}</span>
        </div>
      )}

      {emptyMatrix && (
        <p style={{ fontSize: 12, color: 'var(--muted)' }}>
          Pas assez de paires avec un historique commun
          {data && data.skipped.length > 0 ? ` (${data.skipped.length} ignorés)` : ''}.
        </p>
      )}

      {data && !loading && n >= 2 && data.matrix.length > 0 && (
        <>
          {data.symbols.length <= 5 && (
            <>
              <div className="chart-labels">
                {data.symbols.map((s) => (
                  <span key={s}>{shortSym(s)}</span>
                ))}
              </div>
              <div className="heatmap">
                {data.symbols.flatMap((_, i) =>
                  data.symbols.map((colSym, j) => {
                    const v = data.matrix[i]?.[j] ?? null
                    const strong = v != null && v > 0.85
                    return (
                      <div key={`${i}-${colSym}`} className={strong ? 'strong' : undefined}>
                        {fmtCorr(v)}
                      </div>
                    )
                  }),
                )}
              </div>
            </>
          )}
          {data.symbols.length > 5 && showFullGrid && (
            <div className="table-wrap">
              <table aria-label="Matrice de corrélation">
                <thead>
                  <tr>
                    <th />
                    {data.symbols.map((s) => (
                      <th key={s}>{shortSym(s)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.symbols.map((rowSym, i) => (
                    <tr key={rowSym}>
                      <td>
                        <b>{shortSym(rowSym)}</b>
                      </td>
                      {data.symbols.map((colSym, j) => {
                        const v = data.matrix[i]?.[j] ?? null
                        return (
                          <td key={colSym} className="mono">
                            {fmtCorr(v)}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {focusPeers.length > 0 && focus && (
            <div style={{ marginTop: 12 }}>
              <div className="eyebrow">FOCUS · {shortSym(focus)}</div>
              {focusPeers.slice(0, 5).map((p) => (
                <div key={p.symbol} className="statline">
                  <span>{shortSym(p.symbol)}</span>
                  <b className={`mono ${(p.corr ?? 0) >= 0 ? 'up' : 'down'}`}>{fmtCorr(p.corr)}</b>
                </div>
              ))}
              <label className="field" style={{ marginTop: 10 }}>
                Changer le focus
                <select value={focus ?? ''} onChange={(e) => setFocus(e.target.value || null)}>
                  {data.symbols.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}
          <p style={{ fontSize: 11, color: 'var(--muted)' }}>
            {data.symbols.length} symboles · n={data.sample_size} · {data.timeframe}
          </p>
        </>
      )}
      </div>
    </section>
  )
}
