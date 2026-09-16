import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CorrelationHeatmap } from './CorrelationHeatmap'
import { ContextFeedsPanel } from './ContextFeedsPanel'
import {
  fetchFearGreed,
  fetchFearGreedHistory,
  fetchGlobalMarket,
  fetchTopMarkets,
  type FearGreed,
  type GlobalMarketData,
  type MarketCoin,
} from '../lib/marketContext'

function fmtUsd(n: number): string {
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`
  if (n >= 1e3) return `$${(n / 1e3).toFixed(1)}K`
  return `$${n.toFixed(0)}`
}

function fmtPrice(n: number): string {
  if (n >= 1000) return `$${n.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
  if (n >= 1) return `$${n.toFixed(2)}`
  return `$${n.toPrecision(3)}`
}

function fmtDay(ts: number): string {
  return new Date(ts).toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric' })
}

type ContextVariant = 'compact' | 'full'

export function ContextPanel({ variant = 'full' }: { variant?: ContextVariant }) {
  const compact = variant === 'compact'
  const [market, setMarket] = useState<GlobalMarketData | null>(null)
  const [fng, setFng] = useState<FearGreed | null>(null)
  const [fngHistory, setFngHistory] = useState<FearGreed[]>([])
  const [coins, setCoins] = useState<MarketCoin[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    // Chargements indépendants : un 429 CoinGecko ne doit pas casser Fear & Greed
    const jobs: Promise<void>[] = [
      fetchGlobalMarket()
        .then((m) => {
          if (!cancelled) {
            setMarket(m)
            setError(null)
          }
        })
        .catch((e: unknown) => {
          if (!cancelled) {
            setError((prev) => prev ?? (e instanceof Error ? e.message : 'Erreur CoinGecko'))
          }
        }),
      fetchFearGreed()
        .then((f) => {
          if (!cancelled) setFng(f)
        })
        .catch(() => {
          /* F&G optionnel pour l’aperçu */
        }),
    ]

    if (!compact) {
      jobs.push(
        fetchFearGreedHistory(7)
          .then((h) => {
            if (!cancelled) setFngHistory(h)
          })
          .catch(() => {}),
        fetchTopMarkets(20)
          .then((c) => {
            if (!cancelled) setCoins(c)
          })
          .catch((e: unknown) => {
            if (!cancelled) {
              setError(e instanceof Error ? e.message : 'Erreur top marchés')
            }
          }),
      )
    }

    void Promise.allSettled(jobs).finally(() => {
      if (!cancelled) setLoading(false)
    })

    return () => {
      cancelled = true
    }
  }, [compact])

  const dominanceSlice = compact ? market?.dominance.slice(0, 3) : market?.dominance

  return (
    <section className={`context-view panel${compact ? ' context-view--compact' : ''}`}>
      <header className="panel-head">
        <div>
          <h2>{compact ? 'Contexte (aperçu)' : 'Contexte marché'}</h2>
          {!compact && (
            <p className="context-role muted">
              Régime macro / sentiment — <strong>n’invente pas</strong> la direction Ichimoku. Sert à
              lire l’environnement (risk-on / risk-off), pas à voter LONG/SHORT.
            </p>
          )}
        </div>
        <span className="panel-meta">
          {loading ? 'chargement…' : compact ? 'résumé' : 'CoinGecko · F&G · news · calendrier'}
        </span>
      </header>

      {error && !market && (
        <div className="banner error" role="alert">
          {error}
        </div>
      )}
      {error && market && (
        <p className="muted context-stale-note" title={error}>
          Données en cache — CoinGecko momentanément indisponible.
        </p>
      )}

      {market && (
        <div className="context-grid">
          <div className="context-card">
            <span className="context-label">Market cap</span>
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

      {dominanceSlice && dominanceSlice.length > 0 && (
        <div className="context-dominance">
          <h3>Dominance{compact ? ' (top 3)' : ''}</h3>
          <div className="dominance-bars">
            {dominanceSlice.map((d) => (
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

      {!compact && fngHistory.length > 1 && (
        <div className="context-fng-history">
          <h3>Fear &amp; Greed — 7 jours</h3>
          <div className="fng-history-bars" role="img" aria-label="Historique Fear and Greed">
            {fngHistory
              .slice()
              .reverse()
              .map((p) => (
                <div key={p.timestamp} className="fng-history-col" title={`${p.value} · ${p.classification}`}>
                  <div className="fng-history-bar-wrap">
                    <div className="fng-history-bar" style={{ height: `${Math.max(8, p.value)}%` }} />
                  </div>
                  <span className="fng-history-val mono">{p.value}</span>
                  <span className="fng-history-day muted">{fmtDay(p.timestamp)}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {!compact && coins.length > 0 && (
        <div className="context-markets">
          <header className="panel-head context-markets-head">
            <h3>Marchés majeurs</h3>
            <span className="panel-meta">Top {coins.length} par market cap · pas le screener IchiVol</span>
          </header>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Actif</th>
                  <th>Prix</th>
                  <th>24h</th>
                  <th>Mkt cap</th>
                  <th>Vol. 24h</th>
                </tr>
              </thead>
              <tbody>
                {coins.map((c) => (
                  <tr key={c.id}>
                    <td className="mono muted">{c.rank || '—'}</td>
                    <td>
                      <strong>{c.symbol}</strong>
                      <span className="context-coin-name muted"> {c.name}</span>
                    </td>
                    <td className="mono">{fmtPrice(c.priceUsd)}</td>
                    <td
                      className={`mono ${
                        c.changePercent24h == null
                          ? ''
                          : c.changePercent24h >= 0
                            ? 'up'
                            : 'down'
                      }`}
                    >
                      {c.changePercent24h == null
                        ? '—'
                        : `${c.changePercent24h >= 0 ? '+' : ''}${c.changePercent24h.toFixed(2)}%`}
                    </td>
                    <td className="mono">{fmtUsd(c.marketCapUsd)}</td>
                    <td className="mono">{fmtUsd(c.volume24hUsd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!compact && (
        <section className="context-feeds-wrap" aria-label="News et calendrier">
          <ContextFeedsPanel />
        </section>
      )}

      {!compact && (
        <section className="context-corr" aria-label="Corrélations">
          <CorrelationHeatmap />
        </section>
      )}

      {compact ? (
        <div className="context-compact-footer">
          <p className="context-note">
            Aperçu macro uniquement. Le détail (news, calendrier, corrélations) est sur la page
            Contexte.
          </p>
          <Link to="/app/context" className="ghost">
            Ouvrir le contexte →
          </Link>
        </div>
      ) : (
        <p className="context-note">
          Haut de page : climat crypto. Puis news / calendrier (adapters gratuits) et
          co-mouvements watchlist. Aucun de ces blocs ne vote LONG/SHORT — la méthode
          reste sur Marché et Décisions.
        </p>
      )}
    </section>
  )
}
