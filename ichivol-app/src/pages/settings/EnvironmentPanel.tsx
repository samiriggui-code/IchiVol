import type { useSettingsController } from './useSettingsController'

type Ctrl = ReturnType<typeof useSettingsController>

export function EnvironmentPanel({ c }: { c: Ctrl }) {
  const {
    identity,
  } = c

  return (
            <section className="panel settings-section">
              <header className="panel-head">
                <h2>Environnement</h2>
                <span className="panel-meta">PAPER</span>
              </header>
              <div className="settings-body">
                <dl className="settings-risk-grid">
                  <div>
                    <dt>Mode</dt>
                    <dd>
                      <span className="iv-badge">PAPER</span>
                    </dd>
                  </div>
                  <div>
                    <dt>Exécution réelle</dt>
                    <dd>
                      <span className="iv-badge is-refuse">Désactivée</span>
                    </dd>
                  </div>
                  <div>
                    <dt>Identité</dt>
                    <dd className="mono">{identity?.email ?? '—'}</dd>
                  </div>
                  <div>
                    <dt>User id</dt>
                    <dd className="mono muted">{identity?.id ?? '—'}</dd>
                  </div>
                </dl>
                <p className="muted settings-feed-note">
                  Aucun ordre réel n’est envoyé depuis ce cockpit. Le paper et le Risk Kernel restent
                  la seule voie d’exécution.
                </p>
              </div>
            </section>
  )
}
