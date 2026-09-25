import { MarketLayersMenu } from '../../components/MarketLayersMenu'
import { MarketSymbolSearch } from '../../components/MarketSymbolSearch'
import { INTERVALS } from '../../lib/binance'
import { displaySymbol } from '../../lib/markets'
import type { useMarketController } from './useMarketController'

type Ctrl = ReturnType<typeof useMarketController>
import {
  INDICATOR_TOGGLES,
  fmtPct,
  fmtPrice,
} from './marketHelpers'

export function MarketToolbar({ c }: { c: Ctrl }) {
  const {
    isMobile, current, symbol, live, pctClass, change24hDisplay, providerLabel, chartLoading,
    searchOpen, setSearchOpen, layersOpen, setLayersOpen, indicatorsOpen, setIndicatorsOpen,
    infoOpen, setInfoOpen, layerPrefs, activeObjectLayerCount, setLayerPrefsAndSave, layerCounts,
    toggleIndicator, markOpen, canMarkTrade, markSaving, cancelMarkTrade, startMarkTrade,
    updateLayout, layout, instruments, rows, searchQuery, setSearchQuery, classFilter,
    onClassFilter, selectSymbol, indicatorsRef, infoRef, isTwelveData, interval, setInterval,
  } = c

  const tfButtons = (
    <div className="mkt-tf-group" role="group" aria-label="Timeframe">
      {INTERVALS.map((tf) => (
        <button
          key={tf.id}
          type="button"
          className={tf.id === interval ? 'is-active' : undefined}
          onClick={() => setInterval(tf.id)}
        >
          {tf.label}
        </button>
      ))}
    </div>
  )

  const infoButton = (
    <div className="mkt-info-wrap" ref={infoRef}>
      <button
        type="button"
        className="mkt-icon-btn"
        aria-label="Info source"
        aria-expanded={infoOpen}
        onClick={() => setInfoOpen((o: boolean) => !o)}
      >
        i
      </button>
      {infoOpen ? (
        <div className="mkt-info-pop" role="note">
          {isTwelveData
            ? `Données via le moteur IchiVol (${providerLabel}) — pas de compte broker. Plan Twelve Data gratuit ≈ 8 crédits/min : charge un symbole à la fois (liste sans scan parallèle).`
            : `Source : ${providerLabel}. OHLCV via le moteur IchiVol — pas de compte broker.`}
        </div>
      ) : null}
    </div>
  )

  if (!isMobile) {
    return (
      <header className="mkt-topbar" style={{ height: 52 }}>
        <button
          type="button"
          className="mkt-symbol-btn"
          aria-haspopup="dialog"
          aria-expanded={searchOpen}
          onClick={() => setSearchOpen((o: boolean) => !o)}
        >
          <span className="mkt-symbol-label">
            {current?.label ?? displaySymbol(symbol)}
          </span>
          <span className="mkt-caret" aria-hidden>
            ▾
          </span>
        </button>

        <div className="mkt-quote">
          <span className="mkt-price mono">{fmtPrice(live.price)}</span>
          <span className={`mkt-pct mono ${pctClass}`}>{fmtPct(change24hDisplay)}</span>
          <span className="mkt-source muted">{providerLabel}</span>
          {chartLoading ? <span className="muted">…</span> : null}
        </div>

        {tfButtons}

        <div className="mkt-topbar-actions">
          <div className="mkt-menu-anchor">
            <button
              type="button"
              className="ghost mkt-topbar-btn"
              aria-expanded={layersOpen}
              onClick={() => {
                setLayersOpen((o: boolean) => !o)
                setIndicatorsOpen(false)
              }}
            >
              Calques{activeObjectLayerCount ? ` · ${activeObjectLayerCount}` : ''} ▾
            </button>
            {layersOpen ? (
              <MarketLayersMenu
                open
                onClose={() => setLayersOpen(false)}
                prefs={layerPrefs}
                onChange={setLayerPrefsAndSave}
                counts={layerCounts}
                variant="menu"
              />
            ) : null}
          </div>

          <div className="mkt-menu-anchor" ref={indicatorsRef}>
            <button
              type="button"
              className="ghost mkt-topbar-btn"
              aria-expanded={indicatorsOpen}
              onClick={() => {
                setIndicatorsOpen((o: boolean) => !o)
                setLayersOpen(false)
              }}
            >
              Indicateurs ▾
            </button>
            {indicatorsOpen ? (
              <div className="mkt-indicators-menu" role="menu">
                {INDICATOR_TOGGLES.map((t) => (
                  <button
                    key={t.key}
                    type="button"
                    role="menuitemcheckbox"
                    aria-checked={layerPrefs[t.key]}
                    className={layerPrefs[t.key] ? 'is-on' : undefined}
                    onClick={() => toggleIndicator(t.key)}
                  >
                    <span aria-hidden>{layerPrefs[t.key] ? '◉' : '○'}</span>
                    {t.label}
                  </button>
                ))}
              </div>
            ) : null}
          </div>

          <span className="mkt-topbar-ellipsis" aria-hidden>
            …
          </span>

          {infoButton}

          <button
            type="button"
            className={markOpen ? 'is-active mkt-topbar-btn' : 'ghost mkt-topbar-btn'}
            disabled={!canMarkTrade || markSaving}
            title={
              canMarkTrade
                ? 'Poser ENTRY / STOP / TARGET sur le graphique'
                : 'Disponible sur symboles câblés (TF moteur)'
            }
            onClick={() => {
              if (markOpen) cancelMarkTrade()
              else {
                startMarkTrade()
                updateLayout({ bottomOpen: true, bottomTab: 'mark' })
              }
            }}
          >
            {markOpen ? 'Annuler marquage' : 'Marquer un trade'}
          </button>

          <button
            type="button"
            className="side-toggle mkt-icon-btn"
            aria-expanded={layout.rightOpen}
            aria-controls="mkt-right"
            title={layout.rightOpen ? 'Réduire le panneau' : 'Afficher le panneau'}
            onClick={() => updateLayout({ rightOpen: !layout.rightOpen })}
          >
            {layout.rightOpen ? '⟩' : '⟨'}
          </button>
        </div>

        {searchOpen ? (
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
            variant="popover"
          />
        ) : null}
      </header>
    )
  }

  return (
    <>
      <header className="mkt-topbar mkt-topbar--mobile" style={{ minHeight: 52 }}>
        <button
          type="button"
          className="mkt-symbol-btn"
          style={{ minWidth: 44, minHeight: 44 }}
          aria-haspopup="dialog"
          aria-expanded={searchOpen}
          onClick={() => setSearchOpen(true)}
        >
          <span className="mkt-symbol-label">
            {current?.label ?? displaySymbol(symbol)}
          </span>
          <span className="mkt-caret" aria-hidden>
            ▾
          </span>
        </button>
        <div className="mkt-quote">
          <span className="mkt-price mono">{fmtPrice(live.price)}</span>
          <span className={`mkt-pct mono ${pctClass}`}>{fmtPct(change24hDisplay)}</span>
        </div>
        <button
          type="button"
          className="mkt-icon-btn"
          style={{ minWidth: 44, minHeight: 44 }}
          aria-label="Rechercher"
          onClick={() => setSearchOpen(true)}
        >
          ⌕
        </button>
        <button
          type="button"
          className="mkt-icon-btn"
          style={{ minWidth: 44, minHeight: 44 }}
          aria-label="Calques"
          aria-expanded={layersOpen}
          onClick={() => setLayersOpen(true)}
        >
          Calques
        </button>
      </header>
      <div className="mkt-mobile-tf-row">
        {tfButtons}
        {infoButton}
      </div>
    </>
  )
}
