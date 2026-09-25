import { MarkTradeSheet } from '../../components/MarkTradeSheet'
import { MarketLayersMenu } from '../../components/MarketLayersMenu'
import { MarketSymbolSearch } from '../../components/MarketSymbolSearch'
import { displaySymbol } from '../../lib/markets'
import type { useMarketController } from './useMarketController'

type Ctrl = ReturnType<typeof useMarketController>

export function MarketSheets({ c }: { c: Ctrl }) {
  const {
    isMobile, searchOpen, setSearchOpen, instruments, rows, symbol, searchQuery,
    setSearchQuery, classFilter, onClassFilter, selectSymbol, layersOpen, setLayersOpen,
    layerPrefs, setLayerPrefsAndSave, layerCounts, markOpen, current, markStep, markSaving,
    markError, markPlaced, cancelMarkTrade, validateMarkTrade,
  } = c

  return (
    <>
      {isMobile && searchOpen ? (
        <MarketSymbolSearch
          open
          onClose={() => setSearchOpen(false)}
          instruments={instruments}
          rows={rows}
          selected={symbol}
          search={searchQuery}
          onSearch={setSearchQuery}
          classFilter={classFilter}
          onClassFilter={onClassFilter}
          onSelect={selectSymbol}
          variant="sheet"
        />
      ) : null}

      {isMobile && layersOpen ? (
        <MarketLayersMenu
          open
          onClose={() => setLayersOpen(false)}
          prefs={layerPrefs}
          onChange={setLayerPrefsAndSave}
          counts={layerCounts}
          variant="sheet"
        />
      ) : null}

      {markOpen ? (
        <MarkTradeSheet
          symbolLabel={current?.label ?? displaySymbol(symbol)}
          step={markStep}
          saving={markSaving}
          error={markError}
          placed={markPlaced}
          onCancel={cancelMarkTrade}
          onValidate={() => void validateMarkTrade()}
        />
      ) : null}
    </>
  )
}
