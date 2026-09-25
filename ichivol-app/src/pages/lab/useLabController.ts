import { type FormEvent, useEffect, useMemo, useState } from 'react'
import {
  getBacktestCoverage,
  type BacktestCoverage,
} from '../../lib/activity'
import {
  compareStoredRulesets,
  getAblation,
  getBacktestComparison,
  getBacktestEvidence,
  getEventStudy,
  getRegimeSlices,
  getRulesetEventStudy,
  getWalkForward,
  getWalkForwardOpt,
  listRulesets,
  listStoredExperiments,
  type AblationResult,
  type BacktestComparison,
  type BacktestEvidenceSummary,
  type EventStudyResult,
  type RegimeSlicesResult,
  type RulesetStudyResult,
  type RulesetSummary,
  type StoredExperimentSummary,
  type WalkForwardOptResult,
  type WalkForwardResult,
} from '../../lib/backtest'
import {
  getEngineUniverse,
  type EngineAssetClass,
  type EngineInstrument,
} from '../../lib/universe'
import {
  CLASS_ORDER,
  EXPERIMENT_ORDER,
  REGIME_FILTERS,
  collectEquitySeries,
  friendlyBacktestError,
  metricsBasisLabel,
  type LabTab,
} from './labShared'

export function useLabController() {
  const [instruments, setInstruments] = useState<EngineInstrument[]>([])
  const [universeError, setUniverseError] = useState<string | null>(null)
  const [marketClass, setMarketClass] = useState<EngineAssetClass>('crypto')
  const [symbol, setSymbol] = useState('BTCUSDT')
  const [timeframe, setTimeframe] = useState('1h')
  const [limit, setLimit] = useState(1000)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<BacktestComparison | null>(null)
  const [eventStudy, setEventStudy] = useState<EventStudyResult | null>(null)
  const [rulesets, setRulesets] = useState<RulesetSummary[]>([])
  const [rulesetId, setRulesetId] = useState('IV_ICHIMOKU_RVOL_LONG_001')
  const [rulesetStudy, setRulesetStudy] = useState<RulesetStudyResult | null>(null)
  const [stored, setStored] = useState<StoredExperimentSummary[]>([])
  const [ablation, setAblation] = useState<AblationResult | null>(null)
  const [regimeSlices, setRegimeSlices] = useState<RegimeSlicesResult | null>(null)
  const [walkForward, setWalkForward] = useState<WalkForwardResult | null>(null)
  const [walkForwardOpt, setWalkForwardOpt] = useState<WalkForwardOptResult | null>(null)
  const [evidence, setEvidence] = useState<BacktestEvidenceSummary | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [labTab, setLabTab] = useState<LabTab>('compare')
  const [dbCompare, setDbCompare] = useState<StoredExperimentSummary[]>([])
  const [dbLoading, setDbLoading] = useState(false)
  const [dbError, setDbError] = useState<string | null>(null)
  const [regimeFilter, setRegimeFilter] = useState<(typeof REGIME_FILTERS)[number]>('ALL')
  const [coverage, setCoverage] = useState<BacktestCoverage | null>(null)
  const [kpiExperiments, setKpiExperiments] = useState<StoredExperimentSummary[]>([])

  const visibleClasses = useMemo(() => {
    const present = new Set(
      instruments.filter((i) => i.wired).map((i) => i.asset_class),
    )
    return CLASS_ORDER.filter((c) => present.has(c))
  }, [instruments])

  const classInstruments = useMemo(
    () => instruments.filter((i) => i.asset_class === marketClass && i.wired),
    [instruments, marketClass],
  )

  const current = useMemo(
    () => instruments.find((i) => i.id === symbol) ?? null,
    [instruments, symbol],
  )

  useEffect(() => {
    let cancelled = false
    getEngineUniverse()
      .then((u) => {
        if (cancelled) return
        setInstruments(u.instruments)
        setUniverseError(null)
        setSymbol((prev) => {
          if (u.instruments.some((i) => i.id === prev && i.wired)) return prev
          const first = u.instruments.find((i) => i.wired)
          if (first) {
            setMarketClass(first.asset_class)
            return first.id
          }
          return prev
        })
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setUniverseError(err instanceof Error ? err.message : 'Univers moteur indisponible')
        }
      })
    getBacktestEvidence()
      .then((summary) => {
        if (!cancelled) setEvidence(summary)
      })
      .catch(() => {
        if (!cancelled) setEvidence(null)
      })
    getBacktestCoverage()
      .then((cov) => {
        if (!cancelled) setCoverage(cov)
      })
      .catch(() => {
        if (!cancelled) setCoverage(null)
      })
    listStoredExperiments({ limit: 40 })
      .then((hist) => {
        if (!cancelled) setKpiExperiments(hist.experiments)
      })
      .catch(() => {
        if (!cancelled) setKpiExperiments([])
      })
    listRulesets()
      .then((payload) => {
        if (cancelled) return
        setRulesets(payload.rulesets)
        if (payload.rulesets[0] && !payload.rulesets.some((r) => r.id === rulesetId)) {
          setRulesetId(payload.rulesets[0].id)
        }
      })
      .catch(() => {
        if (!cancelled) setRulesets([])
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (labTab === 'live' || labTab === 'research') return
    const sym = symbol.trim().toUpperCase()
    if (!sym) return
    let cancelled = false
    setDbLoading(true)
    setDbError(null)
    const ids = rulesets.map((r) => r.id)
    const tasks: Promise<void>[] = [
      listStoredExperiments({
        symbol: sym,
        timeframe,
        limit: 50,
        market_regime: regimeFilter === 'ALL' ? undefined : regimeFilter,
      })
        .then((hist) => {
          if (!cancelled) setStored(hist.experiments)
        })
        .catch((err: unknown) => {
          if (!cancelled) {
            setStored([])
            setDbError(err instanceof Error ? err.message : String(err))
          }
        }),
    ]
    if (labTab === 'compare' && ids.length > 0) {
      tasks.push(
        compareStoredRulesets({
          symbol: sym,
          timeframe,
          ruleset_ids: ids,
          market_regime: 'GLOBAL',
        })
          .then((cmp) => {
            if (!cancelled) setDbCompare(cmp.experiments)
          })
          .catch((err: unknown) => {
            if (!cancelled) {
              setDbCompare([])
              setDbError(err instanceof Error ? err.message : String(err))
            }
          }),
      )
    }
    Promise.allSettled(tasks).finally(() => {
      if (!cancelled) setDbLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [labTab, symbol, timeframe, rulesets, regimeFilter])

  function selectClass(next: EngineAssetClass) {
    setMarketClass(next)
    const list = instruments.filter((i) => i.asset_class === next && i.wired)
    if (list[0] && !list.some((i) => i.id === symbol)) {
      setSymbol(list[0].id)
    }
    // Biquote ~100 bars/call (accumulation) ; Twelve Data = crédits — plafonner défaut
    if (next !== 'crypto' && limit > 500) setLimit(300)
  }

  function run(e?: FormEvent) {
    e?.preventDefault()
    const sym = symbol.trim().toUpperCase()
    if (!sym) return
    setLoading(true)
    setError(null)
    setEventStudy(null)
    setRulesetStudy(null)
    setAblation(null)
    setRegimeSlices(null)
    setWalkForward(null)
    setWalkForwardOpt(null)
    Promise.allSettled([
      getBacktestComparison(sym, timeframe, limit),
      getEventStudy(sym, timeframe, limit, 'PIPELINE'),
      getRulesetEventStudy(rulesetId, sym, timeframe, limit),
      getAblation(sym, timeframe, limit, false),
      getRegimeSlices(sym, timeframe, limit, rulesetId, false),
      getWalkForward(sym, timeframe, limit, rulesetId, { persist: false }),
      getWalkForwardOpt(sym, timeframe, limit, rulesetId, { persist: false }),
    ])
      .then((results) => {
        const [bt, es, rs, ab, rg, wf, wfo] = results
        const errors: string[] = []
        if (bt.status === 'fulfilled') setResult(bt.value)
        else errors.push(bt.reason instanceof Error ? bt.reason.message : String(bt.reason))
        if (es.status === 'fulfilled') setEventStudy(es.value)
        else errors.push(es.reason instanceof Error ? es.reason.message : String(es.reason))
        if (rs.status === 'fulfilled') setRulesetStudy(rs.value)
        else errors.push(rs.reason instanceof Error ? rs.reason.message : String(rs.reason))
        if (ab.status === 'fulfilled') setAblation(ab.value)
        if (rg.status === 'fulfilled') setRegimeSlices(rg.value)
        if (wf.status === 'fulfilled') setWalkForward(wf.value)
        else errors.push(wf.reason instanceof Error ? wf.reason.message : String(wf.reason))
        if (wfo.status === 'fulfilled') setWalkForwardOpt(wfo.value)
        else errors.push(wfo.reason instanceof Error ? wfo.reason.message : String(wfo.reason))

        if (bt.status === 'fulfilled') {
          listStoredExperiments({ symbol: sym, timeframe, limit: 10 })
            .then((hist) => setStored(hist.experiments))
            .catch(() => setStored([]))
        }
        if (errors.length && bt.status !== 'fulfilled') {
          setError(friendlyBacktestError(errors[0]))
        } else if (errors.length) {
          setError(friendlyBacktestError(`Partiel : ${errors[0]}`))
        }
      })
      .finally(() => setLoading(false))
  }

  const best = result
    ? EXPERIMENT_ORDER.filter((name) => result.experiments[name]).reduce((a, b) => {
        const sa = result.experiments[a]?.metrics.sharpe ?? Number.NEGATIVE_INFINITY
        const sb = result.experiments[b]?.metrics.sharpe ?? Number.NEGATIVE_INFINITY
        return sb > sa ? b : a
      })
    : null

  const columns = result
    ? EXPERIMENT_ORDER.filter((name) => result.experiments[name])
    : EXPERIMENT_ORDER

  const edge = evidence?.pipeline_beats_ichimoku_sharpe
  const edgeLabel = edge
    ? `${edge.beats}/${edge.compared}`
    : evidence?.total_rows
      ? 'en cours'
      : '—'

  const experimentsForKpi = useMemo(() => {
    const byId = new Map<string, StoredExperimentSummary>()
    for (const row of [...kpiExperiments, ...stored, ...dbCompare]) {
      byId.set(row.experiment_id, row)
    }
    return [...byId.values()]
  }, [kpiExperiments, stored, dbCompare])

  const labKpis = useMemo(() => {
    const othersCovered = coverage
      ? coverage.others.filter((o) => o.covered).length
      : null

    let universValue: string | null = null
    let universMeta: string | null = null
    if (coverage) {
      if (coverage.pairs_covered > 0) {
        universValue = `${coverage.pairs_covered} paires`
        universMeta =
          coverage.crypto_symbols > 0
            ? `${coverage.crypto_symbols} cryptos`
            : othersCovered != null && coverage.others.length > 0
              ? `${othersCovered}/${coverage.others.length} hors crypto`
              : null
      } else if (coverage.crypto_symbols > 0) {
        universValue = `${coverage.crypto_symbols} cryptos`
        universMeta =
          othersCovered != null && coverage.others.length > 0
            ? `${othersCovered}/${coverage.others.length} hors crypto`
            : null
      }
    }

    let fenetreValue: string | null = null
    let fenetreMeta: string | null = null
    if (coverage?.timeframes?.length) {
      fenetreValue = coverage.timeframes.join(' · ')
      fenetreMeta = coverage.min_bars > 0 ? `≥ ${coverage.min_bars} bougies` : null
    } else if (experimentsForKpi.length > 0) {
      const tfs = [...new Set(experimentsForKpi.map((e) => e.timeframe).filter(Boolean))]
      if (tfs.length) fenetreValue = tfs.join(' · ')
    }

    let validationValue: string | null = null
    let validationMeta: string | null = null
    if (coverage && coverage.min_bars > 0) {
      validationValue = `≥ ${coverage.min_bars}`
      validationMeta = 'bougies min. couverture'
    } else {
      const bases = experimentsForKpi
        .map((e) => e.metrics_basis)
        .filter((b): b is string => Boolean(b))
      if (bases.length) {
        const unique = [...new Set(bases)]
        validationValue = unique.map(metricsBasisLabel).join(' · ')
        validationMeta = `${bases.length} run${bases.length > 1 ? 's' : ''} mesurés`
      }
    }

    let hypotheseValue: string | null = null
    let hypotheseMeta: string | null = null
    const withHyp = experimentsForKpi.filter((e) => e.hypothesis_id)
    if (withHyp.length) {
      const latest = [...withHyp].sort((a, b) =>
        (b.created_at ?? '').localeCompare(a.created_at ?? ''),
      )[0]
      hypotheseValue = latest.hypothesis_id ?? null
      hypotheseMeta = latest.ruleset_id
    } else if (experimentsForKpi.length) {
      const latest = [...experimentsForKpi].sort((a, b) =>
        (b.created_at ?? '').localeCompare(a.created_at ?? ''),
      )[0]
      hypotheseValue = latest.ruleset_id
      hypotheseMeta = latest.symbol ? `${latest.symbol} · ${latest.timeframe}` : null
    }

    return [
      { label: 'Univers', value: universValue, meta: universMeta },
      { label: 'Fenêtre', value: fenetreValue, meta: fenetreMeta },
      { label: 'Validation', value: validationValue, meta: validationMeta },
      { label: 'Hypothèse', value: hypotheseValue, meta: hypotheseMeta },
    ]
  }, [coverage, experimentsForKpi])

  const equitySeries = useMemo(
    () =>
      collectEquitySeries([
        result,
        ablation,
        walkForward,
        walkForwardOpt,
        ...dbCompare,
        ...stored,
      ]),
    [result, ablation, walkForward, walkForwardOpt, dbCompare, stored],
  )

  return {
    instruments,
    setInstruments,
    universeError,
    setUniverseError,
    marketClass,
    setMarketClass,
    symbol,
    setSymbol,
    timeframe,
    setTimeframe,
    limit,
    setLimit,
    loading,
    setLoading,
    error,
    setError,
    result,
    setResult,
    eventStudy,
    setEventStudy,
    rulesets,
    setRulesets,
    rulesetId,
    setRulesetId,
    rulesetStudy,
    setRulesetStudy,
    stored,
    setStored,
    ablation,
    setAblation,
    regimeSlices,
    setRegimeSlices,
    walkForward,
    setWalkForward,
    walkForwardOpt,
    setWalkForwardOpt,
    evidence,
    setEvidence,
    historyOpen,
    setHistoryOpen,
    labTab,
    setLabTab,
    dbCompare,
    setDbCompare,
    dbLoading,
    setDbLoading,
    dbError,
    setDbError,
    regimeFilter,
    setRegimeFilter,
    coverage,
    setCoverage,
    kpiExperiments,
    setKpiExperiments,
    visibleClasses,
    classInstruments,
    current,
    selectClass,
    run,
    best,
    columns,
    edge,
    edgeLabel,
    experimentsForKpi,
    labKpis,
    equitySeries,
  }
}
