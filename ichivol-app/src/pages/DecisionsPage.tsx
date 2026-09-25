import { Link } from 'react-router-dom'
import { PaperConfirmSheet } from '../components/PaperConfirmSheet'
import { MarketPulseCard } from '../components/desk/DeskRelocatedCards'
import { CLASS_BLURBS, CLASS_LABELS } from '../lib/universe'
import { DecisionSheet } from './opportunites/DecisionSheet'
import { GateStats } from './opportunites/GateStats'
import { MethodBanner } from './opportunites/MethodBanner'
import { PipelineRibbon } from './opportunites/PipelineRibbon'
import { ScreenerPanel } from './opportunites/ScreenerPanel'
import { WhyCard } from './opportunites/WhyCard'
import { useOpportunitesController } from './opportunites/useOpportunitesController'
import './DecisionsPage.css'

export function DecisionsPage() {
  const c = useOpportunitesController()

  return (
    <div className={`decisions-page${c.sheetOpen ? ' is-sheet-open' : ''}`}>
      <div className="decisions-chrome" aria-hidden={c.sheetOpen || undefined}>
        <header className="iv-page-header page-head market-head">
          <div className="market-head-copy">
            <p className="iv-page-eyebrow">Trading · Opportunités</p>
            <h1>Opportunités</h1>
            <p className="iv-page-question">
              Que dit la méthode ?
              {c.pinnedOnly ? ' · Filtre Épinglés actif.' : ''}
            </p>
            <p className="muted">{CLASS_BLURBS[c.marketClass]}</p>
          </div>
          {c.visibleClasses.length > 0 && (
            <div className="market-class-tabs" role="tablist" aria-label="Classe d’actif">
              {c.pinnedOnly && (
                <Link to="/app/opportunites" className="ghost" style={{ alignSelf: 'center' }}>
                  Tout voir
                </Link>
              )}
              {!c.pinnedOnly && (
                <Link
                  to="/app/opportunites?filter=pinned"
                  className="ghost"
                  style={{ alignSelf: 'center' }}
                >
                  Épinglés
                </Link>
              )}
              {c.visibleClasses.map((cl) => (
                <button
                  key={cl}
                  type="button"
                  role="tab"
                  aria-selected={cl === c.marketClass}
                  className={cl === c.marketClass ? 'is-active' : undefined}
                  onClick={() => c.selectClass(cl)}
                >
                  {CLASS_LABELS[cl]}
                </button>
              ))}
            </div>
          )}
        </header>

        <MethodBanner rows={c.classRows} />
        <PipelineRibbon rows={c.classRows} loading={c.loading} />

        {c.whyCandidate ? (
          <WhyCard
            whyCandidate={c.whyCandidate}
            whyDetail={c.whyDetail}
            whyLoading={c.whyLoading}
            whyError={c.whyError}
            onOpenSheet={c.onSelect}
          />
        ) : null}

        <div className="desk-relocated-stack">
          <MarketPulseCard rows={c.classRows} loading={c.loading} />
        </div>

        <GateStats
          loading={c.loading}
          empty={!c.classRows.length}
          buy={c.gateStats.buy}
          sell={c.gateStats.sell}
          watch={c.gateStats.watch}
          total={c.gateStats.total}
          timeframe={c.timeframe}
          onFilterBuySell={() => {
            c.setActionableOnly(true)
            c.setDecisionFilter('all')
          }}
          onClearActionable={() => {
            c.setActionableOnly(false)
            c.setDecisionFilter('all')
          }}
        />

        {c.error && (
          <div className="banner error" role="alert">
            {c.error.includes('engine_unreachable') || c.error.includes('502')
              ? 'Moteur Python injoignable — vérifie que le service tourne (voir ichivol-app/engine/README).'
              : c.error}
          </div>
        )}
      </div>

      <div className="decisions-split">
        <ScreenerPanel
          marketClass={c.marketClass}
          listView={c.listView}
          setListView={c.setListView}
          loading={c.loading}
          visibleRows={c.visibleRows}
          classRows={c.classRows}
          cacheAge={c.cacheAge}
          onRefresh={() => c.load(true)}
          gateFilter={c.gateFilter}
          setGateFilter={c.setGateFilter}
          setActionableOnly={c.setActionableOnly}
          timeframe={c.timeframe}
          setTimeframe={c.setTimeframe}
          symbolQuery={c.symbolQuery}
          setSymbolQuery={c.setSymbolQuery}
          decisionFilter={c.decisionFilter}
          setDecisionFilter={c.setDecisionFilter}
          rvolMin={c.rvolMin}
          setRvolMin={c.setRvolMin}
          actionableOnly={c.actionableOnly}
          sheetOpen={c.sheetOpen}
          selected={c.selected}
          onSelect={c.onSelect}
          instrumentLabel={c.instrumentLabel}
          onOpenPaperFromMatrix={(row) => void c.onOpenPaperFromMatrix(row)}
          paperBusySymbol={c.paperBusySymbol}
          openPaperSymbols={c.openPaperSymbols}
          paperMsg={c.paperMsg}
          error={c.error}
          sortKey={c.sortKey}
          sortDir={c.sortDir}
          toggleSort={c.toggleSort}
          colCount={c.colCount}
        />

        {c.sheetOpen && c.selected && (
          <DecisionSheet
            selected={c.selected}
            instrumentLabel={c.instrumentLabel}
            detailLoading={c.detailLoading}
            byId={c.byId}
            detail={c.detail}
            closeSheet={c.closeSheet}
            detailError={c.detailError}
            activeIntent={c.activeIntent}
            pipelineView={c.pipelineView}
            intentLoading={c.intentLoading}
            paperConfirming={c.paperConfirming}
            onConfirmPaperOrder={() => void c.onConfirmPaperOrder()}
            onRefreshIntent={() => void c.onRefreshIntent()}
            confirming={c.confirming}
            onConfirmDetail={() => void c.onConfirmDetail()}
            explainDecision={c.explainDecision}
            compareGates={c.compareGates}
            confirmMsg={c.confirmMsg}
          />
        )}
      </div>

      {c.paperConfirm && (
        <PaperConfirmSheet
          symbol={c.paperConfirm.symbol}
          timeframe={c.paperConfirm.timeframe}
          symbolLabel={c.instrumentLabel(c.paperConfirm.symbol)}
          intent={c.paperConfirm.intent}
          confirming={c.paperConfirming}
          error={c.paperConfirmError}
          onConfirm={(order) => void c.executePaperConfirm(order)}
          onCancel={() => {
            if (!c.paperConfirming) c.setPaperConfirm(null)
          }}
        />
      )}
    </div>
  )
}
