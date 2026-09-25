import { useEffect, useMemo, useState } from 'react'
import {
  fetchContextCalendar,
  fetchContextNews,
  impactLabelFr,
  type ContextCalendarEvent,
  type ContextNewsItem,
} from '../lib/contextFeeds'

function fmtPub(ts: number | null): string {
  if (ts == null) return ''
  try {
    return new Date(ts * 1000).toLocaleString('fr-FR', {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return ''
  }
}

function fmtEventDate(iso: string): string {
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    return d.toLocaleString('fr-FR', {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function impactClass(impact: string): string {
  const i = impact.toLowerCase()
  if (i === 'high') return 'is-high'
  if (i === 'medium') return 'is-medium'
  if (i === 'low') return 'is-low'
  if (i === 'holiday') return 'is-holiday'
  return 'is-unknown'
}

type ImpactFilter = 'all' | 'high' | 'high_medium'

type Props = {
  /** Afficher le flux RSS crypto (CoinDesk / CoinTelegraph). */
  showNews?: boolean
  /** Calendrier en premier (forex / macro). */
  calendarFirst?: boolean
  calendarLimit?: number
  defaultImpact?: ImpactFilter
}

/** News RSS + calendrier macro — lecture seule. */
export function ContextFeedsPanel({
  showNews = true,
  calendarFirst = false,
  calendarLimit = 24,
  defaultImpact = 'all',
}: Props) {
  const [news, setNews] = useState<ContextNewsItem[] | null>(null)
  const [events, setEvents] = useState<ContextCalendarEvent[] | null>(null)
  const [newsErr, setNewsErr] = useState<string | null>(null)
  const [calErr, setCalErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [impact, setImpact] = useState<ImpactFilter>(defaultImpact)

  useEffect(() => {
    setImpact(defaultImpact)
  }, [defaultImpact])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    const jobs: Promise<void>[] = [
      fetchContextCalendar({ limit: calendarLimit })
        .then((ev) => {
          if (!cancelled) {
            setEvents(ev)
            setCalErr(null)
          }
        })
        .catch((e: unknown) => {
          if (!cancelled) {
            setCalErr(e instanceof Error ? e.message : 'Calendrier indisponible')
          }
        }),
    ]
    if (showNews) {
      jobs.push(
        fetchContextNews({ limit: 12 })
          .then((items) => {
            if (!cancelled) {
              setNews(items)
              setNewsErr(null)
            }
          })
          .catch((e: unknown) => {
            if (!cancelled) {
              setNewsErr(e instanceof Error ? e.message : 'News indisponibles')
            }
          }),
      )
    } else {
      setNews(null)
      setNewsErr(null)
    }

    void Promise.allSettled(jobs).finally(() => {
      if (!cancelled) setLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [showNews, calendarLimit])

  const filteredEvents = useMemo(() => {
    if (!events) return []
    return events.filter((e) => {
      const i = e.impact.toLowerCase()
      if (impact === 'all') return true
      if (impact === 'high') return i === 'high'
      return i === 'high' || i === 'medium'
    })
  }, [events, impact])

  const calendarBlock = (
    <section className="context-feed-col" aria-label="Calendrier macro">
      <div className="context-cal-head">
        <h4>Calendrier macro (semaine)</h4>
        <div className="market-class-tabs context-impact-tabs" role="tablist" aria-label="Impact">
          {(
            [
              { id: 'high' as const, label: 'Fort' },
              { id: 'high_medium' as const, label: 'Fort+Moyen' },
              { id: 'all' as const, label: 'Tout' },
            ] as const
          ).map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={impact === t.id}
              className={impact === t.id ? 'is-active' : undefined}
              onClick={() => setImpact(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>
      <p className="muted context-feed-hint">
        NFP, CPI, banques centrales… — utile surtout pour le forex et le risk-on / risk-off.
      </p>
      {calErr && <p className="muted">{calErr}</p>}
      {!calErr && filteredEvents.length === 0 && (
        <p className="muted">Aucun événement pour ce filtre.</p>
      )}
      {filteredEvents.length > 0 && (
        <ul className="context-cal-list">
          {filteredEvents.map((e, i) => (
            <li key={`${e.date}-${e.title}-${i}`}>
              <div className="context-cal-top">
                <span className={`context-impact ${impactClass(e.impact)}`}>
                  {impactLabelFr(e.impact)}
                </span>
                <span className="context-cal-country">{e.country || '—'}</span>
                <span className="muted context-cal-when">{fmtEventDate(e.date)}</span>
              </div>
              <strong className="context-cal-title">{e.title}</strong>
              {(e.forecast || e.previous) && (
                <p className="context-cal-nums muted">
                  {e.forecast != null && <span>Prév. {e.forecast}</span>}
                  {e.previous != null && <span>Préc. {e.previous}</span>}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )

  const newsBlock = showNews ? (
    <section className="context-feed-col" aria-label="Actualités crypto">
      <h4>Actualités crypto (RSS)</h4>
      <p className="muted context-feed-hint">CoinDesk · CoinTelegraph — hors pipeline IchiVol.</p>
      {newsErr && <p className="muted">{newsErr}</p>}
      {!newsErr && news && news.length === 0 && (
        <p className="muted">Aucun titre pour le moment.</p>
      )}
      {news && news.length > 0 && (
        <ul className="context-news-list">
          {news.map((item) => (
            <li key={`${item.source}-${item.url}`}>
              <a href={item.url} target="_blank" rel="noreferrer">
                {item.title}
              </a>
              <span className="context-news-meta">
                <span className="context-news-source">{item.source}</span>
                {item.published_at != null && <span>{fmtPub(item.published_at)}</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  ) : null

  return (
    <div className={`context-feeds panel${calendarFirst ? ' is-cal-first' : ''}`}>
      <header className="context-feeds-head">
        <div>
          <p className="corr-kicker">Lecture seule</p>
          <h3>{calendarFirst ? 'Macro & news' : 'News & calendrier'}</h3>
        </div>
        {loading && <span className="panel-meta">chargement…</span>}
      </header>

      <div className={`context-feeds-grid${showNews ? '' : ' is-single'}`}>
        {calendarFirst ? (
          <>
            {calendarBlock}
            {newsBlock}
          </>
        ) : (
          <>
            {newsBlock}
            {calendarBlock}
          </>
        )}
      </div>
    </div>
  )
}
