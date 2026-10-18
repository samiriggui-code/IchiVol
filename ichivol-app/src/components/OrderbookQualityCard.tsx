/**
 * OB-1 — carte « Carnet d'ordres · collecte » : qualité mesurée de la collecte (pas un signal).
 * Une minute absente compte comme non mesurée, jamais comme carnet vide.
 */

import { useEffect, useState } from 'react'
import { bookStateLabel, bookStateTone, getOrderbookQuality, type OrderbookQuality } from '../lib/orderbook'

function fmt(v: number | null | undefined, digits = 2): string {
  return v == null ? '—' : v.toLocaleString('fr-FR', { maximumFractionDigits: digits, minimumFractionDigits: digits })
}

const TONE_CLASS: Record<string, string> = { green: 'is-mint', amber: 'is-amber', red: 'is-sell', gray: 'is-muted' }

export function OrderbookQualityCard({
  symbol = 'BTCUSDT',
  hours = 24,
  className,
}: {
  symbol?: string
  hours?: number
  className?: string
}) {
  const [q, setQ] = useState<OrderbookQuality | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    getOrderbookQuality(symbol, hours)
      .then((r) => {
        if (!cancelled) setQ(r)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      })
    return () => {
      cancelled = true
    }
  }, [symbol, hours])

  const state = q?.status.state ?? 'UNAVAILABLE'
  return (
    <section className={`iv-card ob-card${className ? ` ${className}` : ''}`}>
      <div className="iv-card-head">
        <div className="iv-card-tabs">
          <span className="iv-card-tab is-on">Carnet d’ordres · collecte</span>
        </div>
        <div className="iv-card-tools">
          <span className={`iv-tag ${TONE_CLASS[bookStateTone(q ? state : 'UNAVAILABLE')] ?? 'is-muted'}`}>
            {q ? bookStateLabel(state, q.status.reason) : error ? 'Erreur' : '…'}
          </span>
        </div>
      </div>
      <div className="iv-card-body">
        {q ? (
          <>
            <div className="iv-row">
              Instrument
              <span className="iv-row-v">
                {q.symbol} · {q.venue}
              </span>
            </div>
            <div className="iv-row">
              Minutes synchronisées ({q.window_hours} h)
              <span className="iv-row-v">
                {fmt(q.synced_pct, 1)} % · {q.states.SYNCED}/{q.expected_minutes}
              </span>
            </div>
            <div className="iv-row">
              Minutes non mesurées
              <span className="iv-row-v">
                {q.missing_minutes + q.states.PARTIAL + q.states.STALE + q.states.UNAVAILABLE}
              </span>
            </div>
            <div className="iv-row">
              Trous carnet / transactions
              <span className="iv-row-v">
                {q.book_gaps} / {q.trade_gaps}
              </span>
            </div>
            <div className="iv-row">
              Spread médian · p95
              <span className="iv-row-v">
                {fmt(q.spread_bps_median)} · {fmt(q.spread_bps_p95)} pb
              </span>
            </div>
            {q.status.last_error ? <p className="iv-note ob-note">Dernière erreur : {q.status.last_error}</p> : null}
          </>
        ) : (
          <p className="iv-note ob-note">{error ? `Indisponible : ${error}` : 'Chargement…'}</p>
        )}
        <p className="iv-note ob-foot">
          Une seule plateforme (Binance spot) : ne représente pas tout le marché. Liquidité affichée ≠ volume exécuté ;
          ni carte de liquidations, ni stops. Observation seulement, hors décisions.
        </p>
      </div>
    </section>
  )
}
