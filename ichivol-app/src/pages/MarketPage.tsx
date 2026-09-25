import { type CSSProperties } from 'react'
import { MarketBottomDock } from './market/MarketBottomDock'
import { MarketChartArea } from './market/MarketChartArea'
import { MarketDrawer } from './market/MarketDrawer'
import { MarketSheets } from './market/MarketSheets'
import { MarketToolbar } from './market/MarketToolbar'
import { useMarketController } from './market/useMarketController'
import './MarketPage.css'

export function MarketPage() {
  const c = useMarketController()
  const {
    isMobile, markOpen, btPanelOpen, layout, error, universeError, pinnedOnly,
  } = c

  return (
    <div
      className={`market-page mkt-page${isMobile ? ' is-mobile' : ' is-desktop'}${
        markOpen ? ' is-mark-trade' : ''
      }${btPanelOpen ? ' is-backtest-overlay' : ''}${
        layout.rightOpen ? '' : ' is-right-collapsed'
      }${layout.bottomOpen ? ' is-bottom-open' : ''}`}
      style={
        {
          '--mkt-right-w': `${layout.rightWidth}px`,
          '--mkt-bottom-h': `${layout.bottomHeight}px`,
          '--mkt-drawer-pos': layout.drawerPos,
        } as CSSProperties
      }
      data-drawer={layout.drawerPos}
    >
      <MarketToolbar c={c} />

      {(error || universeError) && (
        <div className="banner error mkt-error-toast" role="alert">
          {error ?? universeError}
        </div>
      )}
      {pinnedOnly && (
        <div className="banner mkt-pinned-banner" role="status">
          Filtre <strong>Épinglés</strong> (watchlist) —{' '}
          <a href="/app/market">voir tout le marché</a>
        </div>
      )}

      <MarketChartArea c={c} />
      <MarketBottomDock c={c} />
      <MarketDrawer c={c} />
      <MarketSheets c={c} />
    </div>
  )
}
