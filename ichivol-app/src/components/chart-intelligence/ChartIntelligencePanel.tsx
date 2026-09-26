/**
 * ChartIntelligencePanel — assemblage prêt à monter dans une page existante
 * (ex. MarketPage, sous le PriceChart, ou dans un onglet). Pas de route, pas de
 * navigation, pas de page : un bloc `.card` au format maquette.
 *
 * Toutes les pièces restent utilisables séparément (voir index.ts).
 */

import { useChartIntelligence, type ChartIntelligenceSource } from '../../lib/useChartIntelligence'
import { AIAnalysisPanel } from './AIAnalysisPanel'
import { ConfluenceLayer } from './ConfluenceZone'
import { DrawingInspector } from './DrawingInspector'
import { DrawingLayer } from './DrawingLayer'
import { FibonacciLayer } from './FibonacciDrawing'
import { FVGLayer } from './FVGDrawing'
import { IntelligenceChart } from './IntelligenceChart'
import { LayerControls } from './LayerControls'
import { LiquidityLayer } from './LiquidityDrawing'
import { MarketStructureLayer } from './MarketStructureLayer'
import { ReplayControls } from './ReplayControls'
import { SupportResistanceLayer } from './SupportResistanceLayer'
import { TrendlineLayer } from './TrendlineDrawing'
import './ChartIntelligence.css'

interface Props {
  symbol: string
  timeframe: string
  source?: ChartIntelligenceSource
  chartHeight?: number
}

export function ChartIntelligencePanel({ symbol, timeframe, source = 'mock', chartHeight = 540 }: Props) {
  const ci = useChartIntelligence({ symbol, timeframe, source })
  const res = ci.response

  return (
    <div className="ci-root">
      <section className="ci-card ci-chart-card" aria-label="Chart Intelligence">
        <header className="ci-card-head">
          <div>
            <div className="ci-eyebrow">CHART INTELLIGENCE{res?.mock ? ' · MOCK PYTHON' : ''}</div>
            <h2>
              {res?.symbol ?? symbol}
              <span className="ci-sub"> · {(res?.timeframe ?? timeframe).toUpperCase()}</span>
            </h2>
          </div>
          <ReplayControls replay={ci.replay} />
        </header>

        {ci.error && (
          <div className="ci-notice" role="alert">
            {ci.error}
          </div>
        )}

        {res && (
          <IntelligenceChart
            candles={res.candles}
            ichimoku={res.ichimoku}
            projection={res.projection}
            showIchimoku={ci.layers.ichimoku}
            resetKey={`${res.symbol}:${res.timeframe}`}
            onBackgroundClick={() => ci.select(null)}
            height={chartHeight}
          >
            <DrawingLayer
              objects={ci.visibleObjects}
              selectedKey={ci.selectedKey}
              onSelect={ci.select}
              asOf={res.as_of}
            >
              <ConfluenceLayer />
              <SupportResistanceLayer />
              <FVGLayer />
              <LiquidityLayer />
              <TrendlineLayer />
              <FibonacciLayer />
              <MarketStructureLayer />
            </DrawingLayer>
          </IntelligenceChart>
        )}
        <p className="ci-foot ci-muted">
          Objets produits par Python (ChartObject). React affiche, sélectionne et masque — aucun calcul de
          marché côté front. {res?.mock ? 'Scores et confidences fictifs (maquette).' : ''}
        </p>
      </section>

      <aside className="ci-side">
        <section className="ci-card" aria-label="Calques">
          <header className="ci-card-head">
            <div className="ci-eyebrow">LAYERS</div>
          </header>
          <LayerControls prefs={ci.layers} onChange={ci.setLayers} counts={ci.counts} />
        </section>
        <DrawingInspector selection={ci.selection} onClose={() => ci.select(null)} />
        <AIAnalysisPanel analysis={res?.analysis ?? null} marketState={res?.market_state} asOf={res?.as_of} />
      </aside>
    </div>
  )
}
