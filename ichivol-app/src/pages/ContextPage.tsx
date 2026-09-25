/**
 * Contexte — climat marché (lecture seule, ne vote jamais).
 * Layout maquette `.ctx-page` + données live (CoinGecko, F&G, calendar, news, ATR, corr).
 */

import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  fetchContextCalendar,
  fetchContextNews,
  fetchSymbolContext,
  type ContextCalendarEvent,
  type ContextNewsItem,
  type SymbolContextSnapshot,
} from '../lib/contextFeeds'
import { fetchCorrelations, type CorrelationMatrix } from '../lib/correlations'
import { displaySymbol } from '../lib/markets'
import {
  fetchFearGreed,
  fetchGlobalMarket,
  type FearGreed,
  type GlobalMarketData,
} from '../lib/marketContext'
import {
  CLASS_LABELS,
  getEngineUniverse,
  type EngineAssetClass,
  type EngineInstrument,
} from '../lib/universe'
import './ContextPage.css'

type BadgeTone = 'green' | 'amber' | 'red' | 'gray' | ''

type ClassRegime = {
  assetClass: EngineAssetClass
  label: string
  badge: string
  tone: BadgeTone
  detail: string
}

type VigilanceItem = { id: string; title: string; body: string }

const HEAT_SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT']

const FLAGSHIPS: Record<EngineAssetClass, string[]> = {
  forex: ['EURUSD', 'GBPUSD', 'USDJPY'],
  crypto: ['BTCUSDT', 'ETHUSDT'],
  metal: ['XAUUSD', 'XAGUSD'],
  index: ['SPX', 'NDX'],
  equity: [],
  energy: ['WTI'],
}

const DISPLAY_CLASSES: EngineAssetClass[] = ['crypto', 'forex', 'metal', 'index', 'equity']

function badge(text: string, tone: BadgeTone = ''): ReactNode {
  let inferred = tone
  if (!inferred) {
    inferred = /PASSE|ACCEPTÉ|OUVERTE|VALIDÉ/i.test(text)
      ? 'green'
      : /REFUS|BLOQU|ERREUR|Non disponible/i.test(text)
        ? 'red'
        : /PRUDENCE|Élevé|ARMED|WATCH|TRIGGERED|NEUTRE/i.test(text)
          ? 'amber'
          : ''
  }
  return <span className={`tag ${inferred}`.trim()}>{text}</span>
}

function fearGreedFr(classification: string): string {
  switch (classification.toLowerCase()) {
    case 'extreme fear':
      return 'Peur extrême'
    case 'fear':
      return 'Peur'
    case 'neutral':
      return 'Neutre'
    case 'greed':
      return 'Avidité'
    case 'extreme greed':
      return 'Avidité extrême'
    default:
      return classification
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

function fmtEventTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(+d)) return iso || '—'
  const now = new Date()
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  if (sameDay) {
    return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', hour12: false })
  }
  return d.toLocaleString('fr-FR', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function fmtNewsTime(ts: number | null): string {
  if (ts == null || !Number.isFinite(ts)) return '—'
  const ms = ts < 1e12 ? ts * 1000 : ts
  const d = new Date(ms)
  if (Number.isNaN(+d)) return '—'
  return d.toLocaleString('fr-FR', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function impactBadge(impact: string): ReactNode {
  const t = impact.trim()
  if (!t) return badge('—', 'gray')
  if (/high|élev|elev/i.test(t)) return badge('Élevé', 'amber')
  if (/med|moy/i.test(t)) return badge('Moyen', 'gray')
  if (/low|faible/i.test(t)) return badge('Faible', 'gray')
  return badge(t, 'gray')
}

function badgeFromSnapshot(snap: SymbolContextSnapshot): {
  badge: string
  tone: BadgeTone
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
    return { badge: 'PRUDENCE', tone: 'amber', detail }
  }
  if (atr === 'dead') {
    return { badge: 'NEUTRE', tone: 'gray', detail }
  }
  if (atr === 'normal') {
    return { badge: 'PASSE', tone: 'green', detail }
  }
  if (atr === 'unknown' || !atr) {
    return { badge: 'Non disponible', tone: 'gray', detail }
  }
  return { badge: 'NEUTRE', tone: 'gray', detail }
}

function toneForClass(tone: BadgeTone): BadgeTone {
  return tone || 'gray'
}

export function ContextPage() {
  const [global, setGlobal] = useState<GlobalMarketData | null>(null)
  const [fg, setFg] = useState<FearGreed | null>(null)
  const [btcSnap, setBtcSnap] = useState<SymbolContextSnapshot | null>(null)
  const [events, setEvents] = useState<ContextCalendarEvent[]>([])
  const [news, setNews] = useState<ContextNewsItem[]>([])
  const [corr, setCorr] = useState<CorrelationMatrix | null>(null)
  const [regimes, setRegimes] = useState<ClassRegime[]>([])
  const [vigilance, setVigilance] = useState<VigilanceItem[]>([])
  const [instruments, setInstruments] = useState<EngineInstrument[]>([])
  const [loading, setLoading] = useState(true)
  const [feedError, setFeedError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setFeedError(null)
    try {
      const [gRes, fRes, calRes, newsRes, cRes, btcRes, uniRes] = await Promise.allSettled([
        fetchGlobalMarket(),
        fetchFearGreed(),
        fetchContextCalendar({ limit: 12 }),
        fetchContextNews({ limit: 8 }),
        fetchCorrelations({ symbols: HEAT_SYMBOLS, timeframe: '1h', limit: 720 }),
        fetchSymbolContext('BTCUSDT', '1h'),
        getEngineUniverse(),
      ])

      const g = gRes.status === 'fulfilled' ? gRes.value : null
      const f = fRes.status === 'fulfilled' ? fRes.value : null
      const cal = calRes.status === 'fulfilled' ? calRes.value : []
      const newsItems = newsRes.status === 'fulfilled' ? newsRes.value : []
      const c = cRes.status === 'fulfilled' ? cRes.value : null
      const btc = btcRes.status === 'fulfilled' ? btcRes.value : null
      const uni = uniRes.status === 'fulfilled' ? uniRes.value : null

      setGlobal(g)
      setFg(f)
      setEvents(cal.slice(0, 6))
      setNews(newsItems.slice(0, 6))
      setCorr(c)
      setBtcSnap(btc)
      setInstruments(uni?.instruments ?? [])

      if (!g && !f && cal.length === 0 && newsItems.length === 0 && !c && !btc) {
        setFeedError('Feeds contexte indisponibles pour le moment.')
      }

      const wired = new Set((uni?.instruments ?? []).filter((i) => i.wired).map((i) => i.id))
      const classRows = await Promise.all(
        DISPLAY_CLASSES.map(async (assetClass) => {
          const candidates = FLAGSHIPS[assetClass].filter((s) => wired.has(s))
          const symbol = candidates[0]
          if (!symbol) {
            return {
              assetClass,
              label: CLASS_LABELS[assetClass],
              badge: 'Non disponible',
              tone: 'gray' as BadgeTone,
              detail: 'Provider non câblé',
            } satisfies ClassRegime
          }
          try {
            const snap = await fetchSymbolContext(symbol, '1h')
            const mapped = badgeFromSnapshot(snap)
            return {
              assetClass,
              label: CLASS_LABELS[assetClass],
              badge: mapped.badge,
              tone: toneForClass(mapped.tone),
              detail: `${symbol} · ${mapped.detail}`,
            } satisfies ClassRegime
          } catch {
            return {
              assetClass,
              label: CLASS_LABELS[assetClass],
              badge: 'Non disponible',
              tone: 'gray' as BadgeTone,
              detail: symbol,
            } satisfies ClassRegime
          }
        }),
      )
      setRegimes(classRows)

      const nextVigilance: VigilanceItem[] = []
      const now = Date.now()
      const dayMs = 24 * 60 * 60 * 1000
      const highSoon = cal.filter((e) => {
        if (!/high|élev|elev/i.test(e.impact)) return false
        const t = Date.parse(e.date)
        if (Number.isNaN(t)) return false
        const delta = t - now
        return delta >= 0 && delta <= dayMs
      })
      if (highSoon.length > 0) {
        const first = highSoon[0]
        nextVigilance.push({
          id: 'calendar-high',
          title: 'Calendrier à fort impact',
          body:
            highSoon.length === 1
              ? `${first.country} · ${first.title} dans les 24 h.`
              : `${highSoon.length} événements high impact dans les 24 h (ex. ${first.country} · ${first.title}).`,
        })
      }

      if (c?.matrix?.length) {
        const pairs: { a: string; b: string; v: number }[] = []
        for (let i = 0; i < c.symbols.length; i++) {
          for (let j = i + 1; j < c.symbols.length; j++) {
            const v = c.matrix[i]?.[j]
            if (v != null && Number.isFinite(v) && Math.abs(v) > 0.8) {
              pairs.push({ a: c.symbols[i], b: c.symbols[j], v })
            }
          }
        }
        pairs.sort((a, b) => Math.abs(b.v) - Math.abs(a.v))
        if (pairs.length > 0) {
          const top = pairs[0]
          nextVigilance.push({
            id: 'corr-high',
            title: 'Corrélation élevée',
            body: `${displaySymbol(top.a)} / ${displaySymbol(top.b)} : ${top.v.toFixed(2)}${
              pairs.length > 1 ? ` (+${pairs.length - 1} autre${pairs.length > 2 ? 's' : ''})` : ''
            }.`,
          })
        }
      }

      if (f && (f.value <= 20 || f.value >= 80)) {
        nextVigilance.push({
          id: 'fng-extreme',
          title: 'Fear & Greed extrême',
          body: `Indice à ${f.value} (${fearGreedFr(f.classification)}) — sentiment hors zone neutre.`,
        })
      }

      if (btc?.atr.regime.toLowerCase() === 'extreme') {
        nextVigilance.push({
          id: 'btc-vol',
          title: 'Volatilité BTC extrême',
          body: 'ATR en régime extrême sur BTC — relire le budget de risque avant d’ajouter de l’exposition.',
        })
      }

      if (nextVigilance.length === 0) {
        nextVigilance.push(
          {
            id: 'fallback-corr',
            title: 'Exposition corrélée',
            body: 'Plusieurs positions crypto peuvent réagir au même mouvement de BTC.',
          },
          {
            id: 'fallback-vol',
            title: 'Volume inhabituel',
            body: 'Un pic de volume peut accompagner un événement. Vérifier le contexte.',
          },
          {
            id: 'fallback-gap',
            title: 'Gap et volatilité',
            body: 'Relire le plan de risque si les conditions de marché changent.',
          },
        )
      }
      setVigilance(nextVigilance)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const btcDom = useMemo(() => {
    const d = global?.dominance?.find((x) => /btc/i.test(x.symbol))
    if (d == null || !Number.isFinite(d.percent)) return null
    return d.percent
  }, [global])

  const climateLabel =
    global != null
      ? climateTrendLabel(global.marketCapChangePercent24h)
      : fg
        ? fearGreedFr(fg.classification)
        : loading
          ? '…'
          : '—'

  const climateMeta =
    global != null
      ? `${global.marketCapChangePercent24h >= 0 ? '+' : ''}${global.marketCapChangePercent24h.toFixed(2)} % · 24 h`
      : fg
        ? `Fear & Greed ${fg.value}`
        : '—'

  const volLabel =
    volLabelFromAtr(btcSnap?.atr.regime) ??
    (fg != null ? (fg.value <= 25 || fg.value >= 75 ? 'Élevée' : 'Modérée') : loading ? '…' : '—')

  const volMeta =
    btcSnap?.atr.regime != null
      ? 'ATR · BTC flagship'
      : fg
        ? `Fear & Greed ${fg.value}`
        : 'ATR / prix · contexte'

  const regimeLabel = fg
    ? fearGreedFr(fg.classification)
    : btcSnap
      ? volLabelFromAtr(btcSnap.atr.regime) ?? '—'
      : loading
        ? '…'
        : '—'

  const regimeMeta = fg
    ? `Fear & Greed ${fg.value} · 0 peur → 100 avidité`
    : btcSnap
      ? 'ATR · BTC'
      : 'Concentration à surveiller'

  const heatLabels = corr?.symbols?.length
    ? corr.symbols.map((s) => displaySymbol(s))
    : ['BTC', 'ETH', 'SOL', 'XRP', 'BNB']

  const heatCells: { v: string; strong: boolean }[] = []
  if (corr?.matrix?.length) {
    const n = Math.min(5, corr.symbols.length)
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const x = corr.matrix[i]?.[j]
        if (x == null || !Number.isFinite(x)) {
          heatCells.push({ v: '—', strong: false })
        } else {
          heatCells.push({ v: x.toFixed(2), strong: Math.abs(x) > 0.85 })
        }
      }
    }
  } else {
    for (let i = 0; i < 25; i++) heatCells.push({ v: loading ? '…' : '—', strong: false })
  }

  const liveOk = Boolean(global || fg || events.length || news.length || corr || btcSnap)
  const wiredCount = instruments.filter((i) => i.wired).length

  return (
    <div className="ctx-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">07 / ICHIVOL WORKSPACE</div>
          <h1>Contexte</h1>
          <p className="subtitle">
            Prendre du recul sur le marché — climat, macro, corrélations. Ne vote jamais.
          </p>
        </div>
        <div className="actions">
          {badge(liveOk ? 'DONNÉES LIVE' : loading ? 'CHARGEMENT' : 'HORS LIGNE', liveOk ? 'green' : 'gray')}
          <button type="button" className="subtle" onClick={() => void load()} disabled={loading}>
            Actualiser
          </button>
        </div>
      </div>

      {feedError ? (
        <p className="subtitle" style={{ marginBottom: 16 }}>
          {feedError}
        </p>
      ) : null}

      <div className="metrics">
        <div className="metric">
          <div className="metric-label">
            Climat du marché<span>↗</span>
          </div>
          <div className="metric-value">{climateLabel}</div>
          <small>{climateMeta}</small>
        </div>
        <div className="metric">
          <div className="metric-label">
            Dominance BTC<span>↗</span>
          </div>
          <div className="metric-value">
            {btcDom != null
              ? `${btcDom.toLocaleString('fr-FR', { maximumFractionDigits: 1, minimumFractionDigits: 1 })} %`
              : loading
                ? '…'
                : '—'}
          </div>
          <small>{btcDom != null ? 'CoinGecko' : '—'}</small>
        </div>
        <div className="metric">
          <div className="metric-label">
            Volatilité<span>↗</span>
          </div>
          <div className="metric-value">{volLabel}</div>
          <small>{volMeta}</small>
        </div>
        <div className="metric">
          <div className="metric-label">
            Régime crypto<span>↗</span>
          </div>
          <div className="metric-value">{regimeLabel}</div>
          <small>{regimeMeta}</small>
        </div>
      </div>

      <div className="grid">
        <section className="card">
          <div className="card-head">
            <h2>Agenda économique</h2>
            {badge(events.length ? `${events.length} events` : loading ? '…' : 'Vide', 'gray')}
          </div>
          <div className="card-body">
            <div className="eyebrow">ÉVÉNEMENTS</div>
            {events.length === 0 ? (
              <div className="session">
                <span className="mono">—</span>
                <b>—</b>
                <span>{loading ? 'Chargement…' : 'Aucun événement cette semaine'}</span>
                {badge('—', 'gray')}
              </div>
            ) : (
              events.map((e, i) => (
                <div className="session" key={`${e.title}-${i}`}>
                  <span className="mono">{fmtEventTime(e.date)}</span>
                  <b>{e.country || '—'}</b>
                  <span>{e.title || '—'}</span>
                  {impactBadge(e.impact)}
                </div>
              ))
            )}
            <p style={{ fontSize: 11, color: 'var(--muted)' }}>
              Le contexte macro éclaire la décision, sans voter dans le signal technique.
            </p>
          </div>
        </section>

        <section className="card">
          <div className="card-head">
            <h2>Régime par classe d’actifs</h2>
            {badge(
              regimes.some((r) => r.badge !== 'Non disponible')
                ? 'RSI / ATR'
                : loading
                  ? '…'
                  : '—',
              'gray',
            )}
          </div>
          <div className="card-body">
            {(regimes.length > 0 ? regimes : DISPLAY_CLASSES.map((c) => ({
              assetClass: c,
              label: CLASS_LABELS[c],
              badge: loading ? '…' : '—',
              tone: 'gray' as BadgeTone,
              detail: '',
            }))).map((r) => (
              <div className="statline" key={r.assetClass}>
                <span>
                  {r.label}
                  {r.detail ? (
                    <small style={{ display: 'block', color: 'var(--muted)', fontSize: 11 }}>
                      {r.detail}
                    </small>
                  ) : null}
                </span>
                <b>{badge(r.badge, r.tone)}</b>
              </div>
            ))}
            {wiredCount > 0 ? (
              <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 8 }}>
                {wiredCount} instruments câblés · flagships uniquement
              </p>
            ) : null}
          </div>
        </section>
      </div>

      <div className="grid equal">
        <section className="card">
          <div className="card-head">
            <h2>Corrélations · crypto</h2>
            {badge(corr ? `LIVE · n=${corr.sample_size}` : loading ? '…' : '—', corr ? 'green' : 'gray')}
          </div>
          <div className="card-body">
            <div className="chart-labels">
              {heatLabels.slice(0, 5).map((s) => (
                <span key={s}>{s}</span>
              ))}
            </div>
            <div className="heatmap">
              {heatCells.map((cell, i) => (
                <div key={i} className={cell.strong ? 'strong' : undefined}>
                  {cell.v}
                </div>
              ))}
            </div>
            <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 10 }}>
              Pearson sur log-returns 1h — lecture seule, hors pipeline.
            </p>
          </div>
        </section>

        <section className="card">
          <div className="card-head">
            <h2>Points de vigilance</h2>
            {badge(`${vigilance.length}`, 'gray')}
          </div>
          <div className="card-body">
            {vigilance.map((item) => (
              <div className="step" key={item.id}>
                <b>{item.title}</b>
                <p>{item.body}</p>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="card" style={{ marginTop: 16 }}>
        <div className="card-head">
          <h2>Actualités crypto</h2>
          {badge(news.length ? `${news.length}` : loading ? '…' : 'Vide', 'gray')}
        </div>
        <div className="card-body">
          {news.length === 0 ? (
            <p style={{ fontSize: 12, color: 'var(--muted)', margin: 0 }}>
              {loading ? 'Chargement des flux RSS…' : 'Aucun titre disponible (RSS dégradé).'}
            </p>
          ) : (
            <ul className="ctx-news-list">
              {news.map((item, i) => (
                <li key={`${item.url}-${i}`}>
                  <a href={item.url} target="_blank" rel="noreferrer noopener">
                    {item.title}
                  </a>
                  <small>
                    {item.source || '—'} · {fmtNewsTime(item.published_at)}
                  </small>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  )
}
