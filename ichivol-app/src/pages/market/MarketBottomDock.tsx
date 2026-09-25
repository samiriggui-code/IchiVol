import { Link } from 'react-router-dom'
import { BacktestOverlaySheet } from '../../components/BacktestOverlaySheet'
import { displaySymbol } from '../../lib/markets'
import type { useMarketController } from './useMarketController'
import { journalGateLabel } from './marketHelpers'

type Ctrl = ReturnType<typeof useMarketController>

function BacktestEmbed({ c }: { c: Ctrl }) {
  const {
    btPanelOpen, current, symbol, btRulesetId, btOutcome, btUiFilter, btCounts, btTrades,
    btRejected, btMetrics, btExitReason, btDirection, btRegimeLabel, btLoading, btError,
    btActive, setBtRulesetId, onBtOutcome, onBtUiFilter, onBtExitReason, onBtDirection,
    onBtRegimeLabel, clearBacktestOverlay, loadBacktestOverlay, isMobile, updateLayout,
  } = c
  if (!btPanelOpen) return null
  return (
    <BacktestOverlaySheet
      symbolLabel={current?.label ?? displaySymbol(symbol)}
      selectedRulesetId={btRulesetId}
      outcome={btOutcome}
      uiFilter={btUiFilter}
      counts={btCounts}
      trades={btTrades}
      rejected={btRejected}
      metrics={btMetrics}
      exitReason={btExitReason}
      direction={btDirection}
      regimeLabel={btRegimeLabel}
      loading={btLoading}
      error={btError}
      active={btActive}
      variant="embed"
      onSelectRuleset={setBtRulesetId}
      onOutcome={onBtOutcome}
      onUiFilter={onBtUiFilter}
      onExitReason={onBtExitReason}
      onDirection={onBtDirection}
      onRegimeLabel={onBtRegimeLabel}
      onShow={() => void loadBacktestOverlay(btOutcome)}
      onClear={clearBacktestOverlay}
      onClose={() => {
        if (isMobile) updateLayout({ drawerPos: 'closed' })
        else updateLayout({ bottomOpen: false })
      }}
    />
  )
}

export function MarketBottomDock({ c }: { c: Ctrl }) {
  const {
    isMobile, layout, markOpen, markStep, canMarkTrade, markSaving, cancelMarkTrade,
    startMarkTrade, current, symbol, journalLoading, journalError, journalForSymbol,
    openBottomTab, btActive,
  } = c
  if (isMobile) return null

  const backtestEmbed = <BacktestEmbed c={c} />

  return (
    <div className="mkt-bottom-dock">
      {layout.bottomOpen && (
        <div className="mkt-bottom-panel" style={{ height: layout.bottomHeight || 250 }}>
          {layout.bottomTab === 'backtest' ? backtestEmbed : null}
          {layout.bottomTab === 'mark' ? (
            <div className="mkt-bottom-embed">
              <p>
                {markOpen
                  ? `Mode marquage — étape : ${markStep}. Clique le graphique pour poser les points.`
                  : 'Pose ENTRY → STOP → TARGET sur le graphique, puis valide.'}
              </p>
              <button
                type="button"
                className={markOpen ? 'is-active' : undefined}
                disabled={!canMarkTrade || markSaving}
                onClick={() => (markOpen ? cancelMarkTrade() : startMarkTrade())}
              >
                {markOpen ? 'Annuler' : 'Démarrer'}
              </button>
            </div>
          ) : null}
          {layout.bottomTab === 'journal' ? (
            <div className="mkt-bottom-embed mkt-journal-dock">
              <div className="mkt-journal-dock-head">
                <h3>Journal · {current?.label ?? displaySymbol(symbol)}</h3>
                <Link className="mkt-journal-dock-link" to="/app/journal">
                  Ouvrir le journal →
                </Link>
              </div>
              {journalLoading ? (
                <p className="mkt-journal-dock-msg">Chargement…</p>
              ) : journalError ? (
                <p className="mkt-journal-dock-msg is-error" role="alert">
                  {journalError}
                </p>
              ) : journalForSymbol.length === 0 ? (
                <p className="mkt-journal-dock-msg">
                  Aucune décision sauvegardée pour ce symbole.
                </p>
              ) : (
                <ul className="mkt-journal-list">
                  {journalForSymbol.slice(0, 12).map((row) => (
                    <li key={row.id}>
                      <span className="mkt-journal-when mono">
                        {new Date(row.createdAt).toLocaleString('fr-FR', {
                          day: '2-digit',
                          month: 'short',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                      <span className="mkt-journal-meta">
                        {row.interval}
                        {row.note ? ` · ${row.note}` : ''}
                      </span>
                      <span className="mkt-journal-gate">{journalGateLabel(row)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : null}
        </div>
      )}
      <nav className="mkt-bottom-bar" style={{ height: 44 }} aria-label="Panneau bas">
        {(
          [
            ['backtest', 'Backtest'],
            ['mark', 'Marquer un trade'],
            ['journal', 'Journal'],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={layout.bottomOpen && layout.bottomTab === id ? 'is-active' : undefined}
            disabled={id === 'backtest' ? !canMarkTrade && !btActive : false}
            onClick={() => openBottomTab(id)}
          >
            {label}
          </button>
        ))}
      </nav>
    </div>
  )
}

export { BacktestEmbed }
