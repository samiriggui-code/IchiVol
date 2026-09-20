import type { PaperOverview, PaperOverviewPosition } from '../lib/paper'
import { assetName, directionWords, eur, pct, price, signedEur } from '../lib/tradeStory'

function tone(v: number | null | undefined): string {
  if (v == null || v === 0) return ''
  return v > 0 ? 'up' : 'down'
}

/** Cartes investissement compactes — l’essentiel, le détail est dans la fiche. */
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

  if (open.length === 0) {
    return (
      <p className="muted synthese-empty">
        Aucun investissement — {eur(overview.account.cash)} libres.
      </p>
    )
  }

  return (
    <div className="invest-cards">
      {open.map((p) => {
        return (
          <article key={p.id} className="invest-card invest-card--slim">
            <header className="invest-card-head">
              <strong className="invest-card-asset">{assetName(p.symbol)}</strong>
              <span className={`invest-card-dir is-${p.direction.toLowerCase()}`}>
                {p.direction === 'LONG' ? 'Long' : 'Short'}
              </span>
            </header>
            <div className="invest-card-slim-row">
              <div>
                <span className="context-label">Investi</span>
                <strong>{eur(p.notional)}</strong>
              </div>
              <div>
                <span className="context-label">P&amp;L</span>
                <strong className={tone(p.unrealized_pnl)}>
                  {signedEur(p.unrealized_pnl)}
                  {p.unrealized_pct != null && (
                    <small className="muted"> {pct(p.unrealized_pct, 1)}</small>
                  )}
                </strong>
              </div>
            </div>
            <footer className="invest-card-actions">
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
            </footer>
          </article>
        )
      })}
    </div>
  )
}

/** Bandeau compte compact — une ligne, pas de pavé. */
export function BrokerAccount({ overview }: { overview: PaperOverview }) {
  const a = overview.account
  const totalPct = a.initial_cash ? a.total_pnl / a.initial_cash : null

  return (
    <div className="broker-account broker-account--slim">
      <div className="broker-slim">
        <div className="broker-slim-equity">
          <span className="context-label">Portefeuille</span>
          <strong className="broker-equity-value">{eur(a.equity)}</strong>
          <span className={`broker-equity-delta ${tone(a.total_pnl)}`}>
            {signedEur(a.total_pnl)} · {pct(totalPct, 2)}
          </span>
        </div>
        <div className="broker-slim-stats">
          <div>
            <span className="context-label">Libre</span>
            <strong>{eur(a.cash)}</strong>
          </div>
          <div>
            <span className="context-label">Investi</span>
            <strong>{eur(a.invested)}</strong>
          </div>
          <div>
            <span className="context-label">Latent</span>
            <strong className={tone(a.unrealized_pnl)}>{signedEur(a.unrealized_pnl)}</strong>
          </div>
          <div>
            <span className="context-label">Encaissé</span>
            <strong className={tone(a.realized_pnl)}>{signedEur(a.realized_pnl)}</strong>
          </div>
        </div>
      </div>
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
