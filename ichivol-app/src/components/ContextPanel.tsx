import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  fetchFearGreed,
  fetchGlobalMarket,
  type FearGreed,
  type GlobalMarketData,
} from '../lib/marketContext'

function fmtUsd(n: number): string {
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`
  return `$${n.toFixed(0)}`
}

/**
 * Teaser Overview — climat crypto compact.
 * Le détail multi-marchés est sur /app/context.
 */
export function ContextPanel({ variant = 'compact' }: { variant?: 'compact' | 'full' }) {
  void variant
  const [market, setMarket] = useState<GlobalMarketData | null>(null)
  const [fng, setFng] = useState<FearGreed | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    void Promise.allSettled([
      fetchGlobalMarket()
        .then((m) => {
          if (!cancelled) {
            setMarket(m)
            setError(null)
          }
        })
        .catch((e: unknown) => {
          if (!cancelled) {
            setError(e instanceof Error ? e.message : 'Erreur CoinGecko')
          }
        }),
      fetchFearGreed()
        .then((f) => {
          if (!cancelled) setFng(f)
        })
        .catch(() => {}),
    ]).finally(() => {
      if (!cancelled) setLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <section className="context-view panel context-view--compact">
      <header className="panel-head">
        <div>
          <h2>Contexte (aperçu crypto)</h2>
        </div>
        <span className="panel-meta">{loading ? 'chargement…' : 'CoinGecko · F&G'}</span>
      </header>

      {error && !market && (
        <div className="banner error" role="alert">
          {error}
        </div>
      )}

      {market && (
        <div className="context-grid">
          <div className="context-card">
            <span className="context-label">Market cap crypto</span>
            <strong className="context-value">{fmtUsd(market.totalMarketCapUsd)}</strong>
            <span className={market.marketCapChangePercent24h >= 0 ? 'up' : 'down'}>
              {market.marketCapChangePercent24h >= 0 ? '+' : ''}
              {market.marketCapChangePercent24h.toFixed(2)}% (24h)
            </span>
          </div>
          <div className="context-card">
            <span className="context-label">Volume 24h</span>
            <strong className="context-value">{fmtUsd(market.totalVolumeUsd)}</strong>
          </div>
          {fng && (
            <div className="context-card">
              <span className="context-label">Fear &amp; Greed</span>
              <strong className="context-value">{fng.value}</strong>
              <span className="muted">{fng.classification}</span>
            </div>
          )}
        </div>
      )}

      {market && market.dominance.length > 0 && (
        <div className="context-dominance">
          <h3>Dominance (top 3)</h3>
          <div className="dominance-bars">
            {market.dominance.slice(0, 3).map((d) => (
              <div key={d.symbol} className="dominance-row">
                <span className="dominance-symbol">{d.symbol}</span>
                <div className="dominance-track">
                  <div className="dominance-fill" style={{ width: `${Math.min(d.percent, 100)}%` }} />
                </div>
                <span className="dominance-pct">{d.percent.toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="context-compact-footer">
        <p className="context-note">
          Aperçu crypto seulement. Forex, métaux, indices, calendrier macro → page Contexte.
        </p>
        <Link to="/app/context" className="ghost">
          Ouvrir le contexte multi-marchés →
        </Link>
      </div>
    </section>
  )
}
