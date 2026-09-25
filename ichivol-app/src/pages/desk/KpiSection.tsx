import { fmtEur, fmtPct } from './deskFormat'
import type { PaperOverview } from '../../lib/paper'

export function KpiSection({
  loading,
  acct,
  risk,
  dayTone,
  dayPct,
  ovError,
}: {
  loading: boolean
  acct: PaperOverview['account'] | undefined
  risk: PaperOverview['risk'] | undefined
  dayTone: 'bull' | 'bear' | 'flat'
  dayPct: number | null
  ovError: string | null
}) {
  return (
    <>
      <section className="iv-metrics desk-kpis iv-animate-in" aria-label="Indicateurs clés">
        <div className={`iv-metric${acct ? '' : ''}`}>
          <div className="iv-metric-label">Capital total</div>
          <div className="iv-metric-value mono">
            {loading && !acct ? '—' : acct ? fmtEur(acct.equity, 0) : '—'}
          </div>
          <small>Portefeuille paper · EUR</small>
        </div>
        <div className="iv-metric">
          <div className="iv-metric-label">Disponible</div>
          <div className="iv-metric-value mono">{acct ? fmtEur(acct.cash, 0) : '—'}</div>
          <small>
            {acct && acct.equity > 0
              ? `${fmtPct(acct.cash / acct.equity, 1, false)} du capital`
              : 'Cash libre'}
          </small>
        </div>
        <div
          className={`iv-metric${dayTone === 'bull' ? ' is-bull' : dayTone === 'bear' ? ' is-bear' : ''}`}
        >
          <div className="iv-metric-label">P&amp;L du jour</div>
          <div className="iv-metric-value mono">
            {acct?.day_change != null ? fmtEur(acct.day_change, 0) : '—'}
          </div>
          <small>{dayPct != null ? fmtPct(dayPct) : 'Variation journalière'}</small>
        </div>
        <div className="iv-metric">
          <div className="iv-metric-label">Risque ouvert</div>
          <div className="iv-metric-value mono">
            {risk?.open_risk_pct != null
              ? fmtPct(risk.open_risk_pct, 1, false)
              : risk
                ? fmtEur(risk.open_risk_amount, 0)
                : '—'}
          </div>
          <small>
            {risk?.max_open_risk_pct != null
              ? `Limite ${fmtPct(risk.max_open_risk_pct, 0, false)}`
              : 'Risque ouvert'}
          </small>
        </div>
      </section>
      {ovError && (
        <div className="banner error" role="alert">
          Compte paper : {ovError}
        </div>
      )}
    </>
  )
}
