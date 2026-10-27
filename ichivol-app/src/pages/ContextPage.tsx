/**
 * Contexte — climat marché (lecture seule, ne vote jamais).
 * Layout maquette `.ctx-page` + données live (CoinGecko, F&G, calendar, news, ATR, corr).
 */

import { Fragment, useCallback, useEffect, useMemo, useState, type CSSProperties, type ReactNode } from 'react'
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
import { OrderbookQualityCard } from '../components/OrderbookQualityCard'
import { TablePager } from '../components/table/TablePager'
import { usePaged } from '../components/table/usePaged'
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

const TONE_CLASS: Record<BadgeTone, string> = {
  green: 'is-mint',
  amber: 'is-amber',
  red: 'is-sell',
  gray: 'is-muted',
  '': 'is-cyan',
}

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
  return <span className={`iv-tag ${TONE_CLASS[inferred]}`}>{text}</span>
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
      setEvents(cal)
      setNews(newsItems)
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
              detail: 'Aucune source branchée',
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

      setVigilance(nextVigilance)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  // Agenda et actualités : tout ce que l'API renvoie, page par page.
  const eventsPaged = usePaged(events, 'contexte-agenda')
  const newsPaged = usePaged(news, 'contexte-actualites')

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

  const heatCells: { v: string; strong: boolean; n: number | null }[] = []
  if (corr?.matrix?.length) {
    const n = Math.min(5, corr.symbols.length)
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const x = corr.matrix[i]?.[j]
        if (x == null || !Number.isFinite(x)) {
          heatCells.push({ v: '—', strong: false, n: null })
        } else {
          heatCells.push({ v: x.toFixed(2), strong: Math.abs(x) > 0.85, n: x })
        }
      }
    }
  } else {
    for (let i = 0; i < 25; i++) heatCells.push({ v: loading ? '…' : '—', strong: false, n: null })
  }

  const liveOk = Boolean(global || fg || events.length || news.length || corr || btcSnap)
  const wiredCount = instruments.filter((i) => i.wired).length

  const heatN = Math.min(5, heatLabels.length)
  const fgPct = fg != null && Number.isFinite(fg.value) ? Math.max(0, Math.min(100, fg.value)) : null

  return (
    <div className="ctx-page">
      <div className="iv-ph">
        <div>
          <div className="iv-meta">Contexte · données live · avant d’agir</div>
          <h1>Contexte</h1>
          <p>Prendre du recul sur le marché — climat, macro, corrélations. Ne vote jamais.</p>
        </div>
        <div className="iv-ph-act">
          <span className={`iv-chip ${liveOk ? 'is-mint' : 'is-muted'}`}>
            <i className={`iv-dot${liveOk ? '' : ' is-off'}`} />
            {liveOk ? 'Données live' : loading ? 'Chargement' : 'Hors ligne'}
          </span>
          <button type="button" className="iv-btn" onClick={() => void load()} disabled={loading}>
            Actualiser
          </button>
        </div>
      </div>

      {feedError ? <div className="iv-empty is-error ctx-feed-error">{feedError}</div> : null}

      <div className="iv-kpis ctx-kpis">
        <div className="iv-kpi">
          <div className="iv-kpi-k">Climat du marché</div>
          <div className="iv-kpi-v">{climateLabel}</div>
          <div className="iv-kpi-s">{climateMeta}</div>
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">Dominance BTC</div>
          <div className="iv-kpi-v">
            {btcDom != null
              ? `${btcDom.toLocaleString('fr-FR', { maximumFractionDigits: 1, minimumFractionDigits: 1 })} %`
              : loading
                ? '…'
                : '—'}
          </div>
          <div className="iv-kpi-s">{btcDom != null ? 'CoinGecko' : '—'}</div>
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">Volatilité</div>
          <div className="iv-kpi-v">{volLabel}</div>
          <div className="iv-kpi-s">{volMeta}</div>
        </div>
        <div className="iv-kpi">
          <div className="iv-kpi-k">{fg ? 'Climat crypto' : 'Régime crypto'}</div>
          <div className="iv-kpi-v">{regimeLabel}</div>
          <div className="iv-kpi-s">{regimeMeta}</div>
        </div>
      </div>

      <div className="iv-grid">
        <section className="iv-card iv-s4 iv-m-s12 ctx-t-half">
          <div className="iv-card-head">
            <div className="iv-card-tabs">
              <span className="iv-card-tab is-on">Régime par classe d’actifs</span>
            </div>
            <div className="iv-card-tools">
              {regimes.some((r) => r.badge !== 'Non disponible') ? 'RSI / ATR' : loading ? '…' : '—'}
            </div>
          </div>
          <div className="iv-card-body ctx-regimes">
            {(regimes.length > 0
              ? regimes
              : DISPLAY_CLASSES.map((c) => ({
                  assetClass: c,
                  label: CLASS_LABELS[c],
                  badge: loading ? '…' : '—',
                  tone: 'gray' as BadgeTone,
                  detail: '',
                }))
            ).map((r) => (
              <div className="ctx-regime" key={r.assetClass}>
                <span className="ctx-regime-name">{r.label}</span>
                {badge(r.badge, r.tone)}
                <span className="ctx-regime-detail">{r.detail || '—'}</span>
              </div>
            ))}
            {wiredCount > 0 ? <p className="iv-cap ctx-wired">{wiredCount} instruments câblés · flagships uniquement</p> : null}
          </div>
        </section>

        <section className="apex-card iv-s5 iv-m-s12 ctx-t-half ctx-vigil">
          <div className="iv-label">Points de vigilance</div>
          {vigilance.length === 0 ? (
            <p className="ctx-vigil-empty">
              {loading ? 'Chargement…' : 'Rien à signaler d’après les données disponibles.'}
            </p>
          ) : (
            <ul className="ctx-vigil-list">
              {vigilance.map((item) => (
                <li key={item.id}>
                  <span className="iv-kw">{item.title}</span> : {item.body}
                </li>
              ))}
            </ul>
          )}
          <div className="apex-card-foot">
            <span className="apex-card-sig">ichivol</span>
            <span className="iv-chip">
              {vigilance.length} point{vigilance.length > 1 ? 's' : ''}
            </span>
          </div>
        </section>

        <section className="iv-card iv-s3 iv-m-s12">
          <div className="iv-card-head">
            <div className="iv-card-tabs">
              <span className="iv-card-tab is-on">Climat crypto</span>
            </div>
          </div>
          <div className="iv-card-body">
            <div className="ctx-fng">
              <span className={`ctx-fng-v${fgPct != null && (fgPct <= 25 || fgPct >= 75) ? ' warn' : ''}`}>
                {fgPct != null ? fgPct : loading ? '…' : '—'}
              </span>
              <div>
                <div className="ctx-fng-label">{fg ? fearGreedFr(fg.classification) : '—'}</div>
                <div className="iv-cap">Fear &amp; Greed · 0 → 100</div>
              </div>
            </div>
            <div className="iv-bar is-amber ctx-fng-bar">
              <i style={{ width: `${fgPct ?? 0}%` }} />
            </div>
            <div className="ctx-fng-legend">
              <span>Peur extrême</span>
              <span>Avidité extrême</span>
            </div>
          </div>
        </section>
      </div>

      <div className="iv-grid">
        <section className="iv-card iv-s5 iv-m-s12 ctx-t-half">
          <div className="iv-card-head">
            <div className="iv-card-tabs">
              <span className="iv-card-tab is-on">Corrélations · crypto</span>
            </div>
            <div className="iv-card-tools">
              {corr ? (
                <span className="ok">Live · n={corr.sample_size}</span>
              ) : loading ? (
                '…'
              ) : (
                '—'
              )}
            </div>
          </div>
          <div className="iv-card-body iv-table-wrap">
            <div className="ctx-heat" style={{ gridTemplateColumns: `44px repeat(${heatN}, minmax(46px, 1fr))` }}>
              <div className="ctx-heat-h" />
              {heatLabels.slice(0, heatN).map((s) => (
                <div className="ctx-heat-h" key={`c-${s}`}>
                  {s}
                </div>
              ))}
              {heatLabels.slice(0, heatN).map((rowLabel, i) => (
                <Fragment key={`r-${rowLabel}`}>
                  <div className="ctx-heat-h">{rowLabel}</div>
                  {heatCells.slice(i * heatN, i * heatN + heatN).map((cell, j) => (
                    <div
                      key={j}
                      className={`ctx-heat-c${cell.n == null ? ' is-na' : cell.n < 0 ? ' is-neg' : ''}${
                        i === j ? ' is-diag' : ''
                      }${cell.strong && i !== j ? ' is-strong' : ''}`}
                      style={
                        cell.n != null
                          ? ({ '--a': `${Math.round(Math.abs(cell.n) * 55)}%` } as CSSProperties)
                          : undefined
                      }
                    >
                      {cell.v}
                    </div>
                  ))}
                </Fragment>
              ))}
            </div>
          </div>
          <div className="iv-card-foot">Pearson sur log-returns 1h — lecture seule, hors pipeline</div>
        </section>

        <section className="iv-card iv-s4 iv-m-s12 ctx-agenda">
          <div className="iv-card-head">
            <div className="iv-card-tabs">
              <span className="iv-card-tab is-on">Agenda économique</span>
            </div>
            <div className="iv-card-tools">{events.length ? `${events.length} événements` : loading ? '…' : 'Vide'}</div>
          </div>
          <div className="iv-card-body is-flush iv-table-wrap">
            <table className="iv-table is-compact">
              <thead>
                <tr>
                  <th>Quand</th>
                  <th>Pays</th>
                  <th>Événement</th>
                  <th>Impact</th>
                </tr>
              </thead>
              <tbody>
                {events.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="ctx-empty">
                      {loading ? 'Chargement…' : 'Aucun événement cette semaine'}
                    </td>
                  </tr>
                ) : (
                  eventsPaged.rows.map((e, i) => (
                    <tr key={`${e.title}-${eventsPaged.start + i}`}>
                      <td className="mono ctx-when">{fmtEventTime(e.date)}</td>
                      <td className="ctx-country">{e.country || '—'}</td>
                      <td className="ctx-event">{e.title || '—'}</td>
                      <td>{impactBadge(e.impact)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <TablePager paged={eventsPaged} label="événements" />
          <div className="iv-card-foot">Le contexte macro éclaire la décision, sans voter dans le signal</div>
        </section>

        <OrderbookQualityCard className="iv-s3 iv-m-s12 ctx-t-half" />
      </div>

      <div className="iv-grid">
        <section className="iv-card iv-s12">
          <div className="iv-card-head">
            <div className="iv-card-tabs">
              <span className="iv-card-tab is-on">Actualités crypto</span>
            </div>
            <div className="iv-card-tools">{news.length ? `${news.length} titres · informatives` : loading ? '…' : 'Vide'}</div>
          </div>
          <div className="iv-card-body ctx-news">
            {news.length === 0 ? (
              <p className="iv-note ctx-news-empty">
                {loading ? 'Chargement des flux RSS…' : 'Aucun titre disponible (RSS dégradé).'}
              </p>
            ) : (
              <ul className="ctx-news-list">
                {newsPaged.rows.map((item, i) => (
                  <li key={`${item.url}-${newsPaged.start + i}`}>
                    <span className="ctx-news-t">{fmtNewsTime(item.published_at)}</span>
                    <a href={item.url} target="_blank" rel="noreferrer noopener">
                      {item.title}
                    </a>
                    <span className="ctx-news-s">{item.source || '—'}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <TablePager paged={newsPaged} label="titres" />
        </section>
      </div>
    </div>
  )
}
