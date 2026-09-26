/**
 * Marché — port littéral de design-reference/ichivol-workspace `marche()` + page-head.
 * Classes HTML = maquette. Données = engine (pas de démo inventée).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { DecisionPipelinePanel } from '../components/DecisionPipelinePanel'
import { MarketLayersMenu } from '../components/MarketLayersMenu'
import { ChartIntelligencePanel } from '../components/chart-intelligence'
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
            .slice(0, 60)
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

  return (
    <div className="market-page">
      <div className="page-head">
        <div>
          <div className="eyebrow">02 / ICHIVOL WORKSPACE</div>
          <h1>Marché</h1>
          <p className="subtitle">Lire le prix. Comprendre le mouvement.</p>
        </div>
        <div className="actions">
          <button
            type="button"
            className="suggestion market-tv-open"
            onClick={() => openMarketTvWindow(symbol, interval)}
          >
            Ouvrir en TV
          </button>
          <span className="tag gray">BOUGIES CLÔTURÉES</span>
        </div>
      </div>

      {error && (
        <div className="notice" role="alert">
          <span>△</span>
          <span>{error}</span>
        </div>
      )}

      <div className="class-chips" role="tablist" aria-label="Classe d’actifs">
        <button
          type="button"
          className={assetClass === 'all' ? 'active' : undefined}
          onClick={() => setAssetClass('all')}
        >
          Tous
        </button>
        {classOptions.map((c) => (
          <button
            key={c}
            type="button"
            className={assetClass === c ? 'active' : undefined}
            onClick={() => setAssetClass(c)}
          >
            {CLASS_LABELS[c]}
          </button>
        ))}
      </div>

      <div className="market-layout">
        <section className="card watchlist" aria-label="Watchlist">
          {watchRows.length === 0 && (
            <button type="button" disabled>
              <b>—</b>
              <small>Chargement…</small>
            </button>
          )}
          {watchRows.map((w) => {
            const ch = w.change24h
            const up = ch != null && ch >= 0
            return (
              <button
                key={w.id}
                type="button"
                className={w.id === symbol ? 'active' : undefined}
                onClick={() => setSymbol(w.id)}
              >
                <b>{w.label}</b>
                <span
                  className={ch == null ? 'chg-na' : up ? 'up' : 'down'}
                  style={{ fontSize: 10 }}
                >
                  {fmtPctMaq(ch)}
                </span>
                <small>{fmtPriceMaq(w.price)}</small>
              </button>
            )
          })}
        </section>

        <section className="card">
          <div className="card-head">
            <div>
              <h2>
                {shortSymbol(symbol)}
                <span style={{ font: '12px Manrope, sans-serif', color: '#91989d' }}>{quote}</span>
              </h2>
              <small>
                {sourceLabel} · bougies clôturées
                {chartLoading ? ' · chargement…' : ''}
              </small>
            </div>
            <div className="card-head-tools">
              <div className="mkt-layers-anchor" ref={layersAnchorRef}>
                <button
                  type="button"
                  className={`mkt-layers-btn mkt-layers-btn-head${layersOpen ? ' is-open' : ''}`}
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
                className="market-tv-open-inline"
                title="Ouvrir le graphique en fenêtre TV"
                onClick={() => openMarketTvWindow(symbol, interval)}
              >
                TV
              </button>
              <div className="segmented">
                {TFS.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    className={interval === t.id ? 'active' : undefined}
                    onClick={() => setInterval(t.id)}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="chart-summary">
            <span>
              PRIX <b>{fmtPriceMaq(priceDisplay)}</b>
            </span>
            <span>
              24H{' '}
              <b className={change24h == null ? undefined : change24h >= 0 ? 'up' : 'down'}>
                {fmtPctMaq(change24h)}
              </b>
            </span>
            <span>
              RVOL <b>{fmtRvolMaq(rvolDisplay)}</b>
            </span>
          </div>

          <div className="market-chart-slot">
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
              <div className="empty">Aucune bougie</div>
            )}
          </div>

          <div className="card-body chart-tools">
            <div className="checkrow">
              <label>
                <input
                  type="checkbox"
                  checked={ichimokuOn}
                  onChange={(e) => setLayers(withIchimoku(layerPrefs, e.target.checked))}
                />{' '}
                Ichimoku 9 / 26 / 52
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={levelsOn}
                  onChange={(e) => setLayers({ ...layerPrefs, structure: e.target.checked })}
                />{' '}
                Supports / résistances
              </label>
              <span className="chart-tools-hint">
                Fib · FVG · Cassures → bouton <b>Calques</b> en haut à droite
              </span>
            </div>
          </div>
        </section>

        <ChartIntelligencePanel symbol={symbol} timeframe={interval} source="api" />

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

        <section className="card analysis-panel">
          <div className="card-head">
            <h2>Lecture du marché</h2>
            <div className="analysis-actions">
              <button
                type="button"
                className="primary"
                onClick={() =>
                  navigate(`/app/opportunites?symbol=${encodeURIComponent(symbol)}&open=1`)
                }
              >
                Préparer le trade →
              </button>
              <button
                type="button"
                className="suggestion"
                disabled={watchBusy}
                onClick={() => void onAddWatchlist()}
              >
                Watchlist
              </button>
            </div>
          </div>
          <div className="card-body analysis-body">
            <div className="analysis-gates">
              {GATE_ORDER.map((id) => {
                const stage = pipeline?.stages.find((s) => s.id === id)
                const badge = maquetteGateBadge(stage?.status)
                return (
                  <div className="statline" key={id}>
                    <span>{GATE_LABELS[id]}</span>
                    <b>
                      <span className={`tag ${badge.tone}`.trim()}>{badge.text}</span>
                    </b>
                  </div>
                )
              })}
            </div>
            <p className="lecture-synthesis">{synthesis}</p>
            {detail && pipeline ? (
              <div className="engine-evidence is-wide">
                <p className="argumentaire">{buildDecisionSummary(detail)}</p>
                <DecisionPipelinePanel view={pipeline} />
                <SignalEvidenceCard detail={detail} />
              </div>
            ) : (
              <p className="lecture-synthesis">—</p>
            )}
            <div className="analysis-foot">
              <div className="step">
                <b>{setupName}</b>
                <p>RVOL attendu ≥ 1,5</p>
                <span className={`tag ${setupState.tone}`.trim()}>{setupState.text}</span>
              </div>
              {watchMsg && <p className="watch-msg">{watchMsg}</p>}
              <p className="fiche-link">
                <Link className="link" to={`/app/opportunites?symbol=${encodeURIComponent(symbol)}`}>
                  Voir la fiche décision ↗
                </Link>
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
