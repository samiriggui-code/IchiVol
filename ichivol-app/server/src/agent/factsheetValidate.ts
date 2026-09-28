/**
 * AG-FS0 — validateur de sortie : aucune affirmation d'Eve sans fait moteur cité.
 * Spec : docs/AG-FS0-FACTSHEET-SPEC.md §3. Pur, sans I/O (testable).
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
/** Écart relatif toléré entre un nombre cité et la valeur du fait. */
export const REL_TOLERANCE = 0.005

/** Nombres qui ne sont pas des valeurs de marché : timeframes et périodes d'indicateurs. */
const TIMEFRAME_RE = /\b\d+\s?(?:m|min|h|d|j|w)\b/gi
/** Périodes usuelles : seul un entier de cette liste juste après le nom d'un indicateur est ignoré. */
const INDICATOR_PERIODS = new Set([5, 7, 9, 10, 12, 14, 20, 21, 26, 50, 52, 55, 100, 200])
const INDICATOR_PERIOD_RE =
  /\b(?:ATR|RSI|ADX|EMA|SMA|MA|Donchian|Kijun|Tenkan|Senkou|Ichimoku)\s?\(?\s?(\d{1,3}(?:\s?[,/]\s?\d{1,3})*)\s?\)?(?![\d.,]\d)/gi
const NUMBER_RE = /[-+−]?\d[\d   ]*(?:[.,]\d+)?/g

export interface ParsedNumber {
  raw: string
  value: number
  decimals: number
  percent: boolean
}

function normaliseNumber(raw: string): { value: number; decimals: number } | null {
  let s = raw.replace(/[   ]/g, '').replace('−', '-')
  if (s.includes(',') && s.includes('.')) {
    // le dernier séparateur est la décimale
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

/** Extrait les nombres d'un texte, hors timeframes et périodes d'indicateurs. */
export function extractNumbers(text: string): ParsedNumber[] {
  const masked = text
    .replace(INDICATOR_PERIOD_RE, (m, nums: string) =>
      nums.split(/\s?[,/]\s?/).every((x) => INDICATOR_PERIODS.has(Number(x))) ? ' ' : m,
    )
    .replace(TIMEFRAME_RE, ' ')
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

function roundTo(v: number, decimals: number): number {
  const f = 10 ** Math.min(decimals, 10)
  return Math.round(v * f) / f
}

function numberMatchesValue(n: ParsedNumber, v: number, ratioField = false): boolean {
  // Candidat brut, et « 93 % » / « 93e percentile » lu comme 0,93 (2 décimales de plus).
  const candidates: Array<[number, number]> = [[n.value, n.decimals]]
  if (n.percent || ratioField) candidates.push([n.value / 100, n.decimals + 2])
  return candidates.some(([x, dec]) => {
    if (x === v) return true
    if (roundTo(v, dec) === roundTo(x, dec)) return true
    return v !== 0 && Math.abs(x - v) / Math.abs(v) <= REL_TOLERANCE
  })
}

/** Jetons numériques d'un texte de fait (dates, heures) acceptés tels quels. */
function numericTokens(s: string): Set<string> {
  return new Set((s.match(/\d+/g) ?? []).map((t) => String(Number(t))))
}

function numberSupported(n: ParsedNumber, facts: Fact[], extraTokens: Set<string>): boolean {
  for (const f of facts) {
    const ratioField = /percentile|share|ratio/.test(f.field) && typeof f.value === 'number' && Math.abs(f.value) <= 1
    if (typeof f.value === 'number' && numberMatchesValue(n, f.value, ratioField)) return true
    if (f.display) {
      const d = normaliseNumber(f.display)
      if (d && /^[-+−]?\d/.test(f.display) && numberMatchesValue(n, d.value)) return true
      if (typeof f.value === 'string' && Number.isInteger(n.value) && numericTokens(f.display).has(String(Math.abs(n.value))))
        return true
    }
  }
  return Number.isInteger(n.value) && extraTokens.has(String(Math.abs(n.value)))
}

function checkClaim(
  claim: Claim,
  byId: Map<string, Fact>,
  extraTokens: Set<string>,
): string[] {
  const errors: string[] = []
  const ids = Array.isArray(claim.fact_ids) ? claim.fact_ids : []
  const cited: Fact[] = []
  for (const id of ids) {
    const f = byId.get(id)
    if (!f) errors.push(`fait inconnu: ${id}`)
    else cited.push(f)
  }
  if (claim.kind === 'fact' && ids.length === 0) errors.push('affirmation factuelle sans fait cité')
  if (claim.kind !== 'missing') {
    for (const f of cited) {
      if (f.status !== 'ok') errors.push(`fait indisponible cité comme donnée: ${f.id}`)
    }
  } else if (cited.some((f) => f.status === 'ok' && f.value !== null)) {
    errors.push('claim « missing » citant un fait disponible')
  }
  for (const n of extractNumbers(claim.text)) {
    if (!numberSupported(n, cited, extraTokens)) errors.push(`nombre non sourcé: ${n.raw}${n.percent ? ' %' : ''}`)
  }
  return errors
}

export function headerTokens(fs: FactSheet): Set<string> {
  const tokens = new Set<string>()
  if (fs.as_of) {
    const d = new Date(fs.as_of * 1000)
    for (const t of [d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate(), d.getUTCHours(), d.getUTCMinutes()])
      tokens.add(String(t))
  }
  for (const t of numericTokens(fs.symbol)) tokens.add(t)
  return tokens
}

/** Valide une sortie d'Eve contre le FactSheet. Le résumé ne cite pas d'ids : ses nombres doivent exister dans le FactSheet. */
export function validateAnalysis(fs: FactSheet, out: AnalysisOutput): ValidationReport {
  const byId = new Map(fs.facts.map((f) => [f.id, f]))
  const extra = headerTokens(fs)
  const verdicts: ClaimVerdict[] = []
  for (const section of ['claims', 'risks', 'invalidation'] as const) {
    for (const claim of out[section] ?? []) {
      const errors = checkClaim(claim, byId, extra)
      verdicts.push({ section, claim, ok: errors.length === 0, errors })
    }
  }
  const okFacts = fs.facts.filter((f) => f.status === 'ok')
  const summaryErrors = extractNumbers(out.summary ?? '')
    .filter((n) => !numberSupported(n, okFacts, extra))
    .map((n) => `nombre non sourcé: ${n.raw}`)
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
