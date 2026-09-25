import { CLASS_LABELS } from '../../lib/universe'
import type { useSettingsController } from './useSettingsController'

type Ctrl = ReturnType<typeof useSettingsController>

export function MarketPanel({ c }: { c: Ctrl }) {
  const {
    apiMissing,
    ichi,
    saving,
    setIchi,
    setTheme,
    setVol,
    theme,
    universe,
    universeError,
    vol,
  } = c

  return (
            <>
            <section className="panel settings-section">
              <header className="panel-head">
                <h2>Univers moteur</h2>
                <span className="panel-meta">Lecture seule</span>
              </header>
              <div className="settings-body">
                {universeError && (
                  <p className="muted" role="status">
                    {universeError}
                  </p>
                )}
                {!universeError && !universe && <p className="muted">Chargement de l’univers…</p>}
                {universe && (
                  <>
                    <p className="muted settings-feed-note">
                      {universe.instruments.length} instruments · classes :{' '}
                      {universe.classes.map((c) => CLASS_LABELS[c] ?? c).join(' · ')}
                    </p>
                    <div className="table-wrap settings-llm-table-wrap">
                      <table className="settings-llm-table">
                        <thead>
                          <tr>
                            <th>Classe</th>
                            <th>Actifs</th>
                            <th>Câblés</th>
                          </tr>
                        </thead>
                        <tbody>
                          {universe.classes.map((cls) => {
                            const rows = universe.instruments.filter((i) => i.asset_class === cls)
                            const wired = rows.filter((i) => i.wired).length
                            return (
                              <tr key={cls}>
                                <td>{CLASS_LABELS[cls] ?? cls}</td>
                                <td className="mono">{rows.length}</td>
                                <td className="mono">{wired}</td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </div>
            </section>
            <section className="panel settings-section">
              <header className="panel-head">
                <h2>Ichimoku · RVOL · thème</h2>
              </header>
              <div className="settings-body controls">
                <label>
                  Tenkan
                  <input
                    type="number"
                    min={1}
                    value={ichi.tenkan}
                    onChange={(e) => setIchi((v) => ({ ...v, tenkan: Number(e.target.value) }))}
                  />
                </label>
                <label>
                  Kijun
                  <input
                    type="number"
                    min={1}
                    value={ichi.kijun}
                    onChange={(e) => setIchi((v) => ({ ...v, kijun: Number(e.target.value) }))}
                  />
                </label>
                <label>
                  Senkou B
                  <input
                    type="number"
                    min={1}
                    value={ichi.senkouB}
                    onChange={(e) => setIchi((v) => ({ ...v, senkouB: Number(e.target.value) }))}
                  />
                </label>
                <label>
                  Displacement
                  <input
                    type="number"
                    min={1}
                    value={ichi.displacement}
                    onChange={(e) =>
                      setIchi((v) => ({ ...v, displacement: Number(e.target.value) }))
                    }
                  />
                </label>
                <label>
                  RVOL len (chart)
                  <input
                    type="number"
                    min={1}
                    value={vol.rvolLen}
                    onChange={(e) => setVol((v) => ({ ...v, rvolLen: Number(e.target.value) }))}
                  />
                </label>
                <label>
                  Spike × (chart)
                  <input
                    type="number"
                    min={0}
                    step={0.1}
                    value={vol.spikeMult}
                    onChange={(e) => setVol((v) => ({ ...v, spikeMult: Number(e.target.value) }))}
                  />
                </label>
                <label>
                  Thème
                  <select value={theme} onChange={(e) => setTheme(e.target.value)}>
                    <option value="dark">Dark</option>
                    <option value="light">Light</option>
                  </select>
                </label>
              </div>

              <p className="muted settings-engine-note">
                Seuils moteur (envoyés à /decisions, /screener, /backtest). Ordre RVOL : low &lt;
                significant &lt; strong &lt; anomaly. ATR : 0 ≤ dead &lt; extreme ≤ 1.
              </p>
              <div className="settings-grid">
                <label>
                  RVOL low
                  <input
                    type="number"
                    min={0}
                    step={0.05}
                    value={vol.rvolLow}
                    onChange={(e) => setVol((v) => ({ ...v, rvolLow: Number(e.target.value) }))}
                  />
                </label>
                <label>
                  RVOL significant
                  <input
                    type="number"
                    min={0}
                    step={0.05}
                    value={vol.rvolSignificant}
                    onChange={(e) =>
                      setVol((v) => ({
                        ...v,
                        rvolSignificant: Number(e.target.value),
                        rvolConfirm: Number(e.target.value),
                      }))
                    }
                  />
                </label>
                <label>
                  RVOL strong
                  <input
                    type="number"
                    min={0}
                    step={0.05}
                    value={vol.rvolStrong}
                    onChange={(e) => setVol((v) => ({ ...v, rvolStrong: Number(e.target.value) }))}
                  />
                </label>
                <label>
                  RVOL anomaly
                  <input
                    type="number"
                    min={0}
                    step={0.05}
                    value={vol.rvolAnomaly}
                    onChange={(e) => setVol((v) => ({ ...v, rvolAnomaly: Number(e.target.value) }))}
                  />
                </label>
                <label>
                  ATR dead %ile
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.01}
                    value={vol.atrDeadPercentile}
                    onChange={(e) =>
                      setVol((v) => ({ ...v, atrDeadPercentile: Number(e.target.value) }))
                    }
                  />
                </label>
                <label>
                  ATR extreme %ile
                  <input
                    type="number"
                    min={0}
                    max={1}
                    step={0.01}
                    value={vol.atrExtremePercentile}
                    onChange={(e) =>
                      setVol((v) => ({ ...v, atrExtremePercentile: Number(e.target.value) }))
                    }
                  />
                </label>
                <label>
                  ATR stop ×
                  <input
                    type="number"
                    min={0.1}
                    step={0.1}
                    value={vol.atrStopMultiplier}
                    onChange={(e) =>
                      setVol((v) => ({ ...v, atrStopMultiplier: Number(e.target.value) }))
                    }
                  />
                </label>
              </div>
              <div className="settings-body">
                <button type="submit" className="ghost settings-save" disabled={saving || apiMissing}>
                  {saving ? 'Enregistrement…' : 'Enregistrer'}
                </button>
              </div>
            </section>
            </>
  )
}
