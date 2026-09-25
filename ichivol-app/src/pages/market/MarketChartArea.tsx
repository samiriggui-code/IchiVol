import { BiasPanel } from '../../components/BiasPanel'
import { MarketWatchlist } from '../../components/MarketWatchlist'
import { PriceChart } from '../../components/PriceChart'
import { displaySymbol } from '../../lib/markets'
import type { useMarketController } from './useMarketController'
import { fmtPct, fmtPrice, fmtRvol } from './marketHelpers'

type Ctrl = ReturnType<typeof useMarketController>

export function MarketChartArea({ c }: { c: Ctrl }) {
  const {
    pinnedOnly, pinnedSymbols, rows, instruments, scanLoading, symbol, selectSymbol,
    layout, onSort, classFilter, onClassFilter, runClassScan, interval, engineOn,
    marketClass, allWired, current, signals, live, summaryRvol, engineDetail,
    enginePipeline, engineLoading, engineError, canMarkTrade, markSaving, startMarkTrade,
    isMobile, updateLayout, change24hDisplay, pctClass, candles, setSignals, setChartLive,
    mergedChartObjects, markOpen, markStep, onPickPoint, layerPrefs, setLayerPrefsAndSave,
    onRightResizeStart,
  } = c

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
        if (isMobile) updateLayout({ drawerPos: 'closed' })
      }}
      prepareTradeDisabled={!canMarkTrade || markSaving}
      prepareTradeHint={prepareHint}
    />
  )

  const chartSummary = (
    <div className="mkt-chart-summary" aria-label="Résumé PRIX 24H RVOL">
      <span>
        Prix <b className="mono">{fmtPrice(live.price)}</b>
      </span>
      <span>
        24H{' '}
        <b className={`mono ${change24hDisplay == null ? 'is-na' : pctClass}`}>
          {change24hDisplay == null ? 'Non disponible' : fmtPct(change24hDisplay)}
        </b>
      </span>
      <span>
        RVOL <b className={`mono ${summaryRvol == null ? 'is-na' : ''}`}>{fmtRvol(summaryRvol)}</b>
      </span>
    </div>
  )

  const chartEl = (
    <PriceChart
      candles={candles}
      symbol={symbol}
      timeframe={interval}
      onSignals={setSignals}
      onLive={setChartLive}
      chartObjects={mergedChartObjects}
      pickMode={markOpen && markStep !== 'review'}
      onPickPoint={onPickPoint}
      layerPrefs={layerPrefs}
      onLayerPrefsChange={setLayerPrefsAndSave}
      volumeHeight={isMobile ? Math.min(layout.volumeHeight, 120) : layout.volumeHeight}
      onVolumeHeightChange={(h) => updateLayout({ volumeHeight: h })}
    />
  )

  return (
    <div className="mkt-body">
      <section className="mkt-chart-panel chart-panel panel">
        {chartSummary}
        {chartEl}
      </section>

      {!isMobile && layout.rightOpen && (
        <>
          <div
            className="mkt-resize-handle"
            role="separator"
            aria-orientation="vertical"
            aria-label="Redimensionner la colonne"
            onPointerDown={onRightResizeStart}
          />
          <aside id="mkt-right" className="mkt-right side">
            <div className="mkt-right-list">
              <MarketWatchlist {...watchlistProps} />
            </div>
            <div className="mkt-right-bias">{biasPanel}</div>
          </aside>
        </>
      )}
    </div>
  )
}
