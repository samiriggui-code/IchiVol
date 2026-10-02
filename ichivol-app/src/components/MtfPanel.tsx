/**
 * MTF-1 — Tendances multi-horizons (1h · 4h · 1d · 1w).
 *
 * Deux modes :
 * - live : `symbol` + `timeframe` → GET /api/engine/mtf/{symbol} (matrice + phrase + lecture portefeuille) ;
 * - enregistré : `stored` = matrice copiée dans `entry_signal` au moment de l'action (ce que le moteur savait,
 *   jamais recalculé).
 *
 * Lecture seule : la matrice n'entre pas dans la décision (filtre MTF testé dans VP3 : pas d'edge).
 */

import { useEffect, useState } from 'react'
import {
  agreementCount,
  directionLabel,
  directionTone,
  fmtUtc,
  getMtf,
  relationLabel,
  stateLabel,
  stateTone,
  unavailableReasonLabel,
  type MtfMatrix,
  type MtfResponse,
} from '../lib/mtf'
import './MtfPanel.css'

interface Props {
  symbol?: string
  timeframe?: string
  /** Matrice enregistrée (fiche position) : pas d'appel réseau. */
  stored?: MtfMatrix | null
  storedLabel?: string
}

function fmtNum(v: number | null, digits = 2): string {
  return v == null ? '—' : v.toLocaleString('fr-FR', { maximumFractionDigits: digits, minimumFractionDigits: digits })
}

function MatrixTable({ matrix }: { matrix: MtfMatrix }) {
  return (
    <div className="mtf-table-wrap">
      <table className="mtf-table">
        <thead>
          <tr>
            <th>Horizon</th>
            <th>Tendance</th>
            <th>Données</th>
            <th>Relation</th>
            <th className="mtf-col-opt">Bougie close</th>
            <th className="mtf-col-opt">RVOL</th>
            <th className="mtf-col-opt">ATR</th>
          </tr>
        </thead>
        <tbody>
          {matrix.horizons.map((h) => {
            const unavailable = h.state === 'UNAVAILABLE'
            return (
              <tr key={h.timeframe} className={h.role === 'decision' ? 'is-decision' : undefined}>
                <td>
                  {h.timeframe}
                  {h.role === 'decision' ? ' · décision' : h.role === 'parent' ? ' · parent' : ''}
                </td>
                <td className="mtf-trend">
                  {unavailable ? (
                    <span className="mtf-muted" title={h.unavailable_reason ?? undefined}>
                      {unavailableReasonLabel(h.unavailable_reason)}
                    </span>
                  ) : (
                    <span className={`mtf-tag ${directionTone(h.direction)}`}>{directionLabel(h.direction)}</span>
                  )}
                  {h.provisional_direction && h.provisional_direction !== h.direction ? (
                    <span className="mtf-provisional" title="Calculé avec la bougie en formation : peut changer jusqu'à la clôture. Jamais utilisé.">
                      provisoire : {directionLabel(h.provisional_direction).toLowerCase()}
                    </span>
                  ) : null}
                </td>
                <td>
                  <span className={`mtf-tag ${stateTone(h.state)}`}>{stateLabel(h.state)}</span>
                </td>
                <td>{h.relation === 'self' ? '—' : relationLabel(h.relation)}</td>
                <td className="mtf-col-opt">{fmtUtc(h.bar_close)}</td>
                <td className="mtf-col-opt">{h.rvol == null ? '—' : `${fmtNum(h.rvol)}×`}</td>
                <td className="mtf-col-opt">{h.atr_regime ? h.atr_regime.toLowerCase() : '—'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export function MtfPanel({ symbol, timeframe = '1h', stored, storedLabel }: Props) {
  const live = !stored && !!symbol
  const key = live ? `${symbol}|${timeframe}` : ''
  // Résultat étiqueté par sa requête : « chargement » se déduit au rendu (pas de setState synchrone dans l'effet).
  const [result, setResult] = useState<{ key: string; data: MtfResponse | null; error: string | null }>({
    key: '',
    data: null,
    error: null,
  })

  useEffect(() => {
    if (!key || !symbol) return
    let cancelled = false
    getMtf(symbol, timeframe)
      .then((r) => {
        if (!cancelled) setResult({ key, data: r, error: null })
      })
      .catch((e: unknown) => {
        if (!cancelled) setResult({ key, data: null, error: e instanceof Error ? e.message : String(e) })
      })
    return () => {
      cancelled = true
    }
  }, [key, symbol, timeframe])

  const current = result.key === key ? result : null
  const data = current?.data ?? null
  const error = current?.error ?? null
  const loading = live && current === null

  const matrix = stored ?? data?.matrix ?? null

  return (
    <section className="mtf-panel" aria-label="Tendances multi-horizons">
      <div className="mtf-panel-head">
        <h3>Tendances multi-horizons</h3>
        <span className="mtf-muted">
          {stored
            ? storedLabel ?? `Enregistré au moment de l'action · ${fmtUtc(stored.computed_at)}`
            : matrix
              ? `${matrix.venue ?? '—'} · calculé ${fmtUtc(matrix.computed_at)}`
              : ''}
        </span>
      </div>

      {live && loading && !data ? <p className="mtf-muted">Chargement…</p> : null}
      {live && error ? <p className="mtf-error">Matrice indisponible : {error}</p> : null}

      {data?.sentence && !stored ? <p className="mtf-sentence">{data.sentence}</p> : null}

      {matrix ? (
        <>
          <MatrixTable matrix={matrix} />
          <dl className="mtf-lines">
            <dt>Accords</dt>
            <dd>{agreementCount(matrix.summary)}</dd>
            {data?.pipeline && !stored ? (
              <>
                <dt>Signal</dt>
                <dd>
                  {data.pipeline.decision} · direction Ichimoku {timeframe} {data.pipeline.direction}
                </dd>
              </>
            ) : null}
            {data?.portfolio && !stored ? (
              <>
                <dt>Portefeuille</dt>
                <dd>{data.portfolio.reading}</dd>
              </>
            ) : null}
            <dt>Méthode</dt>
            <dd className="mtf-muted">
              {matrix.method}. Bougies closes seulement ; « provisoire » = bougie en formation, jamais utilisée.
              Lecture seule : n'entre pas dans la décision (filtre multi-horizons testé dans VP3 : pas d'edge).
            </dd>
          </dl>
        </>
      ) : null}
      {stored === null ? (
        <p className="mtf-muted">Non enregistré pour cette position (ouverte avant MTF-1).</p>
      ) : null}
    </section>
  )
}
