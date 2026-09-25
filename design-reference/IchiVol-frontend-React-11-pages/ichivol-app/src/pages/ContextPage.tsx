import { useEffect, useMemo, useState } from 'react'
import { CorrelationHeatmap } from '../components/CorrelationHeatmap'
import { ContextFeedsPanel } from '../components/ContextFeedsPanel'
import {
  fetchFearGreed,
  fetchGlobalMarket,
  type FearGreed,
  type GlobalMarketData,
} from '../lib/marketContext'
import {
  fetchSymbolContext,
  type SymbolContextSnapshot,
} from '../lib/contextFeeds'
import {
  CLASS_BLURBS,
  CLASS_LABELS,
  getEngineUniverse,
  type EngineAssetClass,
  type EngineInstrument,
} from '../lib/universe'
import './ContextPage.css'

const CLASS_ORDER: EngineAssetClass[] = [
  'forex',
  'crypto',
  'metal',
  'index',
  'equity',
  'energy',
]

const FLAGSHIPS: Record<EngineAssetClass, string[]> = {
  forex: ['EURUSD', 'GBPUSD', 'USDJPY'],
  crypto: ['BTCUSDT', 'ETHUSDT'],
  metal: ['XAUUSD', 'XAGUSD'],
  index: ['SPX', 'NDX'],
  equity: [],
  energy: ['WTI'],
}

const CLASS_HINT: Record<EngineAssetClass, string> = {
  forex: 'Calendrier macro + régime technique des paires majeures + corrélations FX.',
  crypto: 'Climat CoinGecko / Fear & Greed, RSS crypto, puis corrélations spot.',
  metal: 'Or / argent : calendrier USD + régime ATR/RSI + co-mouvements.',
  index: 'Indices risk-on : calendrier + régime + corrélations.',
  equity: 'Actions (quota Twelve Data) — calendrier macro US en priorité.',
  energy: 'Énergie si le provider est câblé — sinon calendrier seul.',
}

function fmtUsd(n: number): string {
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`
  return `$${n.toFixed(0)}`
}

function regimeLabel(regime: string): string {
  switch (regime.toLowerCase()) {
    case 'extreme':
      return 'Volatilité extrême'
    case 'dead':
      return 'Volatilité morte'
    case 'normal':
      return 'Volatilité normale'
    case 'unknown':
      return 'Régime inconnu'
    default:
      return regime || '—'
  }
}

function biasLabel(bias: string): string {
  switch (bias.toLowerCase()) {
    case 'bullish':
    case 'overbought':
      return 'hausse'
    case 'bearish':
    case 'oversold':
      return 'baisse'
    default:
      return bias || 'neutre'
  }
}

function CryptoClimate() {
  const [market, setMarket] = useState<GlobalMarketData | null>(null)
  const [fng, setFng] = useState<FearGreed | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    void Promise.allSettled([
      fetchGlobalMarket().then((m) => {
        if (!cancelled) setMarket(m)
      }),
      fetchFearGreed().then((f) => {
        if (!cancelled) setFng(f)
      }),
    ]).then((results) => {
      if (cancelled) return
      if (results[0].status === 'rejected') {
        setError(
          results[0].reason instanceof Error
            ? results[0].reason.message
            : 'Climat crypto indisponible',
        )
      }
    })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <section className="panel ctx-climate" aria-label="Climat crypto">
      <header className="panel-head">
        <h2>Climat crypto</h2>
        <span className="panel-meta">CoinGecko · Fear &amp; Greed — pas le screener IchiVol</span>
      </header>
      {error && !market && (
        <p className="muted ctx-pad">{error}</p>
      )}
      {market && (
        <div className="context-grid ctx-pad">
          <div className="context-card">
            <span className="context-label">Capitalisation mondiale</span>
            <strong className="context-value">{fmtUsd(market.totalMarketCapUsd)}</strong>
            <span className={market.marketCapChangePercent24h >= 0 ? 'up' : 'down'}>
              {market.marketCapChangePercent24h >= 0 ? '+' : ''}
              {market.marketCapChangePercent24h.toFixed(2)} % (24 h)
            </span>
          </div>
          <div className="context-card">
            <span className="context-label">Volume 24 h</span>
            <strong className="context-value">{fmtUsd(market.totalVolumeUsd)}</strong>
            <span className="muted">activité spot agrégée</span>
          </div>
          {fng && (
            <div className="context-card">
              <span className="context-label">Sentiment (Fear &amp; Greed)</span>
              <strong className="context-value">{fng.value}</strong>
              <span className="muted">{fng.classification} · 0 peur → 100 greed</span>
            </div>
          )}
        </div>
      )}
      {market && market.dominance.length > 0 && (
        <div className="context-dominance ctx-pad">
          <h3>Part de marché (dominance)</h3>
          <div className="dominance-bars">
            {market.dominance.slice(0, 5).map((d) => (
              <div key={d.symbol} className="dominance-row">
                <span className="dominance-symbol">{d.symbol}</span>
                <div className="dominance-track">
                  <div className="dominance-fill" style={{ width: `${Math.min(d.percent, 100)}%` }} />
                </div>
                <span className="dominance-pct">{d.percent.toFixed(1)} %</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}

function RegimeStrip({
  assetClass,
  instruments,
}: {
  assetClass: EngineAssetClass
  instruments: EngineInstrument[]
}) {
  const wanted = FLAGSHIPS[assetClass]
  const symbols = useMemo(() => {
    if (wanted.length === 0) return []
    const wired = new Set(instruments.filter((i) => i.wired).map((i) => i.id))
    return wanted.filter((s) => wired.has(s)).slice(0, 3)
  }, [wanted, instruments])

  const [rows, setRows] = useState<(SymbolContextSnapshot | { symbol: string; error: string })[]>(
    [],
  )
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (symbols.length === 0) {
      setRows([])
      return
    }
    let cancelled = false
    setLoading(true)
    void Promise.all(
      symbols.map((s) =>
        fetchSymbolContext(s, assetClass === 'crypto' ? '1h' : '1h')
          .then((snap) => snap)
          .catch((e: unknown) => ({
            symbol: s,
            error: e instanceof Error ? e.message : 'indisponible',
          })),
      ),
    ).then((res) => {
      if (!cancelled) {
        setRows(res)
        setLoading(false)
      }
    })
    return () => {
      cancelled = true
    }
  }, [symbols, assetClass])

  if (symbols.length === 0) return null

  return (
    <section className="panel ctx-regime" aria-label="Régime technique">
      <header className="panel-head">
        <h2>Régime technique</h2>
        <span className="panel-meta">RSI · ATR — analyse seule, pas un vote</span>
      </header>
      {loading && <p className="muted ctx-pad">Chargement…</p>}
      {!loading && (
        <div className="ctx-regime-grid">
          {rows.map((r) => {
            if ('error' in r) {
              return (
                <div key={r.symbol} className="context-card">
                  <span className="context-label mono">{r.symbol}</span>
                  <span className="muted">{r.error}</span>
                </div>
              )
            }
            return (
              <div key={r.symbol} className="context-card">
                <span className="context-label mono">{r.symbol}</span>
                <strong className="context-value">{regimeLabel(r.atr.regime)}</strong>
                <span className="muted">
                  RSI {r.rsi.value != null ? r.rsi.value.toFixed(0) : '—'} (
                  {biasLabel(r.rsi.bias)}) · ATR{' '}
                  {r.atr.value != null ? r.atr.value.toFixed(r.atr.value >= 10 ? 1 : 4) : '—'}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}

export function ContextPage() {
  const [instruments, setInstruments] = useState<EngineInstrument[]>([])
  const [assetClass, setAssetClass] = useState<EngineAssetClass>('forex')
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let cancelled = false
    getEngineUniverse()
      .then((u) => {
        if (cancelled) return
        setInstruments(u.instruments)
        const present = CLASS_ORDER.filter((c) =>
          u.instruments.some((i) => i.asset_class === c && i.wired),
        )
        const preferred = present.includes('forex')
          ? 'forex'
          : (present[0] ?? 'crypto')
        setAssetClass(preferred)
        setReady(true)
      })
      .catch(() => {
        if (!cancelled) {
          setAssetClass('crypto')
          setReady(true)
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  const visibleClasses = useMemo(() => {
    const present = new Set(
      instruments.filter((i) => i.wired).map((i) => i.asset_class),
    )
    const list = CLASS_ORDER.filter((c) => present.has(c))
    return list.length > 0 ? list : (['crypto'] as EngineAssetClass[])
  }, [instruments])

  const isCrypto = assetClass === 'crypto'

  return (
    <div className="context-page">
      <header className="iv-page-header page-head overview-head">
        <div>
          <p className="iv-page-eyebrow">Recherche · Contexte</p>
          <h1>Contexte</h1>
          <p className="iv-page-question">Dans quel environnement évolue le marché ?</p>
          <p className="muted">{CLASS_HINT[assetClass]}</p>
        </div>
        <div className="market-class-tabs" role="tablist" aria-label="Classe d’actif">
          {visibleClasses.map((c) => (
            <button
              key={c}
              type="button"
              role="tab"
              aria-selected={c === assetClass}
              className={c === assetClass ? 'is-active' : undefined}
              onClick={() => setAssetClass(c)}
              disabled={!ready}
            >
              {CLASS_LABELS[c]}
            </button>
          ))}
        </div>
      </header>

      <p className="muted ctx-blurb">{CLASS_BLURBS[assetClass]}</p>

      {isCrypto && <CryptoClimate />}

      <ContextFeedsPanel
        showNews
        calendarFirst={!isCrypto}
        defaultImpact={isCrypto ? 'high_medium' : 'high'}
        calendarLimit={isCrypto ? 24 : 30}
      />

      <RegimeStrip assetClass={assetClass} instruments={instruments} />

      <CorrelationHeatmap assetClass={assetClass} />

      <p className="context-note">
        Cette page lit l’environnement (macro, sentiment, co-mouvements). Elle ne décide
        jamais LONG/SHORT — ça reste sur Marché et Décisions.
      </p>
    </div>
  )
}
