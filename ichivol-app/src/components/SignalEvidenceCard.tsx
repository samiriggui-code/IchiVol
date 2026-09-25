import { labelReason } from '../lib/decisionLabels'
import type { DecisionDetail } from '../lib/decisions'
import { VerdictBadge } from './VerdictBadge'

function pct(v: number | null | undefined, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '—'
  return `${(v * 100).toFixed(digits)}%`
}

function num(v: number | null | undefined, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '—'
  return v.toFixed(digits)
}

function ChipRow({ codes, tone }: { codes: string[]; tone?: 'risk' | 'ok' }) {
  if (!codes.length) return <p className="muted">—</p>
  return (
    <div className="chip-row">
      {codes.map((code) => (
        <span key={code} className={`sig-chip${tone === 'risk' ? ' risk-chip' : ''}`} title={code}>
          {labelReason(code)}
        </span>
      ))}
    </div>
  )
}

/** Preuves renvoyées par le moteur — aucun chiffre inventé. */
export function SignalEvidenceCard({ detail }: { detail: DecisionDetail }) {
  const ev = detail.evidence
  const hist = ev?.historical
  const ctx = (ev?.context ?? detail.context ?? {}) as {
    ichimoku?: { direction?: string; tk_state?: string; price_vs_cloud?: string }
    volume?: { rvol?: number | null; volume_type?: string; participation_state?: string }
    structure?: { trend?: string; breakout_state?: string }
    regime?: { pipeline_regime?: string; codes?: string[] }
  }

  const whyNot =
    detail.why_not ??
    (detail.pipeline?.direction === 'SHORT' ? ev?.why_not_short : ev?.why_not_long) ??
    detail.risks ??
    []

  const positive = detail.positive_evidence ?? ev?.positive_evidence ?? detail.reasons
  const contradictions = detail.contradictions ?? ev?.contradictions ?? []
  const invalidation = detail.invalidation ?? ev?.invalidation ?? []
  const volumeType = detail.volume_type ?? detail.rvol_detail?.volume_type ?? ctx.volume?.volume_type

  return (
    <article className="signal-evidence-card" aria-label="Preuves du signal">
      <header className="sec-head">
        <div>
          <h3 className="sec-symbol">{detail.symbol}</h3>
          <span className="muted">
            {detail.timeframe}
            {volumeType ? ` · volume ${volumeType}` : ''}
          </span>
        </div>
        <VerdictBadge decision={detail.decision} pipeline={detail.pipeline} variant="detail" />
      </header>

      <section className="sec-block">
        <span className="subhead">Ichimoku</span>
        <p>
          {ctx.ichimoku?.direction ?? detail.ichimoku.direction}
          {ctx.ichimoku?.tk_state ? ` · TK ${ctx.ichimoku.tk_state}` : ''}
          {ctx.ichimoku?.price_vs_cloud ? ` · prix ${ctx.ichimoku.price_vs_cloud} Kumo` : ''}
        </p>
      </section>

      <section className="sec-block">
        <span className="subhead">RVOL</span>
        <p>
          {detail.rvol != null ? `${detail.rvol.toFixed(2)}×` : '—'}
          {ctx.volume?.participation_state ? ` · ${ctx.volume.participation_state}` : ''}
        </p>
      </section>

      {(ctx.structure || ctx.regime) && (
        <section className="sec-grid">
          {ctx.structure && (
            <div className="sec-block">
              <span className="subhead">Structure</span>
              <p>
                {ctx.structure.trend}
                {ctx.structure.breakout_state && ctx.structure.breakout_state !== 'NONE'
                  ? ` · BOS ${ctx.structure.breakout_state}`
                  : ''}
              </p>
            </div>
          )}
          {ctx.regime && (
            <div className="sec-block">
              <span className="subhead">Régime</span>
              <p>{ctx.regime.pipeline_regime}</p>
            </div>
          )}
        </section>
      )}

      <section className="sec-block">
        <span className="subhead">Preuves positives</span>
        <ChipRow codes={positive} tone="ok" />
      </section>

      <section className="sec-block">
        <span className="subhead">Pourquoi pas</span>
        <ChipRow codes={whyNot} tone="risk" />
      </section>

      {contradictions.length > 0 && (
        <section className="sec-block">
          <span className="subhead">Contradictions</span>
          <ChipRow codes={contradictions} tone="risk" />
        </section>
      )}

      <section className="sec-block">
        <span className="subhead">Invalidation</span>
        <ChipRow codes={invalidation} tone="risk" />
      </section>

      <section className="sec-block sec-hist">
        <span className="subhead">Preuves historiques</span>
        {!hist ? (
          <p className="muted">Pas encore calculée pour ce signal.</p>
        ) : (
          <>
            <p>
              <strong>{hist.sample_size}</strong> configurations comparables
              {' · '}
              <span className="muted">
                qualité {hist.sample_quality} · {hist.status}
              </span>
            </p>
            {ev?.calibration_note ? <p className="muted">{ev.calibration_note}</p> : null}
            {hist.status !== 'NO_DATA' && (
              <dl className="sec-stats">
                <div>
                  <dt>Horizon</dt>
                  <dd>{hist.horizon} barres</dd>
                </div>
                <div>
                  <dt>Moyenne</dt>
                  <dd>{pct(hist.mean_return_pct)}</dd>
                </div>
                <div>
                  <dt>Médiane</dt>
                  <dd>{pct(hist.median_return_pct)}</dd>
                </div>
                <div>
                  <dt title="Max Favorable Excursion">MFE</dt>
                  <dd>{pct(hist.mean_mfe_pct)}</dd>
                </div>
                <div>
                  <dt title="Max Adverse Excursion">MAE</dt>
                  <dd>{pct(hist.mean_mae_pct)}</dd>
                </div>
                <div>
                  <dt>Taux favorable</dt>
                  <dd>
                    {hist.favorable_rate != null ? `${(hist.favorable_rate * 100).toFixed(1)}%` : '—'}
                  </dd>
                </div>
              </dl>
            )}
          </>
        )}
      </section>

      {ev?.ablation && ev.ablation.length > 0 && (
        <section className="sec-block">
          <span className="subhead">Ablation</span>
          <table className="sec-ablation">
            <thead>
              <tr>
                <th>Modèle</th>
                <th>N</th>
                <th>Favorable</th>
                <th>Moyenne</th>
              </tr>
            </thead>
            <tbody>
              {ev.ablation.map((row) => (
                <tr key={row.label}>
                  <td>{row.label}</td>
                  <td className="mono">{row.sample_size}</td>
                  <td className="mono">
                    {row.favorable_rate != null ? `${(row.favorable_rate * 100).toFixed(1)}%` : '—'}
                  </td>
                  <td className="mono">{pct(row.mean_return_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <footer className="sec-foot muted">
        {ev?.evidence_engine_version ?? 'evidence'} · {detail.strategy_version}
        {ev?.feature_version ? ` · ${ev.feature_version}` : ''}
        {' · '}
        conf. combiner {num(detail.confidence * 100, 0)}%
      </footer>
    </article>
  )
}
