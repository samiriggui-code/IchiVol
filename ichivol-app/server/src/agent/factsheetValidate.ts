/**
 * AG-FS0 — validateur de sortie : aucune affirmation d'Eve sans fait moteur cité.
 * Spec : docs/AG-FS0-FACTSHEET-SPEC.md §3. Pur, sans I/O (testable).
 *
 * FS-0b (revue #171) : règles strictes, sans tolérance relative.
 * - chaque nombre = `display` d'un fait CITÉ, à sa précision (au plus un cran d'arrondi, jamais sous 2 décimales
 *   si le display en a davantage) ;
 * - `%` seulement pour un fait ratio / percentile ; un nombre ≥ 1000 seulement pour un fait de prix ;
 * - dates et heures seulement si elles figurent telles quelles dans un fait cité ;
 * - résumé sans aucun chiffre ; nombres en toutes lettres interdits ; ≤ 4 faits par claim ;
 * - causalité sur la décision : citer `pipeline.blocking_stages` ; « prix entre X et Y » vérifié contre `price.live`.
 */

export type FactStatus = 'ok' | 'unavailable' | 'stale' | 'engine_absent'

export interface Fact {
  id: string
  engine: string
  field: string
  value: unknown
  display: string | null
  unit?: string | null
  timeframe: string
  as_of: number | null
  known_at: number | null
  source: string
  status: FactStatus | string
  validation_status: string
  decision_role: string
  reason?: string
}

export interface FactSheet {
  schema: string
  factsheet_id: string
  symbol: string
  timeframe: string
  as_of: number | null
  facts: Fact[]
  missing: Array<{ id: string; reason?: string | null }>
}

export type ClaimKind = 'fact' | 'interpretation' | 'scenario' | 'missing'

export interface Claim {
  text: string
  kind: ClaimKind
  fact_ids: string[]
}

export interface AnalysisOutput {
  summary: string
  claims: Claim[]
  risks: Claim[]
  invalidation: Claim[]
  missing_data: string[]
}

export interface ClaimVerdict {
  section: 'claims' | 'risks' | 'invalidation'
  claim: Claim
  ok: boolean
  errors: string[]
}

export interface ValidationReport {
  factsheet_id: string
  total: number
  accepted: number
  rejected: number
  rejectedShare: number
  summaryOk: boolean
  summaryErrors: string[]
  verdicts: ClaimVerdict[]
}

/** Retry une seule fois au-delà de cette part de claims rejetés (spec §3). */
export const RETRY_REJECTED_SHARE = 0.3
/** Nombre maximal de faits cités par un claim (V6). */
export const MAX_FACTS_PER_CLAIM = 4

/** Timeframes usuels, sensibles à la casse (V4 : « 850 M » n'est pas un timeframe). */
const TIMEFRAME_RE = /\b(?:1|3|5|15|30)m\b|\b(?:1|2|4|6|8|12)h\b|\b1[dw]\b/g
/** Noms de programmes et d'étapes du protocole (VP3, AG-S1, RS-D1, B7…) : pas des valeurs de marché. */
const PROGRAM_NAME_RE = /\b(?:VP|AG-S|RS-[A-Z]|OF-|B|T)\d{1,2}[a-z]?\b/g
/**
 * Périodes d'indicateurs (V4) : jamais RSI / ADX (leur valeur tombe dans la même plage).
 * Forme parenthésée toujours ; forme « NOM 14 » seulement si elle n'est pas suivie de « = », « : », « à » ou d'un nombre.
 */
const PERIOD_NAMES = 'ATR|EMA|SMA|MA|Donchian|Kijun|Tenkan|Senkou|Ichimoku'
const INDICATOR_PERIODS = new Set([5, 7, 9, 10, 12, 14, 20, 21, 26, 50, 52, 55, 100, 200])
const PERIOD_PAREN_RE = new RegExp(`\\b(?:${PERIOD_NAMES})\\s?\\((\\d{1,3}(?:\\s?[,/]\\s?\\d{1,3})*)\\)`, 'g')
const PERIOD_BARE_RE = new RegExp(
  `\\b(?:${PERIOD_NAMES})\\s(\\d{1,3}(?:/\\d{1,3})*)(?!\\s*(?:[=:]|à\\b|\\d)|[.,]\\d)`,
  'g',
)
/** Dates et heures (V1) : acceptées seulement si elles figurent dans un fait cité. */
const DATETIME_RE = /\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[:h]\d{2}\b|\b\d{1,2}\/\d{1,2}(?:\/\d{2,4})?\b/g
const NUMBER_RE = /[-+−]?\d[\d   ]*(?:[.,]\d+)?/g
/**
 * Bornes de mot Unicode : `\b` est ASCII en JS, il ne voit ni « moitié » ni « dû à » ni « à cause »
 * (FS-0c, revue de 0692694).
 */
const WB_START = '(?<![\\p{L}\\p{N}_])'
const WB_END = '(?![\\p{L}\\p{N}_])'
/** Nombres en toutes lettres (V7). « un / une / one » exclus (articles). */
const NUMBER_WORDS_RE = new RegExp(
  `${WB_START}(?:deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|treize|quatorze|quinze|seize|vingt|trente|quarante|cinquante|soixante|cent|cents|mille|millions?|milliards?|moitié|doubler?|doublement|tripler?|quadrupler?|pour\\s?cent|two|three|four|five|ten|twenty|hundred|thousand|million|billion|half|twice|double|triple|percent)${WB_END}`,
  'iu',
)
/** Connecteurs causaux (V8). */
const CAUSAL_RE = new RegExp(
  `${WB_START}(?:parce que|parce qu|car|dû à|due à|dus à|dues à|dû au|due au|dus aux|dues aux|à cause|en raison|puisque|because|due to)${WB_END}`,
  'iu',
)
/**
 * Timeframes (V1/V4, FS-0c) : « 12h » peut être une heure inventée, « 30m » trente millions.
 * Un tel jeton n'est masqué que s'il est le timeframe du FactSheet ou celui / le display d'un fait cité ;
 * sinon il est rejeté (jamais ignoré).
 */
const TF_CANDIDATE_RE = /(?<![\p{L}\p{N}_,.])(\d{1,3})\s?(min|m|h|d|j|w|M|H|D|W)(?![\p{L}\p{N}_])/gu
/** Chiffres hors ASCII (pleine chasse, exposants, autres écritures) : jamais contrôlables, donc interdits. */
const NON_ASCII_DIGIT_RE = /(?![0-9])[\p{Nd}\p{No}]/u
/** Unités autres que « % » (points de base, points, milliers, milliards, devises) : interdites. */
const UNIT_RE = new RegExp(`\\d\\s?(?:pbs?|bps?|pts?|points?|pips?|‰|k|K|Mds?|Md|bn|\\$|€|USD|USDT|EUR)${WB_END}|[$€]\\s?\\d`, 'u')
/** Multiplicateur « 1,5x » : permis seulement pour un ratio de volume cité (rvol.rvol). */
const MULTIPLIER_RE = new RegExp(`\\d\\s?[xX×]${WB_END}`, 'u')

function tfKey(n: string, unit: string): string {
  // « M » reste distinct de « m » (millions ≠ minutes) ; H / D / W = h / d / w.
  const u = unit === 'min' ? 'm' : unit === 'j' ? 'd' : unit === 'M' ? 'M' : unit.toLowerCase()
  return `${Number(n)}${u}`
}

/** Jetons de timeframe autorisés, lus dans des chaînes (timeframe du FactSheet, timeframes / displays cités). */
export function timeframeSet(values: Array<string | null | undefined>): Set<string> {
  const out = new Set<string>()
  for (const v of values) {
    if (!v) continue
    for (const m of v.matchAll(TF_CANDIDATE_RE)) out.add(tfKey(m[1], m[2]))
  }
  return out
}

/** Masque les timeframes autorisés ; renvoie les autres (heure inventée, « 30m », « 850 M »…). */
export function maskTimeframes(text: string, allowed: Set<string>): { text: string; rejected: string[] } {
  const rejected: string[] = []
  const masked = text.replace(TF_CANDIDATE_RE, (m, n: string, u: string) => {
    if (!allowed.has(tfKey(n, u))) rejected.push(m.trim())
    return ' '
  })
  return { text: masked, rejected }
}

function formErrors(text: string): string[] {
  const errors: string[] = []
  if (NON_ASCII_DIGIT_RE.test(text)) errors.push('chiffres non ASCII interdits')
  return errors
}
const PRICE_FIELD_RE = /price|poc|vah|val|vwap|avwap|swing|upper|lower|entry|stop|take_profit|level/
const RATIO_FIELD_RE = /percentile|share|ratio/

export interface ParsedNumber {
  raw: string
  value: number
  decimals: number
  percent: boolean
}

function normaliseNumber(raw: string): { value: number; decimals: number } | null {
  let s = raw.replace(/[   ]/g, '').replace('−', '-')
  if (s.includes(',') && s.includes('.')) {
    if (s.lastIndexOf(',') > s.lastIndexOf('.')) s = s.replace(/\./g, '').replace(',', '.')
    else s = s.replace(/,/g, '')
  } else {
    s = s.replace(',', '.')
  }
  const value = Number(s)
  if (!Number.isFinite(value)) return null
  const dot = s.indexOf('.')
  return { value, decimals: dot >= 0 ? s.length - dot - 1 : 0 }
}

function maskPeriods(text: string): string {
  const keepIfPeriods = (m: string, nums: string) =>
    nums.split(/\s?[,/]\s?/).every((x) => INDICATOR_PERIODS.has(Number(x))) ? ' ' : m
  return text.replace(PERIOD_PAREN_RE, keepIfPeriods).replace(PERIOD_BARE_RE, keepIfPeriods)
}

/** Nombres d'un texte, hors timeframes, noms de programme, périodes et dates/heures (traitées à part). */
export function extractNumbers(text: string): ParsedNumber[] {
  const masked = maskPeriods(text)
    .replace(TIMEFRAME_RE, ' ')
    .replace(PROGRAM_NAME_RE, ' ')
    .replace(DATETIME_RE, ' ')
  const out: ParsedNumber[] = []
  for (const m of masked.matchAll(NUMBER_RE)) {
    const raw = m[0].trim()
    if (!/\d/.test(raw)) continue
    const n = normaliseNumber(raw)
    if (!n) continue
    const after = masked.slice((m.index ?? 0) + m[0].length).trimStart()
    out.push({ raw, ...n, percent: after.startsWith('%') })
  }
  return out
}

export function extractDateTimes(text: string): string[] {
  return [...maskPeriods(text).matchAll(DATETIME_RE)].map((m) => m[0])
}

function roundTo(v: number, decimals: number): number {
  const f = 10 ** Math.min(decimals, 10)
  return Math.round(v * f) / f
}

function displayDecimals(f: Fact): number {
  const d = f.display ? normaliseNumber(f.display) : null
  return d ? d.decimals : 0
}

/** V3/V5 : précision au moins celle du display (un cran d'arrondi, jamais sous 2 décimales), aucune bande relative. */
function numberMatchesFact(n: ParsedNumber, f: Fact): boolean {
  if (typeof f.value !== 'number') return false
  const v = f.value
  const dispDec = displayDecimals(f)
  const required = Math.min(dispDec, 2)
  const ratio = RATIO_FIELD_RE.test(f.field) || RATIO_FIELD_RE.test(f.id) || f.unit === '%'
  // V6 : « % » seulement pour un ratio / percentile ; un nombre ≥ 1000 seulement pour un champ de prix.
  if (n.percent && !ratio) return false
  if (Math.abs(n.value) >= 1000 && !PRICE_FIELD_RE.test(f.field) && !PRICE_FIELD_RE.test(f.id)) return false
  const candidates: Array<[number, number]> = []
  if (!n.percent) candidates.push([n.value, n.decimals])
  if (ratio && Math.abs(v) <= 1) candidates.push([n.value / 100, n.decimals + 2])
  return candidates.some(([x, dec]) => dec >= required && roundTo(v, dec) === roundTo(x, dec))
}

function priceLive(fs: FactSheet): number | null {
  const f = fs.facts.find((x) => x.id === 'price.live' && x.status === 'ok')
  return f && typeof f.value === 'number' ? f.value : null
}

/** V8 : « (le prix) entre X et Y » doit encadrer price.live. */
/** Désignations du prix courant (N6) : « prix », « cours », « BTC »… */
const PRICE_SUBJECT_RE = new RegExp(
  `${WB_START}(?:prix|cours|price|spot|marché|BTC|ETH|SOL|BTCUSDT|ETHUSDT|SOLUSDT|bitcoin|ether|solana)${WB_END}`,
  'iu',
)
const ABOVE_RE = new RegExp(`${WB_START}(?:au[- ]dessus|above|supérieur|plus haut que)${WB_END}([^.;]{0,40})`, 'iu')
const BELOW_RE = new RegExp(
  `${WB_START}(?:en[- ]dessous|au[- ]dessous|sous|below|inférieur|plus bas que)${WB_END}([^.;]{0,40})`,
  'iu',
)
const BETWEEN_RE = new RegExp(`${WB_START}entre${WB_END}([^.;]*?)${WB_START}et${WB_END}([^.;]*)`, 'iu')
/** Décision nommée dans le texte (N5) : la causalité exige alors pipeline.blocking_stages. */
const DECISION_TOKEN_RE = /\b(?:NO_TRADE|STRONG_BUY|STRONG_SELL|BUY|SELL|WATCH)\b/

/** V8 / N6 / N10 : relations entre le prix courant et un niveau cité, vérifiées contre price.live. */
function priceRelationErrors(text: string, fs: FactSheet): string[] {
  if (!PRICE_SUBJECT_RE.test(text)) return []
  const p = priceLive(fs)
  if (p === null) return []
  const errors: string[] = []
  const between = BETWEEN_RE.exec(text)
  if (between) {
    const a = extractNumbers(between[1])[0]
    const b = extractNumbers(between[2])[0]
    if (a && b && !(p >= Math.min(a.value, b.value) && p <= Math.max(a.value, b.value))) {
      errors.push(`relation fausse : le prix (${p}) n'est pas entre ${a.raw} et ${b.raw}`)
    }
  }
  const above = ABOVE_RE.exec(text)
  const aboveLevel = above ? extractNumbers(above[1])[0] : undefined
  if (aboveLevel && !(p > aboveLevel.value)) errors.push(`relation fausse : le prix (${p}) n'est pas au-dessus de ${aboveLevel.raw}`)
  const below = BELOW_RE.exec(text)
  const belowLevel = below ? extractNumbers(below[1])[0] : undefined
  if (belowLevel && !(p < belowLevel.value)) errors.push(`relation fausse : le prix (${p}) n'est pas en dessous de ${belowLevel.raw}`)
  return errors
}

function checkClaim(claim: Claim, fs: FactSheet, byId: Map<string, Fact>): string[] {
  const errors: string[] = []
  const ids = Array.isArray(claim.fact_ids) ? claim.fact_ids : []
  if (ids.length > MAX_FACTS_PER_CLAIM) errors.push(`trop de faits cités (${ids.length} > ${MAX_FACTS_PER_CLAIM})`)
  const cited: Fact[] = []
  for (const id of ids) {
    const f = byId.get(id)
    if (!f) errors.push(`fait inconnu: ${id}`)
    else cited.push(f)
  }
  if (claim.kind === 'fact' && ids.length === 0) errors.push('affirmation factuelle sans fait cité')
  if (claim.kind !== 'missing') {
    for (const f of cited) if (f.status !== 'ok') errors.push(`fait indisponible cité comme donnée: ${f.id}`)
  } else if (cited.some((f) => f.status === 'ok' && f.value !== null)) {
    errors.push('claim « missing » citant un fait disponible')
  }
  const okCited = cited.filter((f) => f.status === 'ok')
  errors.push(...formErrors(claim.text))
  // Timeframe masqué seulement s'il vaut fs.timeframe ou le display d'un fait cité (ex. mtf_direction.higher_tf).
  const tf = maskTimeframes(claim.text, timeframeSet([fs.timeframe, ...okCited.map((f) => f.display)]))
  for (const t of tf.rejected) errors.push(`timeframe, heure ou unité non sourcé: ${t}`)
  const unitText = maskPeriods(tf.text)
  if (UNIT_RE.test(unitText)) errors.push('unité non autorisée (seuls « % » et « x » pour rvol.rvol)')
  if (MULTIPLIER_RE.test(unitText) && !ids.includes('rvol.rvol')) errors.push('multiplicateur « x » sans rvol.rvol cité')
  for (const n of extractNumbers(tf.text)) {
    if (!okCited.some((f) => numberMatchesFact(n, f))) errors.push(`nombre non sourcé: ${n.raw}${n.percent ? ' %' : ''}`)
  }
  const citedDisplays = okCited.map((f) => f.display ?? '').join(' | ')
  for (const dt of extractDateTimes(claim.text)) {
    if (!citedDisplays.includes(dt)) errors.push(`date/heure non sourcée: ${dt}`)
  }
  if (claim.kind !== 'missing' && NUMBER_WORDS_RE.test(claim.text)) errors.push('nombre en toutes lettres interdit')
  const namesDecision = ids.includes('pipeline.decision') || DECISION_TOKEN_RE.test(claim.text)
  if (CAUSAL_RE.test(claim.text) && namesDecision && !ids.includes('pipeline.blocking_stages')) {
    errors.push('causalité sur la décision sans citer pipeline.blocking_stages')
  }
  errors.push(...priceRelationErrors(claim.text, fs))
  return errors
}

/** Valide une sortie d'Eve contre le FactSheet. Le résumé ne cite pas de faits : il ne contient donc aucun nombre. */
export function validateAnalysis(fs: FactSheet, out: AnalysisOutput): ValidationReport {
  const byId = new Map(fs.facts.map((f) => [f.id, f]))
  const verdicts: ClaimVerdict[] = []
  for (const section of ['claims', 'risks', 'invalidation'] as const) {
    for (const claim of out[section] ?? []) {
      const errors = checkClaim(claim, fs, byId)
      verdicts.push({ section, claim, ok: errors.length === 0, errors })
    }
  }
  const summary = out.summary ?? ''
  const summaryErrors: string[] = formErrors(summary).map((e) => `résumé : ${e}`)
  const okFacts = fs.facts.filter((f) => f.status === 'ok')
  // Le résumé ne cite pas : seuls fs.timeframe et les displays-timeframes du FactSheet (ex. « 4h ») sont masqués.
  const summaryTf = maskTimeframes(summary, timeframeSet([fs.timeframe, ...okFacts.map((f) => f.display)]))
  for (const t of summaryTf.rejected) summaryErrors.push(`résumé : timeframe, heure ou unité non sourcé: ${t}`)
  if (/\d/.test(maskPeriods(summaryTf.text).replace(PROGRAM_NAME_RE, ' '))) {
    summaryErrors.push('résumé : aucun chiffre autorisé (les chiffres vont dans les claims, avec leurs faits)')
  }
  if (NUMBER_WORDS_RE.test(summary)) summaryErrors.push('résumé : nombre en toutes lettres interdit')
  if (CAUSAL_RE.test(summary) && /NO_TRADE|BUY|SELL|WATCH/.test(summary)) {
    summaryErrors.push('résumé : causalité sur la décision interdite (à mettre dans un claim citant pipeline.blocking_stages)')
  }
  const total = verdicts.length
  const rejected = verdicts.filter((v) => !v.ok).length
  return {
    factsheet_id: fs.factsheet_id,
    total,
    accepted: total - rejected,
    rejected,
    rejectedShare: total ? rejected / total : 0,
    summaryOk: summaryErrors.length === 0,
    summaryErrors,
    verdicts,
  }
}

export function needsRetry(report: ValidationReport): boolean {
  return report.total === 0 || report.rejectedShare > RETRY_REJECTED_SHARE || !report.summaryOk
}
