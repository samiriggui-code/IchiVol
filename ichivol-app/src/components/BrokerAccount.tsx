import type { PaperOverview, PaperOverviewPosition } from '../lib/paper'
import { assetName, directionWords, eur, pct, price, signedEur } from '../lib/tradeStory'

function tone(v: number | null | undefined): string {
  if (v == null || v === 0) return ''
  return v > 0 ? 'up' : 'down'
}

function EquityCurve({ points, initial }: { points: { t: string; equity: number }[]; initial: number }) {
  if (points.length < 2) {
    return <p className="muted broker-curve-empty">La courbe apparaîtra après quelques cycles du moteur.</p>
  }
  const w = 600
  const h = 110
  const values = points.map((p) => p.equity)
  const min = Math.min(...values, initial)
  const max = Math.max(...values, initial)
  const span = max - min || 1
  const x = (i: number) => (i / (points.length - 1)) * w
  const y = (v: number) => h - ((v - min) / span) * (h - 8) - 4
  const d = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.equity).toFixed(1)}`).join(' ')
  const up = values[values.length - 1] >= initial
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="broker-curve" role="img" aria-label="Courbe de la valeur du portefeuille">
      <line x1="0" x2={w} y1={y(initial)} y2={y(initial)} className="broker-curve-base" />
      <path d={d} className={up ? 'broker-curve-line is-up' : 'broker-curve-line is-down'} fill="none" />
    </svg>
  )
}

/** En-tête « compte » façon broker : valeur, cash, investi, gains, courbe. */
export function BrokerAccount({ overview }: { overview: PaperOverview }) {
  const a = overview.account
  const totalPct = a.initial_cash ? a.total_pnl / a.initial_cash : null
  return (
    <div className="broker-account">
      <div className="broker-account-top">
        <div className="broker-equity">
          <span className="context-label">Valeur du portefeuille</span>
          <strong className="broker-equity-value">{eur(a.equity)}</strong>
          <span className={`broker-equity-delta ${tone(a.total_pnl)}`}>
            {signedEur(a.total_pnl)} ({pct(totalPct, 2)}) depuis le départ ({eur(a.initial_cash, 0)})
          </span>
        </div>
        <EquityCurve points={overview.equity_curve} initial={a.initial_cash} />
      </div>
      <div className="paper-perf-grid">
        <div className="context-card">
          <span className="context-label">Argent libre</span>
          <strong className="context-value">{eur(a.cash)}</strong>
        </div>
        <div className="context-card">
          <span className="context-label">Argent investi</span>
          <strong className="context-value">{eur(a.invested)}</strong>
        </div>
        <div className="context-card">
          <span className="context-label">Gain / perte en cours</span>
          <strong className={`context-value ${tone(a.unrealized_pnl)}`}>{signedEur(a.unrealized_pnl)}</strong>
        </div>
        <div className="context-card">
          <span className="context-label">Gain / perte encaissé</span>
          <strong className={`context-value ${tone(a.realized_pnl)}`}>{signedEur(a.realized_pnl)}</strong>
        </div>
        <div className="context-card">
          <span className="context-label">Variation 24 h</span>
          <strong className={`context-value ${tone(a.day_change)}`}>{signedEur(a.day_change)}</strong>
        </div>
        <div className="context-card">
          <span className="context-label">Positions ouvertes</span>
          <strong className="context-value">{a.open_positions}</strong>
        </div>
      </div>
      {(() => {
        const legacy = overview.positions.filter((p) => p.status === 'OPEN' && p.qty == null).length
        const unpriced = a.open_positions - a.priced_positions
        return (
          <>
            {legacy > 0 && (
              <p className="muted paper-perf-note">
                {legacy} position(s) ouvertes avant l’arrivée du capital virtuel : pas de montant
                investi, donc seule leur variation en % est affichée (pas de gain en €).
              </p>
            )}
            {unpriced > 0 && (
              <p className="muted paper-perf-note">
                Prix actuel indisponible pour {unpriced} position(s) (absentes du dernier scan du
                screener).
              </p>
            )}
          </>
        )
      })()}
    </div>
  )
}

/** Tableau « positions » façon broker + répartition du portefeuille. */
export function BrokerPositions({
  overview,
  onSelect,
  onClose,
  closingId,
}: {
  overview: PaperOverview
  onSelect: (p: PaperOverviewPosition) => void
  onClose?: (id: string) => void
  closingId?: string | null
}) {
  const open = overview.positions.filter((p) => p.status === 'OPEN')
  const total = overview.account.equity || 1
  return (
    <div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Actif</th>
              <th>Sens</th>
              <th>Quantité</th>
              <th>Prix d’entrée</th>
              <th>Prix actuel</th>
              <th>Valeur</th>
              <th>Gain / perte</th>
              <th>Stop</th>
              <th>Objectif</th>
              <th>% du portefeuille</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {open.map((p) => {
              const value =
                p.current_price != null && p.qty != null ? p.qty * p.current_price : p.notional
              return (
                <tr key={p.id}>
                  <td>
                    <strong>{assetName(p.symbol)}</strong>
                    <span className="muted"> · {p.timeframe}</span>
                  </td>
                  <td>{directionWords(p.direction).title}</td>
                  <td className="mono">{p.qty != null ? p.qty.toPrecision(4) : '—'}</td>
                  <td className="mono">{price(p.entry_price)}</td>
                  <td className="mono">{price(p.current_price)}</td>
                  <td className="mono">{eur(value)}</td>
                  <td className={`mono ${tone(p.unrealized_pnl)}`}>
                    {signedEur(p.unrealized_pnl)}
                    {p.unrealized_pct != null && <small> ({pct(p.unrealized_pct, 2)})</small>}
                  </td>
                  <td className="mono down">{price(p.stop_price)}</td>
                  <td className="mono up">{price(p.take_profit_price)}</td>
                  <td className="mono muted">
                    {value != null ? `${((value / total) * 100).toFixed(1)} %` : '—'}
                  </td>
                  <td>
                    <button type="button" className="ghost" onClick={() => onSelect(p)}>
                      Fiche
                    </button>
                    {onClose && (
                      <button
                        type="button"
                        className="ghost"
                        disabled={closingId === p.id}
                        onClick={() => onClose(p.id)}
                      >
                        Fermer
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
            {open.length === 0 && (
              <tr>
                <td colSpan={11} className="muted center">
                  Aucune position ouverte — {eur(overview.account.cash)} disponibles.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
