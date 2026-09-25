import type { PaperCosts } from '../lib/paper'
import { eur, pct, signedEur } from '../lib/tradeStory'

function tone(v: number): string {
  return v > 0 ? 'up' : v < 0 ? 'down' : ''
}

/**
 * Du résultat brut au bénéfice net : ce que les trades ont rapporté, ce que le courtier
 * a prélevé (commissions), ce que l'écart acheteur/vendeur et le glissement ont coûté,
 * et ce qu'il vous reste. Tout vient du journal des ordres — aucun chiffre estimé.
 */
export function CostsPanel({ costs }: { costs: PaperCosts }) {
  const financing = costs.financing ?? 0
  const scale = Math.max(
    Math.abs(costs.gross_result),
    costs.commissions,
    costs.spread_slippage,
    financing,
    Math.abs(costs.net_result),
    1,
  )
  const bar = (v: number) => `${Math.min(100, (Math.abs(v) / scale) * 100).toFixed(1)}%`

  const rows: { label: string; hint: string; value: number; cost?: boolean }[] = [
    { label: 'Résultat brut', hint: 'ce que les trades auraient rapporté sans aucun frais', value: costs.gross_result },
    { label: 'Commissions courtier', hint: 'prélevées à chaque achat et vente', value: -costs.commissions, cost: true },
    { label: 'Écart et glissement', hint: 'coût d’exécution, déjà inclus dans les prix', value: -costs.spread_slippage, cost: true },
    {
      label: 'Frais de détention',
      hint:
        costs.financing_bps_per_day_long != null
          ? `overnight CFD ASSUMPTION — long ${Number(costs.financing_bps_per_day_long).toFixed(2)} bps/j` +
            (costs.financing_bps_per_day_short != null
              ? ` · short ${Number(costs.financing_bps_per_day_short).toFixed(2)} bps/j`
              : '') +
            ' · 0 crypto spot'
          : 'financement overnight CFD (ASSUMPTION) — 0 pour crypto spot',
      value: -financing,
      cost: true,
    },
    { label: 'Bénéfice net', hint: 'capital actuel − capital de départ', value: costs.net_result },
  ]

  return (
    <div className="costs-panel">
      <div className="costs-rows">
        {rows.map((r, i) => (
          <div key={r.label} className={`costs-row${i === rows.length - 1 ? ' costs-row-net' : ''}`}>
            <div className="costs-row-label">
              <strong>{r.label}</strong>
              <span className="muted">{r.hint}</span>
            </div>
            <div className="costs-row-bar" aria-hidden>
              <span
                className={`costs-bar ${r.cost ? 'cost' : tone(r.value)}`}
                style={{ width: bar(r.value) }}
              />
            </div>
            <div className={`costs-row-value mono ${r.cost ? 'down' : tone(r.value)}`}>
              {signedEur(r.value)}
            </div>
          </div>
        ))}
      </div>

      <dl className="costs-stats">
        <div>
          <dt>Frais totaux</dt>
          <dd className="mono">{eur(costs.total_costs)}</dd>
        </div>
        <div>
          <dt>Rendement net</dt>
          <dd className={`mono ${tone(costs.net_result)}`}>{pct(costs.net_return_pct, 2)}</dd>
        </div>
        <div>
          <dt>Ordres passés</dt>
          <dd className="mono">{costs.orders}</dd>
        </div>
        <div>
          <dt>Volume échangé</dt>
          <dd className="mono">{eur(costs.notional_traded, 0)}</dd>
        </div>
        <div>
          <dt>Investi maintenant</dt>
          <dd className="mono">
            {eur(costs.invested_now, 0)} · {costs.open_positions} ligne{costs.open_positions > 1 ? 's' : ''}
          </dd>
        </div>
        <div>
          <dt>Trades clos</dt>
          <dd className="mono">
            {costs.wins} gagnant{costs.wins > 1 ? 's' : ''} ({signedEur(costs.sum_wins)}) · {costs.losses} perdant
            {costs.losses > 1 ? 's' : ''} ({signedEur(costs.sum_losses)})
          </dd>
        </div>
      </dl>

      {Object.keys(costs.by_market).length > 0 && (
        <div className="table-wrap">
          <table className="data-table costs-market-table">
            <thead>
              <tr>
                <th>Marché</th>
                <th>Ordres</th>
                <th>Volume</th>
                <th>Commissions</th>
                <th>Écart + glissement</th>
                <th>Total frais</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(costs.by_market).map(([k, v]) => (
                <tr key={k}>
                  <td>{k}</td>
                  <td className="mono">{v.orders}</td>
                  <td className="mono">{eur(v.traded, 0)}</td>
                  <td className="mono">{eur(v.commissions)}</td>
                  <td className="mono">{eur(v.friction)}</td>
                  <td className="mono">{eur(v.total_costs)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted costs-note">{costs.note}</p>
    </div>
  )
}
