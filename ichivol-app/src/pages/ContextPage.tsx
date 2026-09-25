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
  fetchContextCalendar,
  fetchSymbolContext,
  type ContextCalendarEvent,
  type SymbolContextSnapshot,
} from '../lib/contextFeeds'
import {
  fetchCorrelations,
  type CorrelationMatrix,
} from '../lib/correlations'
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

type RegimeTone = 'pass' | 'caution' | 'neutral' | 'unavailable'

type ClassRegime = {
  assetClass: EngineAssetClass
  label: string
  badge: string
  tone: RegimeTone
  detail: string | null
}

type VigilanceItem = {
  id: string
  title: string
  body: string
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

function climateTrendLabel(changePct: number): string {
  if (changePct >= 1) return 'Hausse'
  if (changePct <= -1) return 'Baisse'
  return 'Stable'
}

function volLabelFromAtr(regime: string | null | undefined): string | null {
  if (!regime) return null
  switch (regime.toLowerCase()) {
    case 'extreme':
      return 'Élevée'
    case 'dead':
      return 'Faible'
    case 'normal':
      return 'Modérée'
    case 'unknown':
      return null
    default:
      return regime
  }
}

function badgeFromSnapshot(snap: SymbolContextSnapshot): {
  badge: string
  tone: RegimeTone
  detail: string
} {
  const atr = snap.atr.regime.toLowerCase()
  const bias = snap.rsi.bias.toLowerCase()
  const rsi = snap.rsi.value
  const detail = `RSI ${rsi != null ? rsi.toFixed(0) : '—'} (${biasLabel(snap.rsi.bias)}) · ATR ${
    snap.atr.value != null ? snap.atr.value.toFixed(snap.atr.value >= 10 ? 1 : 4) : '—'
  }`

  if (
    atr === 'extreme' ||
    bias === 'overbought' ||
    bias === 'oversold' ||
    (rsi != null && (rsi >= 70 || rsi <= 30))
  ) {
    return { badge: 'PRUDENCE', tone: 'caution', detail }
  }
  if (atr === 'dead') {
    return { badge: 'NEUTRE', tone: 'neutral', detail }
  }
  if (atr === 'normal') {
    return { badge: 'PASSE', tone: 'pass', detail }
  }
  if (atr === 'unknown' || !atr) {
    return { badge: 'Non disponible', tone: 'unavailable', detail }
  }
  return { badge: 'NEUTRE', tone: 'neutral', detail }
}

function ClimateKpiRow({
  market,
  fng,
  btcRegime,
}: {
  market: GlobalMarketData | null
  fng: FearGreed | null
  btcRegime: string | null
}) {
  const btcDom = market?.dominance.find(
    (d) => d.symbol.toUpperCase() === 'BTC' || d.symbol.toUpperCase() === 'BITCOIN',
  )
  const volFromAtr = volLabelFromAtr(btcRegime)
  const items: { label: string; value: string; meta: string | null; tone?: 'up' | 'down' }[] = []

  if (market) {
    items.push({
      label: 'Climat du marché',
      value: climateTrendLabel(market.marketCapChangePercent24h),
      meta: `${market.marketCapChangePercent24h >= 0 ? '+' : ''}${market.marketCapChangePercent24h.toFixed(2)} % · 24 h`,
      tone: market.marketCapChangePercent24h >= 0 ? 'up' : 'down',
    })
  }
  if (btcDom) {
    items.push({
      label: 'Dominance BTC',
      value: `${btcDom.percent.toFixed(1)} %`,
      meta: market ? `Cap. ${fmtUsd(market.totalMarketCapUsd)}` : null,
    })
  }
  if (volFromAtr) {
    items.push({
      label: 'Volatilité',
      value: volFromAtr,
      meta: 'ATR · BTC flagship',
    })
  } else if (fng) {
    items.push({
      label: 'Volatilité',
      value: fng.value <= 25 || fng.value >= 75 ? 'Élevée' : 'Modérée',
      meta: `Fear & Greed ${fng.value}`,
    })
  }
  if (fng) {
    items.push({
      label: 'Régime crypto',
      value: fng.classification || String(fng.value),
      meta: 'Fear & Greed · 0 peur → 100 greed',
    })
  } else if (btcRegime) {
    items.push({
      label: 'Régime crypto',
      value: regimeLabel(btcRegime),
      meta: 'ATR · BTC',
    })
  }

  if (items.length === 0) return null

  return (
    <section className="iv-metrics ctx-climate-kpis" aria-label="Climat crypto">
      {items.map((item) => (
        <div key={item.label} className="iv-metric">
          <div className="iv-metric-label">{item.label}</div>
          <div
            className={`iv-metric-value mono${item.tone === 'up' ? ' is-bull' : item.tone === 'down' ? ' is-bear' : ''}`}
          >
            {item.value}
          </div>
          {item.meta ? <small>{item.meta}</small> : null}
        </div>
      ))}
    </section>
  )
}

function RegimeByClass({ instruments }: { instruments: EngineInstrument[] }) {
  const [rows, setRows] = useState<ClassRegime[]>([])
  const [loading, setLoading] = useState(false)

  const classesToFetch = useMemo(() => {
    const wired = new Set(instruments.filter((i) => i.wired).map((i) => i.id))
    return CLASS_ORDER.map((assetClass) => {
      const wanted = FLAGSHIPS[assetClass].filter((s) => wired.has(s))
      return { assetClass, symbol: wanted[0] ?? null }
    }).filter((c) => c.symbol != null)
  }, [instruments])

  useEffect(() => {
    let cancelled = false
    if (classesToFetch.length === 0) {
      setRows([])
      return
    }
    setLoading(true)
    void Promise.all(
      classesToFetch.map(async ({ assetClass, symbol }) => {
        try {
          const snap = await fetchSymbolContext(symbol!, '1h')
          const mapped = badgeFromSnapshot(snap)
          return {
            assetClass,
            label: CLASS_LABELS[assetClass],
            badge: mapped.badge,
            tone: mapped.tone,
            detail: `${symbol} · ${mapped.detail}`,
          } satisfies ClassRegime
        } catch {
          return {
            assetClass,
            label: CLASS_LABELS[assetClass],
            badge: 'Non disponible',
            tone: 'unavailable' as const,
            detail: symbol,
          } satisfies ClassRegime
        }
      }),
    ).then((res) => {
      if (!cancelled) {
        setRows(res)
        setLoading(false)
      }
    })
    return () => {
      cancelled = true
    }
  }, [classesToFetch])

  if (classesToFetch.length === 0) return null

  return (
    <section className="panel ctx-regime-classes" aria-label="Régime par classe d’actifs">
      <header className="panel-head">
        <h2>Régime par classe d’actifs</h2>
        <span className="panel-meta">Flagships · RSI / ATR</span>
      </header>
      {loading && <p className="muted ctx-pad">Chargement…</p>}
      {!loading && rows.length === 0 && <p className="muted ctx-pad">Non disponible</p>}
      {!loading && rows.length > 0 && (
        <ul className="ctx-regime-badges">
          {rows.map((r) => (
            <li key={r.assetClass} className="ctx-regime-row">
              <span className="ctx-regime-class">{r.label}</span>
              <span className={`ctx-regime-badge is-${r.tone}`}>{r.badge}</span>
              {r.detail ? <span className="muted ctx-regime-detail">{r.detail}</span> : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function VigilancePoints({
  fng,
  assetClass,
  instruments,
}: {
  fng: FearGreed | null
  assetClass: EngineAssetClass
  instruments: EngineInstrument[]
}) {
  const [items, setItems] = useState<VigilanceItem[]>([])

  const corrSymbols = useMemo(() => {
    return instruments
      .filter((i) => i.wired && i.enabled && i.asset_class === assetClass)
      .map((i) => i.id)
      .slice(0, 12)
  }, [instruments, assetClass])

  useEffect(() => {
    let cancelled = false
    void Promise.allSettled([
      fetchContextCalendar({ limit: 40 }),
      corrSymbols.length >= 2
        ? fetchCorrelations({
            timeframe: assetClass === 'crypto' ? '1h' : '1d',
            symbols: corrSymbols,
          })
        : Promise.resolve(null),
    ]).then((results) => {
      if (cancelled) return
      const next: VigilanceItem[] = []
      const now = Date.now()
      const dayMs = 24 * 60 * 60 * 1000

      if (results[0].status === 'fulfilled') {
        const events = results[0].value as ContextCalendarEvent[]
        const highSoon = events.filter((e) => {
          if (e.impact.toLowerCase() !== 'high') return false
          const t = Date.parse(e.date)
          if (Number.isNaN(t)) return false
          const delta = t - now
          return delta >= 0 && delta <= dayMs
        })
        if (highSoon.length > 0) {
          const first = highSoon[0]
          next.push({
            id: 'calendar-high',
            title: 'Calendrier à fort impact',
            body:
              highSoon.length === 1
                ? `${first.country} · ${first.title} dans les 24 h.`
                : `${highSoon.length} événements high impact dans les 24 h (ex. ${first.country} · ${first.title}).`,
          })
        }
      }

      if (results[1].status === 'fulfilled' && results[1].value) {
        const matrix = results[1].value as CorrelationMatrix
        const pairs: { a: string; b: string; v: number }[] = []
        for (let i = 0; i < matrix.symbols.length; i++) {
          for (let j = i + 1; j < matrix.symbols.length; j++) {
            const v = matrix.matrix[i]?.[j]
            if (v != null && Number.isFinite(v) && Math.abs(v) > 0.8) {
              pairs.push({ a: matrix.symbols[i], b: matrix.symbols[j], v })
            }
          }
        }
        pairs.sort((a, b) => Math.abs(b.v) - Math.abs(a.v))
        if (pairs.length > 0) {
          const top = pairs[0]
          next.push({
            id: 'corr-high',
            title: 'Corrélation élevée',
            body: `${top.a} / ${top.b} : ${top.v.toFixed(2)}${
              pairs.length > 1
                ? ` (+${pairs.length - 1} autre${pairs.length > 2 ? 's' : ''})`
                : ''
            }.`,
          })
        }
      }

      if (fng && (fng.value <= 20 || fng.value >= 80)) {
        next.push({
          id: 'fng-extreme',
          title: 'Fear & Greed extrême',
          body: `Indice à ${fng.value} (${fng.classification}) — sentiment hors zone neutre.`,
        })
      }

      setItems(next)
    })
    return () => {
      cancelled = true
    }
  }, [fng, corrSymbols, assetClass])

  if (items.length === 0) return null

  return (
    <section className="panel ctx-vigilance" aria-label="Points de vigilance">
      <header className="panel-head">
        <h2>Points de vigilance</h2>
        <span className="panel-meta">
          {items.length} signal{items.length > 1 ? 'aux' : ''}
        </span>
      </header>
      <div className="ctx-vigilance-list">
        {items.map((item) => (
          <div key={item.id} className="ctx-vigilance-item">
            <b>{item.title}</b>
            <p>{item.body}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

function CryptoClimateDetail({
  market,
  fng,
  error,
}: {
  market: GlobalMarketData | null
  fng: FearGreed | null
  error: string | null
}) {
  if (!market && !error) return null
  if (error && !market) {
    return (
      <section className="panel ctx-climate" aria-label="Détail climat crypto">
        <header className="panel-head">
          <h2>Climat crypto</h2>
        </header>
        <p className="muted ctx-pad">{error}</p>
      </section>
    )
  }
  if (!market) return null

  return (
    <section className="panel ctx-climate" aria-label="Détail climat crypto">
      <header className="panel-head">
        <h2>Climat crypto</h2>
        <span className="panel-meta">CoinGecko · Fear &amp; Greed — pas le screener IchiVol</span>
      </header>
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
      {market.dominance.length > 0 && (
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

export function ContextPage() {
  const [instruments, setInstruments] = useState<EngineInstrument[]>([])
  const [assetClass, setAssetClass] = useState<EngineAssetClass>('forex')
  const [ready, setReady] = useState(false)
  const [market, setMarket] = useState<GlobalMarketData | null>(null)
  const [fng, setFng] = useState<FearGreed | null>(null)
  const [climateError, setClimateError] = useState<string | null>(null)
  const [btcRegime, setBtcRegime] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getEngineUniverse()
      .then((u) => {
        if (cancelled) return
        setInstruments(u.instruments)
        const present = CLASS_ORDER.filter((c) =>
          u.instruments.some((i) => i.asset_class === c && i.wired),
        )
        const preferred = present.includes('forex') ? 'forex' : (present[0] ?? 'crypto')
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

  useEffect(() => {
    let cancelled = false
    void Promise.allSettled([
      fetchGlobalMarket().then((m) => {
        if (!cancelled) setMarket(m)
      }),
      fetchFearGreed().then((f) => {
        if (!cancelled) setFng(f)
      }),
      fetchSymbolContext('BTCUSDT', '1h')
        .then((snap) => {
          if (!cancelled) setBtcRegime(snap.atr.regime)
        })
        .catch(() => {
          if (!cancelled) setBtcRegime(null)
        }),
    ]).then((results) => {
      if (cancelled) return
      if (results[0].status === 'rejected') {
        setClimateError(
          results[0].reason instanceof Error
            ? results[0].reason.message
            : 'Climat crypto indisponible',
        )
      } else {
        setClimateError(null)
      }
    })
    return () => {
      cancelled = true
    }
  }, [])

  const visibleClasses = useMemo(() => {
    const present = new Set(instruments.filter((i) => i.wired).map((i) => i.asset_class))
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

      <ClimateKpiRow market={market} fng={fng} btcRegime={btcRegime} />

      {isCrypto && <CryptoClimateDetail market={market} fng={fng} error={climateError} />}

      <ContextFeedsPanel
        showNews
        calendarFirst={!isCrypto}
        defaultImpact={isCrypto ? 'high_medium' : 'high'}
        calendarLimit={isCrypto ? 24 : 30}
      />

      <RegimeByClass instruments={instruments} />

      <CorrelationHeatmap assetClass={assetClass} />

      <VigilancePoints fng={fng} assetClass={assetClass} instruments={instruments} />

      <p className="context-note">
        Cette page lit l’environnement (macro, sentiment, co-mouvements). Elle ne décide
        jamais LONG/SHORT — ça reste sur Marché et Décisions.
      </p>
    </div>
  )
}
