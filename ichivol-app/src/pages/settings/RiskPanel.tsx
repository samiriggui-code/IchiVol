import type { useSettingsController } from './useSettingsController'

type Ctrl = ReturnType<typeof useSettingsController>

export function RiskPanel({ c }: { c: Ctrl }) {
  const {
    risk,
    riskError,
  } = c

  return (
            <section className="panel settings-section">
              <header className="panel-head">
                <h2>Limites de risque</h2>
                <span className="panel-meta">Risk Kernel · lecture seule</span>
              </header>
              <div className="settings-body">
                <p className="muted settings-feed-note">
                  Affichage des plafonds issus de <code>getPaperOverview().risk</code>. Modification
                  prévue dans une tranche engine.
                </p>
                {riskError && (
                  <p className="muted" role="status">
                    {riskError}
                  </p>
                )}
                {!riskError && !risk && <p className="muted">Chargement…</p>}
                {risk && (
                  <dl className="settings-risk-grid">
                    <div>
                      <dt>Capital (equity)</dt>
                      <dd className="mono">
                        {risk.capital.toLocaleString('fr-FR', { maximumFractionDigits: 2 })}
                      </dd>
                    </div>
                    <div>
                      <dt>Cash</dt>
                      <dd className="mono">
                        {risk.cash.toLocaleString('fr-FR', { maximumFractionDigits: 2 })}
                      </dd>
                    </div>
                    <div>
                      <dt>Exposé</dt>
                      <dd className="mono">
                        {risk.exposed.toLocaleString('fr-FR', { maximumFractionDigits: 2 })}
                      </dd>
                    </div>
                    <div>
                      <dt>Risque ouvert</dt>
                      <dd className="mono">
                        {risk.open_risk_amount.toLocaleString('fr-FR', { maximumFractionDigits: 2 })}
                        {risk.open_risk_pct != null
                          ? ` · ${(risk.open_risk_pct * 100).toFixed(2)} %`
                          : ''}
                        {risk.max_open_risk_pct != null
                          ? ` / lim. ${(risk.max_open_risk_pct * 100).toFixed(2)} %`
                          : ''}
                      </dd>
                    </div>
                    <div>
                      <dt>Positions ouvertes</dt>
                      <dd className="mono">
                        {risk.open_positions} / {risk.max_open_positions}
                      </dd>
                    </div>
                    <div>
                      <dt>Kernel</dt>
                      <dd className="mono">{risk.kernel}</dd>
                    </div>
                  </dl>
                )}
              </div>
            </section>
  )
}
