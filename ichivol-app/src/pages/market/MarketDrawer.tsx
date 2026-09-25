import { MarketWatchlist } from '../../components/MarketWatchlist'
import type { useMarketController } from './useMarketController'
import { BacktestEmbed } from './MarketBottomDock'
import { BiasPanel } from '../../components/BiasPanel'
import { displaySymbol } from '../../lib/markets'

type Ctrl = ReturnType<typeof useMarketController>

export function MarketDrawer({ c }: { c: Ctrl }) {
  const {
    isMobile, layout, cycleDrawer, setDrawerTab, pinnedOnly, pinnedSymbols, rows,
    instruments, scanLoading, symbol, selectSymbol, onSort, classFilter, onClassFilter,
    runClassScan, interval, engineOn, marketClass, allWired, current, signals, live,
    summaryRvol, engineDetail, enginePipeline, engineLoading, engineError, canMarkTrade,
    markSaving, startMarkTrade, updateLayout,
  } = c
  if (!isMobile) return null

  const watchlistProps = {
    rows: pinnedOnly && pinnedSymbols
      ? rows.filter((r) => pinnedSymbols.has(r.symbol))
      : rows,
    instruments,
    loading: scanLoading || (pinnedOnly && pinnedSymbols == null),
    selected: symbol,
    onSelect: selectSymbol,
    sortKey: layout.sortKey,
    sortDir: layout.sortDir,
    onSort,
    classFilter,
    onClassFilter,
    onRescan: () => void runClassScan(interval, instruments),
    scanLoading,
    showEngine: engineOn || marketClass === 'crypto' || allWired.some((i) => i.provider !== 'twelve_data'),
  }

  const prepareHint = canMarkTrade
    ? null
    : 'Disponible sur symboles câblés (timeframes moteur 15m / 1h / 4h / 1d).'

  const biasPanel = (
    <BiasPanel
      symbol={current?.label ?? displaySymbol(symbol)}
      signals={signals}
      bias={live.bias}
      rvol={summaryRvol}
      price={live.price}
      engineDetail={engineDetail}
      enginePipeline={enginePipeline}
      engineLoading={engineLoading}
      engineError={engineError}
      engineAvailable={engineOn}
      onPrepareTrade={() => {
        if (!canMarkTrade || markSaving) return
        startMarkTrade()
        updateLayout({ drawerPos: 'closed' })
      }}
      prepareTradeDisabled={!canMarkTrade || markSaving}
      prepareTradeHint={prepareHint}
    />
  )

  return (
    <div className={`mkt-drawer is-${layout.drawerPos}`} data-pos={layout.drawerPos}>
      <button
        type="button"
        className="mkt-drawer-handle"
        aria-label="Hauteur du tiroir"
        onClick={() => cycleDrawer()}
      />
      <nav className="mkt-drawer-tabs" aria-label="Tiroir">
        {(
          [
            ['list', 'Liste'],
            ['analysis', 'Analyse'],
            ['backtest', 'Backtest'],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={
              layout.drawerPos !== 'closed' && layout.drawerTab === id ? 'is-active' : undefined
            }
            style={{ minHeight: 44 }}
            onClick={() => setDrawerTab(id)}
          >
            {label}
          </button>
        ))}
      </nav>
      {layout.drawerPos !== 'closed' && (
        <div className="mkt-drawer-body">
          {layout.drawerTab === 'list' ? (
            <MarketWatchlist {...watchlistProps} hideScore />
          ) : null}
          {layout.drawerTab === 'analysis' ? (
            <div className="mkt-analysis-mobile">{biasPanel}</div>
          ) : null}
          {layout.drawerTab === 'backtest' ? <BacktestEmbed c={c} /> : null}
        </div>
      )}
    </div>
  )
}
