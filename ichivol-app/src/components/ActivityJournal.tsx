import type { PaperOrderRow } from '../lib/paper'
import { assetName, eur, exitReasonLabel, price } from '../lib/tradeStory'

function describe(o: PaperOrderRow): string {
  const asset = assetName(o.symbol)
  const qty = o.qty.toPrecision(4)
  if (o.reason === 'open') {
    return `${o.side === 'BUY' ? 'Achat' : 'Vente à découvert'} de ${qty} ${asset} à ${price(o.filled_price)}`
  }
  return `Clôture de ${qty} ${asset} à ${price(o.filled_price)} — ${exitReasonLabel(o.reason)}`
}

/** Journal d'activité façon broker : chaque ordre virtuel exécuté par le moteur. */
export function ActivityJournal({ orders }: { orders: PaperOrderRow[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Action</th>
            <th>Sens</th>
            <th>Montant</th>
            <th>Frais</th>
            <th>Statut</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((o) => (
            <tr key={o.id}>
              <td className="mono muted">
                {new Date(o.time).toLocaleString('fr-FR', {
                  day: '2-digit',
                  month: '2-digit',
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </td>
              <td>{describe(o)}</td>
              <td className={o.side === 'BUY' ? 'up' : 'down'}>
                {o.side === 'BUY' ? 'Achat' : 'Vente'}
              </td>
              <td className="mono">{eur(o.notional)}</td>
              <td className="mono muted">{eur(o.fee)}</td>
              <td className="muted">{o.status === 'FILLED' ? 'Exécuté' : o.status}</td>
            </tr>
          ))}
          {orders.length === 0 && (
            <tr>
              <td colSpan={6} className="muted center">
                Aucune activité pour l’instant.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
