import { useEffect, useState } from 'react'
import {
  fetchContextCalendar,
  fetchContextNews,
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

/** News RSS + calendrier macro — opt-in context, hors pipeline. */
export function ContextFeedsPanel() {
  const [news, setNews] = useState<ContextNewsItem[] | null>(null)
  const [events, setEvents] = useState<ContextCalendarEvent[] | null>(null)
  const [newsErr, setNewsErr] = useState<string | null>(null)
  const [calErr, setCalErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    void Promise.allSettled([
      fetchContextNews({ limit: 12 }).then((items) => {
        if (!cancelled) {
          setNews(items)
          setNewsErr(null)
        }
      }),
      fetchContextCalendar({ limit: 16 }).then((ev) => {
        if (!cancelled) {
          setEvents(ev)
          setCalErr(null)
        }
      }),
    ]).then((results) => {
      if (cancelled) return
      if (results[0].status === 'rejected') {
        setNewsErr(
          results[0].reason instanceof Error
            ? results[0].reason.message
            : 'News indisponibles',
        )
      }
      if (results[1].status === 'rejected') {
        setCalErr(
          results[1].reason instanceof Error
            ? results[1].reason.message
            : 'Calendrier indisponible',
        )
      }
      setLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="context-feeds">
      <header className="context-feeds-head">
        <div>
          <p className="corr-kicker">Adapters context · opt-in</p>
          <h3>News &amp; calendrier</h3>
          <p className="muted corr-lede">
            Flux gratuits (RSS + macro semaine). Lecture seule — jamais branchés
            sur Ichimoku × RVOL ni sur les portes.
          </p>
        </div>
        {loading && <span className="panel-meta">chargement…</span>}
      </header>

      <div className="context-feeds-grid">
        <section className="context-feed-col" aria-label="Actualités crypto">
          <h4>Actualités</h4>
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
                    {item.published_at != null && (
                      <span>{fmtPub(item.published_at)}</span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="context-feed-col" aria-label="Calendrier macro">
          <h4>Calendrier (semaine)</h4>
          {calErr && <p className="muted">{calErr}</p>}
          {!calErr && events && events.length === 0 && (
            <p className="muted">Aucun événement cette semaine.</p>
          )}
          {events && events.length > 0 && (
            <ul className="context-cal-list">
              {events.map((e, i) => (
                <li key={`${e.date}-${e.title}-${i}`}>
                  <div className="context-cal-top">
                    <span className={`context-impact ${impactClass(e.impact)}`}>
                      {e.impact || '—'}
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
      </div>
    </div>
  )
}
