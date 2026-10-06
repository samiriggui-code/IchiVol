/**
 * Strategy Lab : transforme un résultat brut du moteur en fiche lisible (« Examiner »).
 * Chaque fiche dit en clair : ce qui a été mesuré, le résultat, comment c'est calculé et quoi en conclure.
 * Uniquement des valeurs fournies par le moteur ; absent → « — » ou phrase neutre, jamais d'invention.
 */

import type { BacktestRun, RunExperiment } from './activity'
import type {
  AblationDelta,
  AblationStepRow,
  BacktestMetrics,
  RegimeSliceRow,
  RulesetStudyResult,
  RulesetSummary,
  RulesetTrade,
  WalkForwardFoldRow,
} from './backtest'
import { VARIANT_LABELS, ablationVerdict, layerLabel, num, pct, regimeLabel, type Verdict } from './labFormat.ts'

export interface ExplainStat {
  label: string
  value: string
  hint: string
  tone?: 'up' | 'down' | ''
}

export interface ExplainHistoryRow {
  when: string
  trades: string
  winRate: string
  expectancy: string
  profitFactor: string
}

export interface Explanation {
  title: string
  subtitle: string
  verdict: Verdict
  /** Le résultat en 2–3 phrases simples. */
  summary: string[]
  stats: ExplainStat[]
  /** Comment le chiffre a été obtenu, étape par étape. */
  method: string[]
  /** Quoi en conclure. */
  takeaway: string
  trades?: RulesetTrade[]
  history?: ExplainHistoryRow[]
}

export interface StudyContext {
  symbol: string
  timeframe: string
  nBars: number
}

const MIN_TRADES = 30

const TF_WORDS: Record<string, string> = { '1h': 'bougies d’une heure', '4h': 'bougies de 4 heures', '1d': 'bougies journalières' }

function tfWords(tf: string): string {
  return TF_WORDS[tf] ?? `bougies ${tf}`
}

function coin(symbol: string): string {
  return symbol.replace(/USDT$/, '')
}

function tone(v: number | null | undefined): 'up' | 'down' | '' {
  if (v == null || !Number.isFinite(v) || v === 0) return ''
  return v > 0 ? 'up' : 'down'
}

function plural(n: number, one: string, many: string): string {
  return `${n} ${n > 1 ? many : one}`
}

/** Condition de règle → phrase. */
export function conditionText(key: string, value: boolean | number): string {
  switch (key) {
    case 'price_above_kumo':
      return 'le prix clôture au-dessus du nuage Ichimoku'
    case 'tenkan_above_kijun':
      return 'la Tenkan est au-dessus de la Kijun (tendance courte haussière)'
    case 'tk_cross_age_max':
      return `le croisement haussier Tenkan/Kijun date de ${value} bougies au plus`
    case 'rvol_min':
      return `le volume de la bougie vaut au moins ${num(Number(value), 1)} fois le volume habituel`
    case 'bos_bullish':
      return 'le prix vient de casser un sommet récent (cassure de structure haussière)'
    case 'atr_expansion':
      return 'la volatilité (ATR) est en hausse'
    case 'cmf_min':
      return `le flux d’argent (CMF) est supérieur ou égal à ${num(Number(value), 2)} : les acheteurs dominent`
    default:
      return `${key.replace(/_/g, ' ')} = ${String(value)}`
  }
}

function conditionList(rs: RulesetSummary | null | undefined): string {
  if (!rs?.conditions) return 'les conditions de la règle'
  const parts = Object.entries(rs.conditions).map(([k, v]) => conditionText(k, v))
  return parts.length ? parts.join(' ; ') : 'les conditions de la règle'
}

/** Mécanique commune d'un backtest de règle (entrée, stop, objectif, frais). */
function tradeMechanics(rs: RulesetSummary | null | undefined, study: RulesetStudyResult | null | undefined): string[] {
  const stop = rs?.stop_atr
  const target = rs?.target_atr
  const fees = study?.backtest?.backtest
  const out = [
    'On achète à l’ouverture de la bougie qui suit le signal : on ne connaît jamais la bougie avant qu’elle soit close.',
  ]
  if (stop != null && target != null) {
    out.push(
      `Stop à ${num(stop, 1)} ATR sous l’entrée, objectif à ${num(target, 1)} ATR au-dessus (l’ATR est l’amplitude moyenne d’une bougie). Si les deux sont touchés dans la même bougie, on compte le stop, par prudence.`,
    )
  }
  if (fees?.commission_bps != null && fees?.slippage_bps != null) {
    out.push(
      `Frais déduits à chaque passage d’ordre : ${num(fees.commission_bps / 100, 2)} % de commission + ${num(fees.slippage_bps / 100, 2)} % de glissement.`,
    )
  }
  return out
}

function lexicon(): string {
  return 'Réussite = part des trades gagnants. Espérance = gain moyen par trade, frais déduits. Profit factor = total des gains ÷ total des pertes (au-dessus de 1, la stratégie gagne plus qu’elle ne perd). Drawdown = pire baisse du capital depuis un sommet.'
}

function sampleWarning(n: number | null | undefined): string | null {
  if (n == null) return null
  if (n === 0) return 'Aucun trade : impossible de juger.'
  if (n < MIN_TRADES)
    return `Seulement ${plural(n, 'trade', 'trades')} : en dessous de ${MIN_TRADES}, le hasard pèse plus que la stratégie. À confirmer sur plus d’historique.`
  return null
}

/** Verdict sur une performance : rentable si espérance > 0 et profit factor > 1. */
export function performanceVerdict(m: { trades: number; expectancy: number | null; pf: number | null }): Verdict {
  if (!m.trades) return { text: 'AUCUN TRADE', tone: 'gray' }
  if (m.trades < MIN_TRADES) {
    if (m.expectancy != null && m.expectancy > 0) return { text: 'PROMETTEUR, PEU DE TRADES', tone: 'amber' }
    return { text: 'PEU DE TRADES', tone: 'gray' }
  }
  if (m.expectancy != null && m.expectancy > 0 && (m.pf == null || m.pf > 1)) return { text: 'RENTABLE', tone: 'green' }
  if (m.expectancy != null && m.expectancy > 0) return { text: 'FRAGILE', tone: 'amber' }
  return { text: 'PERDANT', tone: 'red' }
}

function metricStats(m: BacktestMetrics | null): ExplainStat[] {
  const n = m?.num_trades ?? 0
  const wins = m?.win_rate != null ? Math.round(m.win_rate * n) : null
  return [
    {
      label: 'Trades',
      value: m ? String(n) : '—',
      hint: wins != null ? `${wins} gagnants, ${n - wins} perdants` : 'Positions simulées',
    },
    { label: 'Réussite', value: pct(m?.win_rate), hint: 'Part des trades gagnants' },
    {
      label: 'Espérance / trade',
      value: pct(m?.expectancy, 2, true),
      hint: 'Gain moyen par trade, frais déduits',
      tone: tone(m?.expectancy),
    },
    { label: 'Profit factor', value: num(m?.profit_factor), hint: 'Gains ÷ pertes ; > 1 = gagnant' },
    { label: 'Drawdown max', value: pct(m?.max_drawdown), hint: 'Pire baisse depuis un sommet' },
    {
      label: 'Rendement total',
      value: pct(m?.total_return, 1, true),
      hint: 'Sur toute la période testée',
      tone: tone(m?.total_return),
    },
  ]
}

function tradesOf(study: RulesetStudyResult | null | undefined): RulesetTrade[] | undefined {
  const t = study?.backtest?.trades
  return t && t.length ? t : undefined
}

function metricsOf(study: RulesetStudyResult | null | undefined): BacktestMetrics | null {
  return study?.backtest?.metrics ?? null
}

/* ----------------------------------------------------------------------------------------------
 * Backtests : une variante du backtest quotidien
 * -------------------------------------------------------------------------------------------- */

const VARIANT_HOW: Record<string, string> = {
  ICHIMOKU_ONLY:
    'Position acheteuse quand la structure Ichimoku est haussière (prix au-dessus du nuage, Tenkan au-dessus de la Kijun), sans aucun filtre de volume. C’est la référence.',
  ICHIMOKU_RVOL:
    'Même structure Ichimoku, mais le volume relatif doit rester élevé à chaque bougie : dès qu’il retombe, on sort. Plus strict, mais peut multiplier les entrées/sorties.',
  ICHIMOKU_RVOL_ENTRY_GATE:
    'Même structure Ichimoku ; le volume relatif ne sert qu’à confirmer l’entrée. Une fois entré, on garde tant que la structure tient.',
  PIPELINE:
    'Le moteur complet : direction, participation (volume), structure / multi-unités, puis filtres de régime (ADX, Donchian). On n’est en position que si le pipeline dit ACHAT ou VENTE.',
  PIPELINE_WYCKOFF_FILTER:
    'Le pipeline complet, plus un filtre Wyckoff (spring / upthrust) qui peut seulement annuler une position. Expérimental : jusqu’ici sans effet positif prouvé.',
}

export function explainVariant(
  key: string,
  e: RunExperiment,
  runs: BacktestRun[],
  baseline: RunExperiment | null,
  minTrades: number,
): Explanation {
  const name = VARIANT_LABELS[key] ?? key
  const last = runs[0]
  const verdict = e.small_sample
    ? { text: 'ÉCHANTILLON FAIBLE', tone: 'amber' as const }
    : performanceVerdict({ trades: e.trades_total, expectancy: e.expectancy_mean, pf: e.profit_factor_median })

  const summary: string[] = [
    `Lors du dernier calcul, « ${name} » a pris ${plural(e.trades_total, 'trade', 'trades')} sur ${plural(e.n_pairs, 'paire', 'paires')} (marché × unité de temps), soit ${num(e.trades_mean, 1)} par paire en moyenne.`,
  ]
  if (e.win_rate_mean != null && e.expectancy_mean != null) {
    summary.push(
      `En moyenne ${pct(e.win_rate_mean, 0)} des trades sont gagnants et chaque trade ${e.expectancy_mean >= 0 ? 'rapporte' : 'coûte'} ${pct(Math.abs(e.expectancy_mean), 2)}, frais déduits.`,
    )
  }
  if (baseline && key !== 'ICHIMOKU_ONLY' && baseline.expectancy_mean != null && e.expectancy_mean != null) {
    const d = e.expectancy_mean - baseline.expectancy_mean
    summary.push(
      `Par rapport à Ichimoku seul (${pct(baseline.expectancy_mean, 2, true)} par trade), c’est ${d >= 0 ? 'mieux' : 'moins bien'} de ${pct(Math.abs(d), 2)} par trade, avec ${e.trades_total} trades au lieu de ${baseline.trades_total}.`,
    )
  }

  const history: ExplainHistoryRow[] = runs.map((r) => {
    const x = r.experiments[key]
    return {
      when: r.ended_at,
      trades: x ? String(x.trades_total) : '—',
      winRate: pct(x?.win_rate_mean),
      expectancy: pct(x?.expectancy_mean, 2, true),
      profitFactor: num(x?.profit_factor_median),
    }
  })

  const positiveRuns = runs.filter((r) => (r.experiments[key]?.expectancy_mean ?? 0) > 0).length
  let takeaway: string
  if (e.small_sample) {
    takeaway = `Trop peu de trades par paire (moins de ${minTrades} sur au moins une paire) : ce chiffre peut changer beaucoup d’un jour à l’autre. Ne pas en tirer de conclusion seul.`
  } else if (verdict.tone === 'green') {
    takeaway = `Résultat positif, frais compris.${runs.length > 1 ? ` Positif sur ${positiveRuns} des ${runs.length} derniers calculs : ` + (positiveRuns === runs.length ? 'c’est stable.' : 'à surveiller.') : ''}`
  } else if (verdict.tone === 'red') {
    takeaway = 'Après frais, cette variante perd de l’argent en moyenne. Elle ne doit pas servir à trader telle quelle.'
  } else {
    takeaway = 'Résultat ambigu : gain moyen faible ou instable. Regarder l’historique ci-dessous avant de conclure.'
  }

  return {
    title: name,
    subtitle: last ? `Backtest quotidien · ${plural(last.n_pairs, 'paire', 'paires')}` : 'Backtest quotidien',
    verdict,
    summary,
    stats: [
      { label: 'Trades', value: String(e.trades_total), hint: `${num(e.trades_mean, 1)} par paire en moyenne` },
      { label: 'Réussite', value: pct(e.win_rate_mean), hint: 'Moyenne des paires' },
      {
        label: 'Espérance / trade',
        value: pct(e.expectancy_mean, 2, true),
        hint: 'Gain moyen par trade, frais déduits',
        tone: tone(e.expectancy_mean),
      },
      { label: 'Profit factor', value: num(e.profit_factor_median), hint: 'Médiane des paires ; > 1 = gagnant' },
      { label: 'Sharpe', value: num(e.sharpe_mean), hint: 'Gain rapporté au risque ; > 1 = bon' },
      { label: 'Paires', value: String(e.n_pairs), hint: 'Marché × unité de temps testés' },
    ],
    method: [
      VARIANT_HOW[key] ?? 'Variante du backtest quotidien.',
      'Chaque jour, le moteur rejoue cette règle sur l’historique de chaque crypto suivie et chaque unité de temps, uniquement sur bougies clôturées.',
      'Les résultats de chaque paire sont ensuite moyennés (le profit factor prend la médiane, pour ne pas être faussé par une paire extrême).',
      `Une paire avec moins de ${minTrades} trades est signalée « échantillon faible ».`,
      lexicon(),
    ],
    takeaway,
    history,
  }
}

/* ----------------------------------------------------------------------------------------------
 * Ablations : une étape de l'échelle A → E
 * -------------------------------------------------------------------------------------------- */

export function explainAblationStep(
  step: AblationStepRow,
  prev: AblationStepRow | null,
  delta: AblationDelta | null,
  ctx: StudyContext,
): Explanation {
  const m = metricsOf(step.study)
  const pm = metricsOf(prev?.study)
  const rs = step.study?.ruleset
  const label = layerLabel(step.label)
  const n = m?.num_trades ?? 0
  const where = `${coin(ctx.symbol)} en ${tfWords(ctx.timeframe)}, sur les ${ctx.nBars} dernières bougies`

  const summary: string[] = []
  let verdict: Verdict
  let takeaway: string
  if (!prev || !delta) {
    verdict = { text: 'RÉFÉRENCE', tone: 'gray' }
    summary.push(
      `C’est le point de départ : la règle Ichimoku seule, sans aucun filtre. Sur ${where}, elle a donné ${plural(step.n_signals, 'signal', 'signaux')} et ${plural(n, 'trade', 'trades')}.`,
    )
    if (m?.expectancy != null) {
      summary.push(
        `${pct(m.win_rate, 0)} de trades gagnants, ${pct(m.expectancy, 2, true)} par trade en moyenne, frais déduits.`,
      )
    }
    takeaway =
      'Chaque étape suivante ajoute un filtre à cette base. Un filtre mérite sa place s’il améliore l’espérance ou le profit factor par rapport à l’étape d’avant.'
  } else {
    verdict = ablationVerdict(delta.improves_expectancy, delta.improves_profit_factor)
    const added = delta.added_conditions.map((k) => conditionText(k, rs?.conditions?.[k] ?? true))
    summary.push(
      `On reprend l’étape précédente et on exige en plus que ${added.join(' et ') || 'la nouvelle condition soit vraie'}.`,
    )
    summary.push(
      `Résultat sur ${where} : on passe de ${plural(prev.n_signals, 'signal', 'signaux')} à ${step.n_signals} et de ${pm?.num_trades ?? '—'} à ${n} trades.`,
    )
    if (pm?.expectancy != null && m?.expectancy != null) {
      summary.push(
        `L’espérance par trade passe de ${pct(pm.expectancy, 2, true)} à ${pct(m.expectancy, 2, true)}, le profit factor de ${num(pm.profit_factor)} à ${num(m.profit_factor)}.`,
      )
    } else if (n === 0) {
      summary.push('Avec ce filtre, plus aucun trade n’a été pris : il est trop restrictif sur cette période.')
    }
    if (verdict.tone === 'green') takeaway = 'Ce filtre améliore à la fois l’espérance et le profit factor : il mérite sa place.'
    else if (verdict.tone === 'amber') takeaway = 'Ce filtre améliore un des deux indicateurs mais dégrade l’autre : utile seulement si l’on accepte ce compromis.'
    else if (verdict.tone === 'red') takeaway = 'Ce filtre fait moins bien que l’étape précédente : sur ce marché et cette période, il retire surtout de bons trades.'
    else takeaway = 'Pas assez de trades pour comparer : il faut plus d’historique ou une unité de temps plus courte.'
  }
  const warn = sampleWarning(n)
  if (warn && verdict.tone !== 'gray') takeaway += ` ${warn}`

  return {
    title: label,
    subtitle: `${ctx.symbol} · ${ctx.timeframe} · ${ctx.nBars} bougies`,
    verdict,
    summary,
    stats: [
      { label: 'Signaux', value: String(step.n_signals), hint: 'Bougies où toutes les conditions deviennent vraies' },
      ...metricStats(m),
    ],
    method: [
      `Règle testée : on achète quand ${conditionList(rs)}.`,
      'Toutes les étapes A → E sont rejouées sur exactement les mêmes bougies ; seule la liste des conditions change. La différence vient donc uniquement du filtre ajouté.',
      ...tradeMechanics(rs, step.study),
      lexicon(),
    ],
    takeaway,
    trades: tradesOf(step.study),
  }
}

/* ----------------------------------------------------------------------------------------------
 * Régimes : la même règle, triée par état du marché
 * -------------------------------------------------------------------------------------------- */

const REGIME_HOW: Record<string, string> = {
  GLOBAL: 'Tous les signaux, sans tri : la référence pour comparer les autres lignes.',
  TRENDING: 'Le marché est en tendance quand l’ADX (force de tendance) indique une tendance installée ou forte.',
  RANGING: 'Le marché est sans tendance quand l’ADX est faible ou en train de se former.',
  HIGH_VOLATILITY: 'Forte volatilité : l’ATR (amplitude des bougies) est dans sa zone extrême par rapport à son historique.',
  NORMAL_VOLATILITY: 'Volatilité normale : l’ATR est dans sa zone habituelle.',
  LOW_VOLATILITY: 'Faible volatilité : l’ATR est dans sa zone basse (marché endormi).',
  BULL: 'Haussier : marché en tendance avec la force acheteuse (+DI) nettement au-dessus de la force vendeuse (−DI).',
  BEAR: 'Baissier : marché en tendance avec la force vendeuse (−DI) nettement au-dessus de la force acheteuse (+DI).',
  SIDEWAYS: 'Latéral : pas de tendance, ou acheteurs et vendeurs à égalité.',
}

export function explainRegime(slice: RegimeSliceRow, global: RegimeSliceRow | null, ctx: StudyContext): Explanation {
  const m = metricsOf(slice.study)
  const g = metricsOf(global?.study)
  const rs = slice.study?.ruleset
  const label = regimeLabel(slice.regime)
  const n = m?.num_trades ?? 0
  const isGlobal = slice.regime === 'GLOBAL'
  const share = ctx.nBars ? slice.n_bars_in_regime / ctx.nBars : null

  const summary: string[] = []
  if (isGlobal) {
    summary.push(
      `Sur ${coin(ctx.symbol)} en ${tfWords(ctx.timeframe)} (${ctx.nBars} bougies), la règle a donné ${plural(slice.n_signals, 'signal', 'signaux')} et ${plural(n, 'trade', 'trades')}, tous régimes confondus.`,
    )
  } else {
    summary.push(
      `Le marché était « ${label.toLowerCase()} » pendant ${slice.n_bars_in_regime} des ${ctx.nBars} bougies${share != null ? ` (${pct(share, 0)} du temps)` : ''}.`,
    )
    summary.push(
      `Pendant ces moments-là, la règle a donné ${plural(slice.n_signals, 'signal', 'signaux')} et ${plural(n, 'trade', 'trades')}.`,
    )
  }
  if (m?.expectancy != null) {
    summary.push(`${pct(m.win_rate, 0)} de trades gagnants, ${pct(m.expectancy, 2, true)} par trade en moyenne.`)
  }

  let verdict = performanceVerdict({ trades: n, expectancy: m?.expectancy ?? null, pf: m?.profit_factor ?? null })
  let takeaway: string
  if (isGlobal) {
    takeaway = 'Comparez chaque ligne à celle-ci : un régime nettement meilleur montre où la stratégie a vraiment un avantage.'
  } else if (!n) {
    takeaway = 'Aucun trade dans ce régime : la règle ne se déclenche presque jamais dans ces conditions.'
  } else if (g?.expectancy != null && m?.expectancy != null) {
    const better = m.expectancy > g.expectancy
    takeaway = better
      ? `Mieux que la moyenne (${pct(g.expectancy, 2, true)} par trade tous régimes confondus) : la stratégie est plus à l’aise dans ce régime.`
      : `Moins bien que la moyenne (${pct(g.expectancy, 2, true)} par trade tous régimes confondus) : ce régime tire le résultat vers le bas. Filtrer ces moments pourrait aider.`
    if (verdict.tone === 'green' && !better) verdict = { text: 'SOUS LA MOYENNE', tone: 'amber' }
  } else {
    takeaway = 'Pas assez de données pour comparer à la moyenne.'
  }
  const warn = sampleWarning(n)
  if (warn && n) takeaway += ` ${warn}`

  return {
    title: label,
    subtitle: `${ctx.symbol} · ${ctx.timeframe} · ${ctx.nBars} bougies`,
    verdict,
    summary,
    stats: [
      {
        label: 'Bougies dans ce régime',
        value: String(slice.n_bars_in_regime),
        hint: share != null ? `${pct(share, 0)} de la période` : 'Sur la période',
      },
      { label: 'Signaux', value: String(slice.n_signals), hint: 'Signaux tombés dans ce régime' },
      ...metricStats(m),
    ],
    method: [
      REGIME_HOW[slice.regime] ?? 'Régime calculé par le moteur à partir de l’ADX et de l’ATR.',
      'Le régime est calculé bougie par bougie avec seulement le passé (aucune information future). Chaque signal est rangé dans le régime du moment où il apparaît.',
      `Règle testée : on achète quand ${conditionList(rs)}.`,
      ...tradeMechanics(rs, slice.study),
      lexicon(),
    ],
    takeaway,
    trades: tradesOf(slice.study),
  }
}

/* ----------------------------------------------------------------------------------------------
 * Walk-forward : une période apprise puis testée
 * -------------------------------------------------------------------------------------------- */

export function foldVerdict(oos: BacktestMetrics | null): Verdict {
  if (!oos || oos.num_trades === 0) return { text: 'AUCUN TRADE', tone: 'gray' }
  return oos.profit_factor != null && oos.profit_factor > 1 ? { text: 'TIENT', tone: 'green' } : { text: 'NE TIENT PAS', tone: 'red' }
}

export function explainFold(fold: WalkForwardFoldRow, ctx: StudyContext, nFolds: number): Explanation {
  const is = metricsOf(fold.is)
  const oos = metricsOf(fold.oos)
  const rs = fold.oos?.ruleset ?? fold.is?.ruleset
  const verdict = foldVerdict(oos)
  const n = oos?.num_trades ?? 0
  const tf = tfWords(ctx.timeframe)

  const summary: string[] = [
    `Période ${fold.fold_index + 1} sur ${nFolds}. On regarde d’abord comment la règle s’est comportée sur ${fold.train_bars} ${tf} (bougies ${fold.train_start} à ${fold.train_end}) : c’est la partie « apprise ».`,
    `Puis on la fait tourner, sans rien changer, sur les ${fold.test_bars} bougies suivantes (${fold.test_start} à ${fold.test_end}) qu’elle n’a jamais vues : c’est la partie « testée ».`,
  ]
  if (is?.expectancy != null || oos?.expectancy != null) {
    summary.push(
      `Appris : ${is ? plural(is.num_trades, 'trade', 'trades') : '— trades'}, ${pct(is?.expectancy, 2, true)} par trade. Testé : ${plural(n, 'trade', 'trades')}, ${pct(oos?.expectancy, 2, true)} par trade.`,
    )
  }

  let takeaway: string
  if (verdict.tone === 'gray') {
    takeaway = 'Aucun trade dans la partie testée : cette période ne dit rien, ni en bien ni en mal.'
  } else if (verdict.tone === 'green') {
    takeaway = 'Sur des bougies jamais vues, la règle gagne plus qu’elle ne perd (profit factor > 1) : elle tient sur cette période.'
  } else {
    takeaway =
      'Sur des bougies jamais vues, la règle perd plus qu’elle ne gagne : ce qui marchait sur la partie apprise ne se répète pas ici.'
  }
  if (is?.expectancy != null && oos?.expectancy != null && is.expectancy > 0 && oos.expectancy < 0) {
    takeaway += ' Bon résultat appris, mauvais résultat testé : c’est le signe typique d’un résultat dû au hasard ou à la période.'
  }
  const warn = sampleWarning(n)
  if (warn && n) takeaway += ` ${warn}`

  return {
    title: `Période #${fold.fold_index + 1}`,
    subtitle: `${ctx.symbol} · ${ctx.timeframe} · appris ${fold.train_bars} → testé ${fold.test_bars} bougies`,
    verdict,
    summary,
    stats: [
      { label: 'Trades appris', value: is ? String(is.num_trades) : '—', hint: 'Sur la partie apprise' },
      {
        label: 'Espérance apprise',
        value: pct(is?.expectancy, 2, true),
        hint: 'Gain moyen par trade, partie apprise',
        tone: tone(is?.expectancy),
      },
      { label: 'Trades testés', value: String(n), hint: 'Sur des bougies jamais vues' },
      {
        label: 'Espérance testée',
        value: pct(oos?.expectancy, 2, true),
        hint: 'Gain moyen par trade, partie testée',
        tone: tone(oos?.expectancy),
      },
      { label: 'Profit factor testé', value: num(oos?.profit_factor), hint: '> 1 = la période tient' },
      { label: 'Drawdown testé', value: pct(oos?.max_drawdown), hint: 'Pire baisse sur la partie testée' },
    ],
    method: [
      'Le walk-forward découpe l’historique en fenêtres successives : une partie apprise, puis la partie juste après pour tester. La fenêtre avance ensuite et on recommence.',
      'La règle n’est pas ré-optimisée : on vérifie simplement qu’elle continue de marcher sur des données qu’elle n’a pas vues. C’est le meilleur garde-fou contre un résultat trop beau pour être vrai.',
      `Règle testée : on achète quand ${conditionList(rs)}.`,
      ...tradeMechanics(rs, fold.oos),
      'Verdict : « tient » si le profit factor de la partie testée est au-dessus de 1.',
    ],
    takeaway,
    trades: tradesOf(fold.oos),
  }
}
