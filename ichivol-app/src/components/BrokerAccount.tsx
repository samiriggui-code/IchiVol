import type { PaperOverview, PaperOverviewPosition } from '../lib/paper'
import { assetName, directionWords, eur, pct, price, signedEur } from '../lib/tradeStory'

function tone(v: number | null | undefined): string {
  if (v == null || v === 0) return ''
  return v > 0 ? 'up' : 'down'
}

/** Courbe equity avec bulles chiffrées (départ, min, max, actuel). */
export function EquityCurve({
  points,
  initial,
}: {
  points: { t: string; equity: number }[]
  initial: number
}) {
  if (points.length < 2) {
    return (
      <p className="muted broker-curve-empty">
        La courbe apparaîtra après quelques cycles du moteur (achats / ventes virtuels).
      </p>
    )
  }

  const w = 640
  const h = 200
  const padL = 52
  const padR = 16
  const padT = 28
  const padB = 28
  const plotW = w - padL - padR
  const plotH = h - padT - padB

  const values = points.map((p) => p.equity)
  const min = Math.min(...values, initial)
  const max = Math.max(...values, initial)
  const span = max - min || 1
  const x = (i: number) => padL + (i / (points.length - 1)) * plotW
  const y = (v: number) => padT + plotH - ((v - min) / span) * plotH
  const d = points
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(p.equity).toFixed(1)}`)
    .join(' ')
  const last = values[values.length - 1]
  const up = last >= initial
  const area = `${d} L${x(points.length - 1).toFixed(1)},${(padT + plotH).toFixed(1)} L${x(0).toFixed(1)},${(padT + plotH).toFixed(1)} Z`

  const minIdx = values.indexOf(Math.min(...values))
  const maxIdx = values.indexOf(Math.max(...values))
  const bubbles: { i: number; label: string; value: number; kind: 'start' | 'min' | 'max' | 'now' }[] =
    [
      { i: 0, label: 'Départ', value: values[0], kind: 'start' },
      { i: minIdx, label: 'Plus bas', value: values[minIdx], kind: 'min' },
      { i: maxIdx, label: 'Plus haut', value: values[maxIdx], kind: 'max' },
      { i: points.length - 1, label: 'Maintenant', value: last, kind: 'now' },
    ]
  // Dédupliquer si indices identiques (courbe plate)
  const seen = new Set<number>()
  const uniqueBubbles = bubbles.filter((b) => {
    if (seen.has(b.i) && b.kind !== 'now') return false
    seen.add(b.i)
    return true
  })

  const fmtShort = (v: number) =>
    v >= 1000 ? `${(v / 1000).toFixed(v >= 10000 ? 0 : 1)}k` : v.toFixed(0)

  return (
    <div className="broker-curve-wrap">
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="broker-curve broker-curve-rich"
        role="img"
        aria-label="Courbe de la valeur du portefeuille"
      >
        <defs>
          <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
            <stop
              offset="0%"
              stopColor={up ? 'var(--bull)' : 'var(--bear)'}
              stopOpacity="0.22"
            />
            <stop
              offset="100%"
              stopColor={up ? 'var(--bull)' : 'var(--bear)'}
              stopOpacity="0"
            />
          </linearGradient>
        </defs>
        <text x={4} y={padT + 4} className="broker-curve-axis">
          {fmtShort(max)} €
        </text>
        <text x={4} y={padT + plotH} className="broker-curve-axis">
          {fmtShort(min)} €
        </text>
        <line
          x1={padL}
          x2={w - padR}
          y1={y(initial)}
          y2={y(initial)}
          className="broker-curve-base"
        />
        <text x={w - padR} y={y(initial) - 6} textAnchor="end" className="broker-curve-axis">
          départ {fmtShort(initial)} €
        </text>
        <path d={area} fill="url(#equityFill)" />
        <path
          d={d}
          className={up ? 'broker-curve-line is-up' : 'broker-curve-line is-down'}
          fill="none"
        />
        {uniqueBubbles.map((b) => {
          const cx = x(b.i)
          const cy = y(b.value)
          const above = b.kind === 'min' ? false : cy > padT + 36
          const ty = above ? cy - 14 : cy + 22
          return (
            <g key={`${b.kind}-${b.i}`} className={`broker-curve-bubble is-${b.kind}`}>
              <circle cx={cx} cy={cy} r={4.5} />
              <rect
                x={cx - 36}
                y={ty - 12}
                width={72}
                height={22}
                rx={11}
                className="broker-curve-bubble-bg"
              />
              <text x={cx} y={ty + 3} textAnchor="middle" className="broker-curve-bubble-text">
                {fmtShort(b.value)} €
              </text>
            </g>
          )
        })}
      </svg>
      <div className="broker-curve-legend">
        <span>
          Départ <strong>{eur(initial, 0)}</strong>
        </span>
        <span className={tone(last - initial)}>
          Actuel <strong>{eur(last)}</strong>
        </span>
        <span className="down">
          Plus bas <strong>{eur(Math.min(...values))}</strong>
        </span>
        <span className="up">
          Plus haut <strong>{eur(Math.max(...values))}</strong>
        </span>
      </div>
    </div>
  )
}

/** Cartes investissement — une par position ouverte. */
export function InvestmentCards({
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
  const equity = overview.account.equity || 1

  if (open.length === 0) {
    return (
      <p className="muted">
        Aucun investissement en cours — {eur(overview.account.cash)} libres sur le compte.
      </p>
    )
  }

  return (
    <div className="invest-cards">
      {open.map((p) => {
        const value =
          p.current_price != null && p.qty != null ? p.qty * p.current_price : p.notional
        const share = value != null ? (value / equity) * 100 : null
        const dir = directionWords(p.direction)
        return (
          <article key={p.id} className="invest-card">
            <header className="invest-card-head">
              <div>
                <strong className="invest-card-asset">{assetName(p.symbol)}</strong>
                <span className="muted"> · {p.timeframe}</span>
              </div>
              <span className={`invest-card-dir is-${p.direction.toLowerCase()}`}>{dir.title}</span>
            </header>
            <p className="invest-card-invested">
              <span className="context-label">Somme investie</span>
              <strong>{eur(p.notional)}</strong>
            </p>
            <dl className="invest-card-grid">
              <div>
                <dt>Valeur actuelle</dt>
                <dd>{eur(value)}</dd>
              </div>
              <div>
                <dt>Gain / perte</dt>
                <dd className={tone(p.unrealized_pnl)}>
                  {signedEur(p.unrealized_pnl)}
                  {p.unrealized_pct != null && <small> · {pct(p.unrealized_pct, 2)}</small>}
                </dd>
              </div>
              <div>
                <dt>Part du compte</dt>
                <dd>{share != null ? `${share.toFixed(1)} %` : '—'}</dd>
              </div>
              <div>
                <dt>Entrée → actuel</dt>
                <dd className="mono">
                  {price(p.entry_price)} → {price(p.current_price)}
                </dd>
              </div>
              <div>
                <dt>Stop</dt>
                <dd className="mono down">{price(p.stop_price)}</dd>
              </div>
              <div>
                <dt>Objectif</dt>
                <dd className="mono up">{price(p.take_profit_price)}</dd>
              </div>
            </dl>
            <footer className="invest-card-actions">
              <button type="button" className="ghost" onClick={() => onSelect(p)}>
                Voir la fiche
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
            </footer>
          </article>
        )
      })}
    </div>
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
          <strong className={`context-value ${tone(a.unrealized_pnl)}`}>
            {signedEur(a.unrealized_pnl)}
          </strong>
        </div>
        <div className="context-card">
          <span className="context-label">Gain / perte encaissé</span>
          <strong className={`context-value ${tone(a.realized_pnl)}`}>
            {signedEur(a.realized_pnl)}
          </strong>
        </div>
        <div className="context-card">
          <span className="context-label">Variation 24 h</span>
          <strong className={`context-value ${tone(a.day_change)}`}>
            {signedEur(a.day_change)}
          </strong>
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

/** Tableau « positions » façon broker (vue technique / détail). */
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
              <th>Somme investie</th>
              <th>Quantité</th>
              <th>Prix d’entrée</th>
              <th>Prix actuel</th>
              <th>Valeur actuelle</th>
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
                  <td className="mono">
                    <strong>{eur(p.notional)}</strong>
                  </td>
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
                <td colSpan={12} className="muted center">
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
