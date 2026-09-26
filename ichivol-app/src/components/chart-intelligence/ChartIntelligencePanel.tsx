/**
 * ChartIntelligencePanel — assemblage pour fiches Décisions / Position
 * (symbole sélectionné). Le graphique live Marché reste PriceChart.
 *
 * variant brief = densifié pour dialogues ; full = page / route preview.
 * Briefing V0 : période + pack calques + caméra (directeur heuristique).
 */

import { useEffect, useMemo, useState } from 'react'
import {
  cameraForPeriod,
  defaultBriefing,
  matchLayerPack,
  packById,
  type BriefingPeriodId,
  type LayerPackId,
} from '../../lib/chartIntelligenceBriefing'
import { useChartIntelligence, type ChartIntelligenceSource } from '../../lib/useChartIntelligence'
import { AIAnalysisPanel } from './AIAnalysisPanel'
import { BriefingControls } from './BriefingControls'
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

type Variant = 'full' | 'brief'
type Context = 'prep' | 'position' | 'explore'

interface Props {
  symbol: string
  timeframe: string
  source?: ChartIntelligenceSource
  chartHeight?: number
  /** brief = fiche dialog (Décisions / Position) ; full = route preview */
  variant?: Variant
  /** Libellé d’eyebrow selon le contexte d’usage */
  context?: Context
  /** Unix s ou ISO — ancre caméra « Depuis entrée » (fiche Position). */
  entryTime?: number | string | null
}

function toUnixSeconds(raw: number | string | null | undefined): number | null {
  if (raw == null) return null
  if (typeof raw === 'number' && Number.isFinite(raw)) {
    return raw > 1e12 ? Math.floor(raw / 1000) : raw
  }
  const ms = Date.parse(String(raw))
  return Number.isFinite(ms) ? Math.floor(ms / 1000) : null
}

const CONTEXT_EYEBROW: Record<Context, string> = {
  prep: 'BRIEFING TRADE · CHART INTELLIGENCE',
  position: 'POSITION · CHART INTELLIGENCE',
  explore: 'CHART INTELLIGENCE',
}

export function ChartIntelligencePanel({
  symbol,
  timeframe,
  source = 'api',
  chartHeight,
  variant = 'full',
  context = 'explore',
  entryTime = null,
}: Props) {
  const entryUnix = toUnixSeconds(entryTime)
  const defaults = defaultBriefing(context, { entryTime: entryUnix })
  const [period, setPeriod] = useState<BriefingPeriodId>(defaults.period)
  const [camToken, setCamToken] = useState(0)
  const ci = useChartIntelligence({ symbol, timeframe, source })
  const res = ci.response
  const height = chartHeight ?? (variant === 'brief' ? 300 : 540)
  const eyebrow = CONTEXT_EYEBROW[context] + (res?.mock ? ' · MOCK' : '')

  // Directeur V0 : appliquer le pack par défaut au montage / changement de contexte.
  useEffect(() => {
    const d = defaultBriefing(context, { entryTime: entryUnix })
    setPeriod(d.period)
    setCamToken((t) => t + 1)
    ci.setLayers(packById(d.pack).layers)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [context, symbol, timeframe, entryUnix])

  const activePack: LayerPackId | null = useMemo(() => matchLayerPack(ci.layers), [ci.layers])

  const camera = useMemo(
    () =>
      cameraForPeriod(period, camToken, {
        entryTime: entryUnix,
        barSeconds: res?.replay?.bar_seconds ?? 3600,
      }),
    [period, camToken, entryUnix, res?.replay?.bar_seconds],
  )
  const onPeriod = (id: BriefingPeriodId) => {
    setPeriod(id)
    setCamToken((t) => t + 1)
  }

  const onPack = (id: LayerPackId) => {
    ci.setLayers(packById(id).layers)
  }

  return (
    <div className={`ci-root${variant === 'brief' ? ' ci-root--brief' : ''}`}>
      <section className="ci-card ci-chart-card" aria-label="Chart Intelligence">
        <header className="ci-card-head">
          <div>
            <div className="ci-eyebrow">{eyebrow}</div>
            <h2>
              {res?.symbol ?? symbol}
              <span className="ci-sub"> · {(res?.timeframe ?? timeframe).toUpperCase()}</span>
            </h2>
          </div>
          <ReplayControls replay={ci.replay} />
        </header>

        <BriefingControls period={period} pack={activePack} onPeriod={onPeriod} onPack={onPack} />

        {ci.error && (
          <div className="ci-notice" role="alert">
            {ci.error}
          </div>
        )}

        {ci.loading && !res && (
          <div className="ci-notice" role="status">
            Chargement Chart Intelligence…
          </div>
        )}

        {res && (
          <IntelligenceChart
            candles={res.candles}
            ichimoku={res.ichimoku}
            projection={res.projection}
            showIchimoku={ci.layers.ichimoku}
            resetKey={`${res.symbol}:${res.timeframe}`}
            camera={camera}
            onBackgroundClick={() => ci.select(null)}
            height={height}
          >
            <DrawingLayer
              objects={ci.visibleObjects}
              selectedKey={ci.selectedKey}
              onSelect={ci.select}
              asOf={res.as_of}
              freshKeys={ci.freshKeys}
              dimStale={!ci.replay.isLive}
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
          Briefing = période + pack + caméra. Calques moteur (ChartObject) uniquement —
          aucun niveau inventé côté front.
        </p>
      </section>

      <aside className="ci-side">
        <section className="ci-card" aria-label="Palette de signaux">
          <header className="ci-card-head">
            <div className="ci-eyebrow">PALETTE SIGNAUX</div>
          </header>
          <LayerControls prefs={ci.layers} onChange={ci.setLayers} counts={ci.counts} />
        </section>
        <DrawingInspector selection={ci.selection} onClose={() => ci.select(null)} />
        <AIAnalysisPanel analysis={res?.analysis ?? null} marketState={res?.market_state} asOf={res?.as_of} />
      </aside>
    </div>
  )
}
