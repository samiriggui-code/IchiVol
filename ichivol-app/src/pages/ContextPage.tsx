/**
 * Contexte — port littéral de design-reference/ichivol-workspace `contexte()` + page-head.
 * Classes HTML = maquette. Données = engine (manquant → « — »).
 */

import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  fetchContextCalendar,
  type ContextCalendarEvent,
} from '../lib/contextFeeds'
import { fetchCorrelations, type CorrelationMatrix } from '../lib/correlations'
import { displaySymbol } from '../lib/markets'
import {
  fetchFearGreed,
  fetchGlobalMarket,
  type FearGreed,
  type GlobalMarketData,
} from '../lib/marketContext'
import './ContextPage.css'

type BadgeTone = 'green' | 'amber' | 'red' | 'gray' | ''

const HEAT_SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT']

function badge(text: string, tone: BadgeTone = ''): ReactNode {
  let inferred = tone
  if (!inferred) {
    inferred = /PASSE|ACCEPTÉ|OUVERTE|VALIDÉ/i.test(text)
      ? 'green'
      : /REFUS|BLOQU|ERREUR/i.test(text)
        ? 'red'
        : /PRUDENCE|Élevé|ARMED|WATCH|TRIGGERED/i.test(text)
          ? 'amber'
          : ''
  }
  return <span className={`tag ${inferred}`.trim()}>{text}</span>
}

function fmtEventTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(+d)) return iso || '—'
  return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', hour12: false })
}

function impactBadge(impact: string): ReactNode {
  const t = impact.trim()
  if (!t) return badge('—', 'gray')
  if (/high|élev|elev/i.test(t)) return badge('Élevé', 'amber')
  if (/med|moy/i.test(t)) return badge('Moyen', 'gray')
  if (/low|faible/i.test(t)) return badge('Faible', 'gray')
  return badge(t, 'gray')
}

export function ContextPage() {
  const [global, setGlobal] = useState<GlobalMarketData | null>(null)
  const [fg, setFg] = useState<FearGreed | null>(null)
  const [events, setEvents] = useState<ContextCalendarEvent[]>([])
  const [corr, setCorr] = useState<CorrelationMatrix | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [g, f, cal, c] = await Promise.all([
        fetchGlobalMarket().catch(() => null),
        fetchFearGreed().catch(() => null),
        fetchContextCalendar({ limit: 8 }).catch(() => [] as ContextCalendarEvent[]),
        fetchCorrelations({ symbols: HEAT_SYMBOLS, timeframe: '1h', limit: 5 }).catch(
          () => null,
        ),
      ])
      setGlobal(g)
      setFg(f)
      setEvents(cal.slice(0, 3))
      setCorr(c)
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
          heatCells.push({ v: x.toFixed(2), strong: x > 0.85 })
        }
      }
    }
  } else {
    for (let i = 0; i < 25; i++) heatCells.push({ v: '—', strong: false })
  }

  return (
    <div className="ctx-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">07 / ICHIVOL WORKSPACE</div>
          <h1>Contexte</h1>
          <p className="subtitle">Prendre du recul sur le marché.</p>
        </div>
        <div className="actions">{badge('DONNÉES LIVE', 'gray')}</div>
      </div>

      <div className="metrics">
        <div className="metric">
          <div className="metric-label">
            Climat du marché<span>↗</span>
          </div>
          <div className="metric-value">
            {fg?.classification ?? (loading ? '—' : '—')}
          </div>
          <small>
            {fg != null ? `Fear & Greed ${fg.value}` : '—'}
          </small>
        </div>
        <div className="metric">
          <div className="metric-label">
            Dominance BTC<span>↗</span>
          </div>
          <div className="metric-value">
            {btcDom != null
              ? `${btcDom.toLocaleString('fr-FR', { maximumFractionDigits: 1, minimumFractionDigits: 1 })} %`
              : '—'}
          </div>
          <small>{btcDom != null ? 'CoinGecko' : '—'}</small>
        </div>
        <div className="metric">
          <div className="metric-label">
            Volatilité<span>↗</span>
          </div>
          <div className="metric-value">—</div>
          <small>ATR / prix · contexte</small>
        </div>
        <div className="metric">
          <div className="metric-label">
            Régime crypto<span>↗</span>
          </div>
          <div className="metric-value">—</div>
          <small>Concentration à surveiller</small>
        </div>
      </div>

      <div className="grid">
        <section className="card">
          <div className="card-head">
            <h2>Agenda économique</h2>
          </div>
          <div className="card-body">
            <div className="eyebrow">ÉVÉNEMENTS</div>
            {events.length === 0 ? (
              <div className="session">
                <span className="mono">—</span>
                <b>—</b>
                <span>—</span>
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
          </div>
          <div className="card-body">
            <div className="statline">
              <span>Crypto</span>
              <b>{badge('—', 'gray')}</b>
            </div>
            <div className="statline">
              <span>Forex</span>
              <b>{badge('—', 'gray')}</b>
            </div>
            <div className="statline">
              <span>Métaux</span>
              <b>{badge('—', 'gray')}</b>
            </div>
            <div className="statline">
              <span>Indices</span>
              <b>{badge('—', 'gray')}</b>
            </div>
            <div className="statline">
              <span>Actions</span>
              <b>{badge('—', 'gray')}</b>
            </div>
          </div>
        </section>
      </div>

      <div className="grid equal">
        <section className="card">
          <div className="card-head">
            <h2>Corrélations · 30 jours</h2>
            {badge(corr ? 'LIVE' : '—', 'gray')}
          </div>
          <div className="card-body">
            <div className="chart-labels">
              {heatLabels.slice(0, 5).map((s) => (
                <span key={s}>{s}</span>
              ))}
            </div>
            <div className="heatmap">
              {heatCells.map((c, i) => (
                <div key={i} className={c.strong ? 'strong' : undefined}>
                  {c.v}
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="card">
          <div className="card-head">
            <h2>Points de vigilance</h2>
          </div>
          <div className="card-body">
            <div className="step">
              <b>Exposition corrélée</b>
              <p>Plusieurs positions crypto peuvent réagir au même mouvement de BTC.</p>
            </div>
            <div className="step">
              <b>Volume inhabituel</b>
              <p>Un pic de volume peut accompagner un événement. Vérifier le contexte.</p>
            </div>
            <div className="step">
              <b>Gap et volatilité</b>
              <p>Relire le plan de risque si les conditions de marché changent.</p>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
