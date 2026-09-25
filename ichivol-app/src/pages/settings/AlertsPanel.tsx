import {
  detectPushSupport,
  disablePushAlerts,
  enablePushAlerts,
} from '../../lib/pushAlerts'
import type { useSettingsController } from './useSettingsController'

type Ctrl = ReturnType<typeof useSettingsController>

export function AlertsPanel({ c }: { c: Ctrl }) {
  const {
    apiMissing,
    pushBusy,
    pushPrefs,
    pushStatusMsg,
    saving,
    setPushBusy,
    setPushPrefs,
    setPushStatusMsg,
  } = c

  return (
            <section className="panel">
              <header className="panel-head">
                <h2>Alertes push (téléphone)</h2>
                <span className="panel-meta">T0-NOTIF · informatif only</span>
              </header>
              <p className="muted" style={{ padding: '0 1rem' }}>
                Préviens quand une position paper ouverte approche objectif/stop, accélère (RVOL +
                BOS moteur), ou flip Ichimoku. <strong>Jamais d’ordre automatique</strong>.
              </p>
              {(() => {
                const support = detectPushSupport()
                return !support.ok ? (
                  <p
                    className="muted"
                    style={{ padding: '0.5rem 1rem', color: 'var(--danger, #c44)' }}
                    role="status"
                  >
                    {support.message}
                  </p>
                ) : null
              })()}
              {pushStatusMsg && (
                <p className="muted" style={{ padding: '0 1rem' }} role="status">
                  {pushStatusMsg}
                </p>
              )}
              <div className="settings-body controls" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
                <label className="settings-check">
                  <input
                    type="checkbox"
                    checked={pushPrefs.enabled}
                    onChange={(e) =>
                      setPushPrefs((p) => ({ ...p, enabled: e.target.checked }))
                    }
                  />
                  Activer la surveillance des positions
                </label>
                <label className="settings-check">
                  <input
                    type="checkbox"
                    checked={pushPrefs.targetStop}
                    onChange={(e) =>
                      setPushPrefs((p) => ({ ...p, targetStop: e.target.checked }))
                    }
                  />
                  Objectif / stop proches
                </label>
                <label className="settings-check">
                  <input
                    type="checkbox"
                    checked={pushPrefs.accel}
                    onChange={(e) => setPushPrefs((p) => ({ ...p, accel: e.target.checked }))}
                  />
                  Accélération (RVOL + BOS)
                </label>
                <label className="settings-check">
                  <input
                    type="checkbox"
                    checked={pushPrefs.directionFlip}
                    onChange={(e) =>
                      setPushPrefs((p) => ({ ...p, directionFlip: e.target.checked }))
                    }
                  />
                  Changement de direction Ichimoku
                </label>
                <label>
                  Seuil proximité (reste ≤ %)
                  <input
                    type="number"
                    min={5}
                    max={50}
                    step={5}
                    value={Math.round(pushPrefs.nearPct * 100)}
                    onChange={(e) =>
                      setPushPrefs((p) => ({
                        ...p,
                        nearPct: Math.min(1, Math.max(0.05, Number(e.target.value) / 100)),
                      }))
                    }
                  />
                </label>
                <label>
                  Cooldown (min)
                  <input
                    type="number"
                    min={5}
                    max={240}
                    step={5}
                    value={pushPrefs.cooldownMin}
                    onChange={(e) =>
                      setPushPrefs((p) => ({
                        ...p,
                        cooldownMin: Math.max(1, Math.floor(Number(e.target.value) || 30)),
                      }))
                    }
                  />
                </label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                  <button
                    type="button"
                    className="ghost"
                    disabled={pushBusy || apiMissing}
                    onClick={() => {
                      setPushBusy(true)
                      setPushStatusMsg(null)
                      void enablePushAlerts().then((r) => {
                        setPushBusy(false)
                        setPushStatusMsg(
                          r.ok
                            ? 'Abonnement push enregistré sur cet appareil.'
                            : r.message,
                        )
                        if (r.ok) {
                          setPushPrefs((p) => ({ ...p, enabled: true }))
                        }
                      })
                    }}
                  >
                    {pushBusy ? 'Activation…' : 'Activer les alertes (permission)'}
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    disabled={pushBusy}
                    onClick={() => {
                      setPushBusy(true)
                      void disablePushAlerts().then(() => {
                        setPushBusy(false)
                        setPushStatusMsg('Abonnement push retiré sur cet appareil.')
                      })
                    }}
                  >
                    Désabonner cet appareil
                  </button>
                  <button type="submit" className="ghost settings-save" disabled={saving || apiMissing}>
                    {saving ? 'Enregistrement…' : 'Enregistrer les préférences'}
                  </button>
                </div>
              </div>
            </section>
  )
}
