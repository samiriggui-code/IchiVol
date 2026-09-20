import type { PaperOverview, PaperOverviewPosition } from '../lib/paper'
import { assetName, directionWords, eur, pct, price, signedEur } from '../lib/tradeStory'

function tone(v: number | null | undefined): string {
  if (v == null || v === 0) return ''
  return v > 0 ? 'up' : 'down'
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

/** Cartes compte uniquement — pas de graphique. */
export function BrokerAccount({ overview }: { overview: PaperOverview }) {
  const a = overview.account
  const totalPct = a.initial_cash ? a.total_pnl / a.initial_cash : null
  const legacy = overview.positions.filter((p) => p.status === 'OPEN' && p.qty == null).length
  const unpriced = a.open_positions - a.priced_positions

  return (
    <div className="broker-account">
      <div className="broker-equity-row">
        <div className="broker-equity">
          <span className="context-label">Valeur du portefeuille</span>
          <strong className="broker-equity-value">{eur(a.equity)}</strong>
          <span className={`broker-equity-delta ${tone(a.total_pnl)}`}>
            {signedEur(a.total_pnl)} ({pct(totalPct, 2)}) depuis le départ ({eur(a.initial_cash, 0)})
          </span>
        </div>
        <div className="paper-perf-grid broker-equity-stats">
          <div className="context-card">
            <span className="context-label">Libre</span>
            <strong className="context-value">{eur(a.cash)}</strong>
          </div>
          <div className="context-card">
            <span className="context-label">Investi</span>
            <strong className="context-value">{eur(a.invested)}</strong>
          </div>
          <div className="context-card">
            <span className="context-label">En cours</span>
            <strong className={`context-value ${tone(a.unrealized_pnl)}`}>
              {signedEur(a.unrealized_pnl)}
            </strong>
          </div>
          <div className="context-card">
            <span className="context-label">Encaissé</span>
            <strong className={`context-value ${tone(a.realized_pnl)}`}>
              {signedEur(a.realized_pnl)}
            </strong>
          </div>
        </div>
      </div>

      {legacy > 0 && (
        <p className="muted paper-perf-note">
          {legacy} position(s) legacy sans montant investi (€).
        </p>
      )}
      {unpriced > 0 && (
        <p className="muted paper-perf-note">
          Prix actuel indisponible pour {unpriced} position(s).
        </p>
      )}
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
