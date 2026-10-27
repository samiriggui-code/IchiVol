/**
 * Marché : station en trois colonnes (watchlist, graphique, lecture des portes)
 * sur les primitives premium iv-. Données = moteur (pas de démo inventée).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { TablePager } from '../components/table/TablePager'
import { usePaged } from '../components/table/usePaged'
import { DecisionPipelinePanel } from '../components/DecisionPipelinePanel'
import { MtfPanel } from '../components/MtfPanel'
import { MarketLayersMenu } from '../components/MarketLayersMenu'
import { PriceChart } from '../components/PriceChart'
import { SignalEvidenceCard } from '../components/SignalEvidenceCard'
import '../components/engineEvidence.css'
import { confirmAgentAction } from '../lib/agent'
import { getChartObjects, type ChartObject } from '../lib/chartObjects'
import { fetchTickers24h } from '../lib/binance'
import {
  getDecisionDetail,
  getScreener,
  type DecisionDetail,
  type ScreenerDecisionRow,
} from '../lib/decisions'
import {
  pipelineFromDecisionDetail,
  type PipelineStageId,
} from '../lib/decisionPipeline'
import { buildDecisionSummary } from '../lib/decisionLabels'
import {
  OBJECT_LAYER_META,
  countObjectsByLayer,
  loadLayerPrefs,
  saveLayerPrefs,
  withIchimoku,
  type LayerPrefs,
} from '../lib/marketPrefs'
import type { Candle, Interval } from '../lib/types'
import {
  CLASS_LABELS,
  getEngineOhlcv,
  getEngineUniverse,
  type EngineAssetClass,
  type EngineInstrument,
} from '../lib/universe'
import {
  fmtPctMaq,
  fmtPriceMaq,
  fmtRvolMaq,
  lectureSynthesisFr,
  maquetteGateBadge,
  type MaquetteBadgeTone,
  nearestSrObjects,
  shortSymbol,
} from './market/marketMaquetteHelpers'
import { openMarketTvWindow } from '../lib/marketTv'
import './MarketPage.css'

const TFS: { id: Interval; label: string }[] = [
  { id: '15m', label: '15M' },
  { id: '1h', label: '1H' },
  { id: '4h', label: '4H' },
  { id: '1d', label: '1D' },
]

const GATE_ORDER: PipelineStageId[] = [
  'direction',
  'participation',
  'structure',
  'location',
  'regime',
]

const GATE_LABELS: Record<PipelineStageId, string> = {
  direction: 'Direction',
  participation: 'Participation',
  structure: 'Structure',
  location: 'Emplacement',
  regime: 'Régime',
}

const GATE_GLYPH: Record<MaquetteBadgeTone, string> = {
  green: '✓',
  amber: '~',
  red: '✕',
  gray: '·',
  '': '·',
}

type EvidenceTab = 'pipeline' | 'signal' | 'mtf'

const EVIDENCE_TABS: { id: EvidenceTab; label: string }[] = [
  { id: 'pipeline', label: 'Argumentaire et portes' },
  { id: 'signal', label: 'Preuves du signal' },
  { id: 'mtf', label: 'Multi-horizons' },
]

function classLabel(c: EngineAssetClass | 'all'): string {
  return c === 'all' ? 'Toutes classes' : CLASS_LABELS[c]
}

type WatchRow = {
  id: string
  label: string
  price: number | null
  change24h: number | null
  rvol: number | null
}

export function MarketPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [instruments, setInstruments] = useState<EngineInstrument[]>([])
  const [assetClass, setAssetClass] = useState<EngineAssetClass | 'all'>('all')
  const [screenerRows, setScreenerRows] = useState<ScreenerDecisionRow[]>([])
  const [tickers24h, setTickers24h] = useState<Map<string, { price: number; change24h: number }>>(
    () => new Map(),
  )
  const [symbol, setSymbol] = useState('BTCUSDT')
  const [interval, setInterval] = useState<Interval>('1h')
  const [candles, setCandles] = useState<Candle[]>([])
  const [provider, setProvider] = useState<string | null>(null)
  const [detail, setDetail] = useState<DecisionDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [chartLoading, setChartLoading] = useState(false)
  const [layerPrefs, setLayerPrefs] = useState<LayerPrefs>(() => loadLayerPrefs())
  const [watchMsg, setWatchMsg] = useState<string | null>(null)
  const [watchBusy, setWatchBusy] = useState(false)
  const [engineObjects, setEngineObjects] = useState<ChartObject[]>([])
  const [layersOpen, setLayersOpen] = useState(false)
  const [layersSheet, setLayersSheet] = useState(false)
  const [evidenceTab, setEvidenceTab] = useState<EvidenceTab>('pipeline')
  const layersAnchorRef = useRef<HTMLDivElement>(null)

  const ichimokuOn =
    layerPrefs.tenkan && layerPrefs.kijun && layerPrefs.spanA && layerPrefs.spanB
  const levelsOn = layerPrefs.structure

  const setLayers = useCallback((next: LayerPrefs) => {
    setLayerPrefs(next)
    saveLayerPrefs(next)
  }, [])

  const layerCounts = useMemo(() => countObjectsByLayer(engineObjects), [engineObjects])
  const activeObjectLayerCount = useMemo(
    () => OBJECT_LAYER_META.filter((m) => layerPrefs[m.key]).length,
    [layerPrefs],
  )

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 800px)')
    const sync = () => setLayersSheet(mq.matches)
    sync()
    mq.addEventListener('change', sync)
    return () => mq.removeEventListener('change', sync)
  }, [])

  useEffect(() => {
    if (!layersOpen || layersSheet) return
    const onDoc = (e: MouseEvent) => {
      const el = layersAnchorRef.current
      if (el && e.target instanceof Node && !el.contains(e.target)) {
        setLayersOpen(false)
      }
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setLayersOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [layersOpen, layersSheet])

  useEffect(() => {
    let cancelled = false
    getEngineUniverse()
      .then((u) => {
        if (cancelled) return
        setInstruments(u.instruments.filter((i) => i.wired && i.enabled))
        const fromUrl = searchParams.get('symbol')
        const iq = searchParams.get('interval')
        if (iq === '15m' || iq === '1h' || iq === '4h' || iq === '1d') setInterval(iq)
        if (fromUrl && u.instruments.some((i) => i.id === fromUrl)) {
          setSymbol(fromUrl)
          return
        }
        const btc = u.instruments.find((i) => i.id === 'BTCUSDT' && i.wired)
        const first = u.instruments.find((i) => i.wired && i.asset_class === 'crypto')
        if (btc) setSymbol(btc.id)
        else if (first) setSymbol(first.id)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Univers indisponible')
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    let cancelled = false
    getScreener(interval, false)
      .then((res) => {
        if (!cancelled) setScreenerRows(res.rows)
      })
      .catch(() => {
        if (!cancelled) setScreenerRows([])
      })
    return () => {
      cancelled = true
    }
  }, [interval])

  // 24h Binance pour chaque symbole watchlist (crypto USDT)
  useEffect(() => {
    let cancelled = false
    fetchTickers24h()
      .then((rows) => {
        if (cancelled) return
        const m = new Map<string, { price: number; change24h: number }>()
        for (const t of rows) {
          m.set(t.symbol, { price: t.lastPrice, change24h: t.priceChangePercent })
        }
        setTickers24h(m)
      })
      .catch(() => {
        if (!cancelled) setTickers24h(new Map())
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!symbol) return
    let cancelled = false
    setChartLoading(true)
    setError(null)
    getEngineOhlcv(symbol, interval, 300)
      .then((res) => {
        if (cancelled) return
        setCandles(res.candles)
        setProvider(res.provider)
      })
      .catch((e: unknown) => {
        if (cancelled) return
        setCandles([])
        setProvider(null)
        setError(e instanceof Error ? e.message : 'OHLCV indisponible')
      })
      .finally(() => {
        if (!cancelled) setChartLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [symbol, interval])

  // Objets chart moteur (structure / fib / FVG / breaks) + USER / CLAUDE.
  useEffect(() => {
    if (!symbol) return
    let cancelled = false
    setEngineObjects([])
    getChartObjects(symbol, interval, 300, ['engine', 'user', 'claude'])
      .then((objs) => {
        if (!cancelled) setEngineObjects(objs)
      })
      .catch(() => {
        if (!cancelled) setEngineObjects([])
      })
    return () => {
      cancelled = true
    }
  }, [symbol, interval])

  // Toutes les couches + libellés RÉSISTANCE / SUPPORT les plus proches (structure).
  const chartObjectsForView = useMemo(() => {
    const nearest = layerPrefs.structure
      ? nearestSrObjects(
          engineObjects,
          candles.length ? candles[candles.length - 1]!.close : null,
          symbol,
          interval,
        )
      : []
    return [...engineObjects, ...nearest]
  }, [engineObjects, candles, symbol, interval, layerPrefs.structure])

  useEffect(() => {
    if (!symbol) return
    let cancelled = false
    getDecisionDetail(symbol, interval, false, true)
      .then((d) => {
        if (!cancelled) setDetail(d)
      })
      .catch(() => {
        if (!cancelled) setDetail(null)
      })
    return () => {
      cancelled = true
    }
  }, [symbol, interval])

  const current = useMemo(
    () => instruments.find((i) => i.id === symbol) ?? null,
    [instruments, symbol],
  )
  const screenerById = useMemo(() => {
    const m = new Map<string, ScreenerDecisionRow>()
    for (const r of screenerRows) m.set(r.symbol, r)
    return m
  }, [screenerRows])

  const classOptions = useMemo(() => {
    const present = new Set(instruments.map((i) => i.asset_class))
    return (Object.keys(CLASS_LABELS) as EngineAssetClass[]).filter((c) => present.has(c))
  }, [instruments])

  const watchRows: WatchRow[] = useMemo(() => {
    const list =
      instruments.length > 0
        ? instruments
            .filter((i) => assetClass === 'all' || i.asset_class === assetClass)
        : []
    return list.map((inst) => {
      const row = screenerById.get(inst.id)
      const tick = tickers24h.get(inst.id)
      const price =
        tick?.price && tick.price > 0
          ? tick.price
          : row?.price && row.price > 0
            ? row.price
            : null
      return {
        id: inst.id,
        label: shortSymbol(inst.id),
        price,
        change24h: tick != null && Number.isFinite(tick.change24h) ? tick.change24h : null,
        rvol: row?.rvol ?? null,
      }
    })
  }, [instruments, screenerById, tickers24h, assetClass])
  const watchPaged = usePaged(watchRows, 'marche-watchlist')
  // L'actif affiché (lien direct, choix précédent) reste visible : on ouvre la page qui le contient.
  const selectedWatchIndex = watchRows.findIndex((w) => w.id === symbol)
  const { pageSize: watchPageSize, setPage: setWatchPage } = watchPaged
  useEffect(() => {
    if (selectedWatchIndex >= 0) setWatchPage(Math.floor(selectedWatchIndex / watchPageSize) + 1)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- seulement au changement d'actif ou de liste
  }, [symbol, watchRows.length])

  const selectedTick = tickers24h.get(symbol)
  const change24h =
    selectedTick != null && Number.isFinite(selectedTick.change24h)
      ? selectedTick.change24h
      : null
  const lastClose = candles.length ? candles[candles.length - 1]!.close : null
  const priceDisplay =
    (selectedTick?.price && selectedTick.price > 0 ? selectedTick.price : null) ??
    (screenerById.get(symbol)?.price && screenerById.get(symbol)!.price > 0
      ? screenerById.get(symbol)!.price
      : null) ??
    lastClose
  const rvolDisplay = detail?.rvol ?? screenerById.get(symbol)?.rvol ?? null

  const pipeline = useMemo(
    () => (detail ? pipelineFromDecisionDetail(detail) : null),
    [detail],
  )

  const synthesis = useMemo(
    () => lectureSynthesisFr(pipeline, rvolDisplay),
    [pipeline, rvolDisplay],
  )

  const setupName = useMemo(() => {
    if (!pipeline) return '—'
    if (pipeline.direction === 'LONG') return 'Setup haussier'
    if (pipeline.direction === 'SHORT') return 'Setup baissier'
    return 'Setup neutre'
  }, [pipeline])

  const setupState = useMemo(() => {
    const g = pipeline?.gateDecision
    if (g === 'BUY' || g === 'SELL') return { text: 'Déclenché', tone: 'green' as const }
    if (g === 'WATCH') return { text: 'Armé', tone: '' as const }
    if (g === 'NO_TRADE') return { text: 'Veille', tone: 'gray' as const }
    return { text: '—', tone: 'gray' as const }
  }, [pipeline])

  const quote = current?.quote ? ` / ${current.quote}` : ''
  const sourceLabel =
    provider === 'binance'
      ? 'Binance'
      : provider === 'twelve_data'
        ? 'Twelve Data'
        : provider
          ? provider
          : '—'

  const onAddWatchlist = async () => {
    setWatchBusy(true)
    setWatchMsg(null)
    try {
      const res = await confirmAgentAction({
        intent: 'pin_symbol',
        confirm: true,
        symbol,
      })
      setWatchMsg(res.ok ? 'Ajouté à la watchlist.' : (res.error ?? res.message ?? 'Échec'))
    } catch (e: unknown) {
      setWatchMsg(e instanceof Error ? e.message : 'Échec watchlist')
    } finally {
      setWatchBusy(false)
    }
  }

  const toggleLayer = (key: 'structure' | 'fibonacci' | 'fvg' | 'breaks') =>
    setLayers({ ...layerPrefs, [key]: !layerPrefs[key] })

  const setupTagTone =
    pipeline?.direction === 'LONG' ? 'is-buy' : pipeline?.direction === 'SHORT' ? 'is-sell' : 'is-muted'
  const stateTagTone =
    setupState.tone === 'green' ? 'is-mint' : setupState.tone === '' ? 'is-amber' : 'is-muted'
  const rvolOk = rvolDisplay != null && rvolDisplay >= 1.5

  return (
    <div className="market-page mk-page">
      <header className="iv-ph">
        <div>
          <div className="iv-meta">Marché · bougies clôturées · Ichimoku × RVOL</div>
          <h1>Marché</h1>
          <p>Lire le prix, comprendre le mouvement : graphique et cinq portes sur le même écran.</p>
        </div>
        <div className="iv-ph-act">
          <span className="iv-chip">
            Classe d’actifs · <b>{classLabel(assetClass)}</b>
          </span>
          <span className="iv-chip is-cyan">
            <i className={`iv-dot${chartLoading ? ' is-amber' : ''}`} />
            {sourceLabel}
          </span>
          <button
            type="button"
            className="iv-btn iv-btn--sm"
            onClick={() => openMarketTvWindow(symbol, interval)}
          >
            Ouvrir TV Marché ↗
          </button>
        </div>
      </header>

      {error && (
        <div className="mk-notice" role="alert">
          <span aria-hidden>△</span>
          <span>{error}</span>
        </div>
      )}

      <div className="iv-grid mk-grid">
        <section className="iv-card iv-s3 iv-m-s12 mk-watch" aria-label="Watchlist">
          <div className="iv-card-head">
            <div className="iv-card-tabs">
              <span className="iv-card-tab is-on">Watchlist</span>
            </div>
            <div className="iv-card-tools">{classLabel(assetClass)}</div>
          </div>
          <div className="mk-ctool" role="tablist" aria-label="Classe d’actifs">
            <button
              type="button"
              className={`mk-iv-tb${assetClass === 'all' ? ' is-on' : ''}`}
              onClick={() => setAssetClass('all')}
            >
              Tous
            </button>
            {classOptions.map((c) => (
              <button
                key={c}
                type="button"
                className={`mk-iv-tb${assetClass === c ? ' is-on' : ''}`}
                onClick={() => setAssetClass(c)}
              >
                {CLASS_LABELS[c]}
              </button>
            ))}
          </div>
          <div className="iv-card-body is-flush mk-watch-body">
            <div className="iv-table-wrap mk-watch-scroll">
              <table className="iv-table is-compact">
                <thead>
                  <tr>
                    <th>Actif</th>
                    <th className="n">Dernier</th>
                    <th className="n">Var.</th>
                    <th className="n">RVOL</th>
                  </tr>
                </thead>
                <tbody>
                  {watchRows.length === 0 && (
                    <tr>
                      <td colSpan={4} className="mk-td-empty">
                        Chargement…
                      </td>
                    </tr>
                  )}
                  {watchPaged.rows.map((w) => {
                    const ch = w.change24h
                    return (
                      <tr
                        key={w.id}
                        className={`mk-row${w.id === symbol ? ' is-selected' : ''}`}
                        aria-selected={w.id === symbol}
                        tabIndex={0}
                        onClick={() => setSymbol(w.id)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault()
                            setSymbol(w.id)
                          }
                        }}
                      >
                        <td className="sym">{w.label}</td>
                        <td className="n">{fmtPriceMaq(w.price)}</td>
                        <td className={`n ${ch == null ? 'dim' : ch >= 0 ? 'pos' : 'neg'}`}>
                          {fmtPctMaq(ch)}
                        </td>
                        <td className={`n${w.rvol != null && w.rvol >= 1.5 ? ' ok' : ''}`}>
                          {fmtRvolMaq(w.rvol)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
          <TablePager paged={watchPaged} label="actifs" />
        </section>

        <section className="iv-card iv-s6 iv-m-s12 mk-chart-card" aria-label="Graphique">
          <div className="iv-card-head">
            <div className="iv-card-tabs">
              <span className="iv-card-tab is-on">
                {shortSymbol(symbol)}
                <span className="mk-quote">{quote}</span> · {interval.toUpperCase()}
              </span>
            </div>
            <div className="iv-card-tools">
              {chartLoading ? 'Chargement…' : 'Bougies clôturées'}
            </div>
          </div>
          <div className="mk-ctool">
            {TFS.map((t) => (
              <button
                key={t.id}
                type="button"
                className={`mk-iv-tb${interval === t.id ? ' is-on' : ''}`}
                aria-pressed={interval === t.id}
                onClick={() => setInterval(t.id)}
              >
                {t.label}
              </button>
            ))}
            <span className="mk-sep" aria-hidden />
            <button
              type="button"
              className={`mk-iv-tb${ichimokuOn ? ' is-on' : ''}`}
              aria-pressed={ichimokuOn}
              title="Ichimoku 9 / 26 / 52"
              onClick={() => setLayers(withIchimoku(layerPrefs, !ichimokuOn))}
            >
              Ichimoku
            </button>
            <button
              type="button"
              className={`mk-iv-tb${levelsOn ? ' is-on' : ''}`}
              aria-pressed={levelsOn}
              title="Supports / résistances"
              onClick={() => toggleLayer('structure')}
            >
              Structure
            </button>
            <button
              type="button"
              className={`mk-iv-tb${layerPrefs.fibonacci ? ' is-on' : ''}`}
              aria-pressed={layerPrefs.fibonacci}
              onClick={() => toggleLayer('fibonacci')}
            >
              Fib
            </button>
            <button
              type="button"
              className={`mk-iv-tb${layerPrefs.fvg ? ' is-on' : ''}`}
              aria-pressed={layerPrefs.fvg}
              onClick={() => toggleLayer('fvg')}
            >
              FVG
            </button>
            <button
              type="button"
              className={`mk-iv-tb${layerPrefs.breaks ? ' is-on' : ''}`}
              aria-pressed={layerPrefs.breaks}
              onClick={() => toggleLayer('breaks')}
            >
              Cassures
            </button>
            <span className="mk-sep" aria-hidden />
            <div className="mkt-layers-anchor" ref={layersAnchorRef}>
              <button
                type="button"
                className={`mk-iv-tb${layersOpen ? ' is-on' : ''}`}
                aria-expanded={layersOpen}
                aria-haspopup="dialog"
                title="Afficher / masquer Structure, Fib, FVG, Cassures…"
                onClick={() => setLayersOpen((o) => !o)}
              >
                Calques{activeObjectLayerCount ? ` · ${activeObjectLayerCount}` : ''}
              </button>
              {layersOpen && !layersSheet && (
                <MarketLayersMenu
                  open
                  onClose={() => setLayersOpen(false)}
                  prefs={layerPrefs}
                  onChange={setLayers}
                  counts={layerCounts}
                  variant="menu"
                />
              )}
            </div>
            <button
              type="button"
              className="mk-iv-tb"
              title="Ouvrir le graphique en fenêtre TV"
              onClick={() => openMarketTvWindow(symbol, interval)}
            >
              TV ↗
            </button>
          </div>

          <div className="mk-chart-slot">
            {candles.length > 0 ? (
              <PriceChart
                candles={candles}
                symbol={symbol}
                timeframe={interval}
                layerPrefs={layerPrefs}
                onLayerPrefsChange={setLayers}
                chartObjects={chartObjectsForView}
              />
            ) : (
              <div className="iv-empty mk-chart-empty">
                {chartLoading ? 'Chargement…' : 'Aucune bougie'}
              </div>
            )}
          </div>

          <div className="iv-card-foot mk-chart-foot">
            <span>
              Prix <b className="mk-v">{fmtPriceMaq(priceDisplay)}</b>
            </span>
            <span>
              24 h{' '}
              <b className={`mk-v ${change24h == null ? '' : change24h >= 0 ? 'pos' : 'neg'}`}>
                {fmtPctMaq(change24h)}
              </b>
            </span>
            <span>
              RVOL <b className={`mk-v${rvolOk ? ' ok' : ''}`}>{fmtRvolMaq(rvolDisplay)}</b> ≥ 1,5
            </span>
            <span className="mk-foot-src">{sourceLabel}</span>
          </div>
        </section>

        {layersOpen && layersSheet && (
          <MarketLayersMenu
            open
            onClose={() => setLayersOpen(false)}
            prefs={layerPrefs}
            onChange={setLayers}
            counts={layerCounts}
            variant="sheet"
          />
        )}

        <div className="iv-s3 iv-m-s12 mk-side">
          <section className="iv-card iv-glow mk-read" aria-label="Lecture du marché">
            <div className="iv-card-head">
              <div className="iv-card-tabs">
                <span className="iv-card-tab is-on">Lecture du marché</span>
              </div>
              <div className="iv-card-tools">{shortSymbol(symbol)}</div>
            </div>
            <div className="iv-card-body">
              <div className="mk-tags">
                <span className={`iv-tag ${setupTagTone}`}>{setupName}</span>
                <span className={`iv-tag ${stateTagTone}`}>{setupState.text}</span>
              </div>
              <div className="mk-gates">
                {GATE_ORDER.map((id) => {
                  const stage = pipeline?.stages.find((s) => s.id === id)
                  const badge = maquetteGateBadge(stage?.status)
                  return (
                    <div className="iv-row mk-gate-row" key={id}>
                      <span
                        className={`mk-gate is-${badge.tone || 'cyan'}`}
                        title={badge.text}
                        aria-label={badge.text}
                      >
                        {GATE_GLYPH[badge.tone]}
                      </span>
                      <span className="mk-gate-k">{GATE_LABELS[id]}</span>
                      <span className="iv-row-v mk-gate-v">
                        {stage?.summary ? stage.summary : badge.text}
                      </span>
                    </div>
                  )
                })}
              </div>
              <p className="iv-note mk-synth">
                <span className="iv-kw">RVOL attendu ≥ 1,5</span> : {synthesis}
              </p>
            </div>
            <div className="mk-read-act">
              <button
                type="button"
                className="iv-btn iv-btn--primary"
                onClick={() =>
                  navigate(`/app/opportunites?symbol=${encodeURIComponent(symbol)}&open=1`)
                }
              >
                Préparer le trade →
              </button>
              <button
                type="button"
                className="iv-btn"
                disabled={watchBusy}
                onClick={() => void onAddWatchlist()}
              >
                Watchlist
              </button>
            </div>
            {watchMsg && <p className="iv-note mk-watch-msg">{watchMsg}</p>}
            <div className="iv-card-foot">
              <span>Fiche décision</span>
              <Link to={`/app/opportunites?symbol=${encodeURIComponent(symbol)}`}>Voir ↗</Link>
            </div>
          </section>
          <section className="iv-card mk-inst" aria-label="Instrument">
            <div className="iv-card-head">
              <div className="iv-card-tabs">
                <span className="iv-card-tab is-on">Instrument</span>
              </div>
              <div className="iv-card-tools">{interval.toUpperCase()}</div>
            </div>
            <div className="iv-card-body">
              <div className="iv-row">
                <span>Dernier prix</span>
                <span className="iv-row-v">{fmtPriceMaq(priceDisplay)}</span>
              </div>
              <div className="iv-row">
                <span>Variation 24 h</span>
                <span
                  className={`iv-row-v${change24h == null ? '' : change24h >= 0 ? ' pos' : ' neg'}`}
                >
                  {fmtPctMaq(change24h)}
                </span>
              </div>
              <div className="iv-row">
                <span>RVOL (attendu ≥ 1,5)</span>
                <span className={`iv-row-v${rvolOk ? ' ok' : ''}`}>{fmtRvolMaq(rvolDisplay)}</span>
              </div>
              <div className="iv-row">
                <span>Classe d’actifs</span>
                <span className="iv-row-v">{current ? CLASS_LABELS[current.asset_class] : '—'}</span>
              </div>
              <div className="iv-row">
                <span>Source</span>
                <span className="iv-row-v">{sourceLabel}</span>
              </div>
            </div>
          </section>
        </div>

        <section className="iv-card iv-s12 mk-evidence" aria-label="Preuves du moteur">
          <div className="iv-card-head">
            <div className="iv-card-tabs" role="tablist">
              {EVIDENCE_TABS.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  className={`iv-card-tab${evidenceTab === t.id ? ' is-on' : ''}`}
                  aria-selected={evidenceTab === t.id}
                  onClick={() => setEvidenceTab(t.id)}
                >
                  {t.label}
                </button>
              ))}
            </div>
            <div className="iv-card-tools">
              {shortSymbol(symbol)} · {interval.toUpperCase()}
            </div>
          </div>
          <div className="iv-card-body mk-evidence-body">
            {detail && pipeline ? (
              <div className="engine-evidence is-wide">
                {evidenceTab === 'pipeline' && (
                  <>
                    <p className="argumentaire">{buildDecisionSummary(detail)}</p>
                    <DecisionPipelinePanel view={pipeline} />
                  </>
                )}
                {evidenceTab === 'signal' && <SignalEvidenceCard detail={detail} />}
                {evidenceTab === 'mtf' && <MtfPanel symbol={symbol} timeframe={interval} />}
              </div>
            ) : (
              <div className="iv-empty">—</div>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
