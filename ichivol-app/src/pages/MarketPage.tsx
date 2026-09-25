/**
 * Marché — port littéral de design-reference/ichivol-workspace `marche()` + page-head.
 * Classes HTML = maquette. Données = engine (pas de démo inventée).
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { PriceChart } from '../components/PriceChart'
import { confirmAgentAction } from '../lib/agent'
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
import {
  loadLayerPrefs,
  saveLayerPrefs,
  withIchimoku,
  type LayerPrefs,
} from '../lib/marketPrefs'
import type { Candle, Interval } from '../lib/types'
import {
  getEngineOhlcv,
  getEngineUniverse,
  type EngineInstrument,
} from '../lib/universe'
import {
  fmtPctMaq,
  fmtPriceMaq,
  fmtRvolMaq,
  lectureSynthesisFr,
  maquetteGateBadge,
  shortSymbol,
} from './market/marketMaquetteHelpers'
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

  const ichimokuOn =
    layerPrefs.tenkan && layerPrefs.kijun && layerPrefs.spanA && layerPrefs.spanB
  const levelsOn = layerPrefs.structure

  const setLayers = useCallback((next: LayerPrefs) => {
    setLayerPrefs(next)
    saveLayerPrefs(next)
  }, [])

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

  const watchRows: WatchRow[] = useMemo(() => {
    const list =
      instruments.length > 0
        ? instruments.filter((i) => i.asset_class === 'crypto').slice(0, 40)
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
  }, [instruments, screenerById, tickers24h])

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
    if (g === 'BUY' || g === 'SELL') return { text: 'TRIGGERED', tone: 'green' as const }
    if (g === 'WATCH') return { text: 'ARMED', tone: '' as const }
    if (g === 'NO_TRADE') return { text: 'WATCH', tone: 'gray' as const }
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
          <span className="tag gray">BOUGIES CLÔTURÉES</span>
        </div>
      </div>

      {error && (
        <div className="notice" role="alert">
          <span>△</span>
          <span>{error}</span>
        </div>
      )}

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
              />
            ) : (
              <div className="empty">Aucune bougie</div>
            )}
          </div>

          <div className="card-body">
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
            </div>
          </div>
        </section>

        <section className="card analysis-panel">
          <div className="card-head">
            <h2>Lecture du marché</h2>
          </div>
          <div className="card-body">
            {GATE_ORDER.map((id) => {
              const stage = pipeline?.stages.find((s) => s.id === id)
              const badge = maquetteGateBadge(stage?.status)
              return (
                <div className="statline" key={id}>
                  <span>{GATE_LABELS[id]}</span>
                  <span className={`tag ${badge.tone}`.trim()}>{badge.text}</span>
                </div>
              )
            })}
            <p className="lecture-synthesis">{synthesis}</p>
            <div className="step">
              <b>{setupName}</b>
              <p>
                RVOL attendu ≥ 1,5
                {rvolDisplay != null ? ` · actuel ${fmtRvolMaq(rvolDisplay)}` : ''}
              </p>
              <span className={`tag ${setupState.tone}`.trim()}>{setupState.text}</span>
            </div>
            <button
              type="button"
              className="primary"
              onClick={() =>
                navigate(`/app/opportunites?symbol=${encodeURIComponent(symbol)}`)
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
              Ajouter à la watchlist
            </button>
            {watchMsg && <p className="watch-msg">{watchMsg}</p>}
            <p className="fiche-link">
              <Link className="link" to={`/app/opportunites?symbol=${encodeURIComponent(symbol)}`}>
                Voir la fiche décision ↗
              </Link>
            </p>
          </div>
        </section>
      </div>
    </div>
  )
}
