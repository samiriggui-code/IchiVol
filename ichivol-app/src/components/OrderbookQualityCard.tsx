/**
 * OB-1 — carte « Carnet d'ordres · collecte » : qualité mesurée de la collecte (pas un signal).
 * Une minute absente compte comme non mesurée, jamais comme carnet vide.
 */

import { useEffect, useState } from 'react'
import { bookStateLabel, bookStateTone, getOrderbookQuality, type OrderbookQuality } from '../lib/orderbook'

function fmt(v: number | null | undefined, digits = 2): string {
  return v == null ? '—' : v.toLocaleString('fr-FR', { maximumFractionDigits: digits, minimumFractionDigits: digits })
}

export function OrderbookQualityCard({ symbol = 'BTCUSDT', hours = 24 }: { symbol?: string; hours?: number }) {
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
    <section className="card" style={{ marginTop: 16 }}>
      <div className="card-head">
        <h2>Carnet d’ordres · collecte</h2>
        <span className={`tag ${bookStateTone(q ? state : 'UNAVAILABLE')}`}>
          {q ? bookStateLabel(state, q.status.reason) : error ? 'Erreur' : '…'}
        </span>
      </div>
      <div className="card-body">
        {q ? (
          <>
            <div className="statline">
              <span>Instrument</span>
              <b>
                {q.symbol} · {q.venue}
              </b>
            </div>
            <div className="statline">
              <span>Minutes synchronisées ({q.window_hours} h)</span>
              <b>
                {fmt(q.synced_pct, 1)} % · {q.states.SYNCED}/{q.expected_minutes}
              </b>
            </div>
            <div className="statline">
              <span>Minutes non mesurées</span>
              <b>
                {q.missing_minutes + q.states.PARTIAL + q.states.STALE + q.states.UNAVAILABLE}
              </b>
            </div>
            <div className="statline">
              <span>Trous carnet / transactions</span>
              <b>
                {q.book_gaps} / {q.trade_gaps}
              </b>
            </div>
            <div className="statline">
              <span>Spread médian · p95</span>
              <b>
                {fmt(q.spread_bps_median)} · {fmt(q.spread_bps_p95)} pb
              </b>
            </div>
            {q.status.last_error ? (
              <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 8 }}>Dernière erreur : {q.status.last_error}</p>
            ) : null}
          </>
        ) : (
          <p style={{ fontSize: 12, color: 'var(--muted)', margin: 0 }}>
            {error ? `Indisponible : ${error}` : 'Chargement…'}
          </p>
        )}
        <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 10 }}>
          Une seule plateforme (Binance spot) : ne représente pas tout le marché. Liquidité affichée ≠ volume exécuté ;
          ni carte de liquidations, ni stops. Observation seulement, hors décisions.
        </p>
      </div>
    </section>
  )
}
