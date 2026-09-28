/**
 * AG-FS0 — Eve répond à partir du FactSheet moteur, en UN appel LLM à sortie forcée,
 * puis le validateur retire toute affirmation non sourcée (docs/AG-FS0-FACTSHEET-SPEC.md).
 *
 * Adaptateur minimal : Anthropic (tool_use forcé) ou OpenAI-compatible (OpenRouter / OpenAI,
 * function calling forcé). Le FactSheet et le schéma de sortie appartiennent à IchiVol.
 */
import { engineAgentCommand } from './engineAgentChannel.js'
import {
  type AnalysisOutput,
  type Claim,
  type Fact,
  type FactSheet,
  type ValidationReport,
  needsRetry,
  validateAnalysis,
} from './factsheetValidate.js'
import { loadSkills } from './skills/loadSkills.js'
import type { AgentMode } from './types.js'

export const FACTSHEET_PROMPT_VERSION = 'fs0-v1'
const MAX_TOKENS = 1200
const TIMEOUT_MS = 60_000
const FS_SKILLS = ['ichimoku', 'rvol', 'structure', 'mtf', 'risk']

const CLAIM_SCHEMA = {
  type: 'object',
  properties: {
    text: { type: 'string' },
    kind: { type: 'string', enum: ['fact', 'interpretation', 'scenario', 'missing'] },
    fact_ids: { type: 'array', items: { type: 'string' } },
  },
  required: ['text', 'kind', 'fact_ids'],
} as const

export const SUBMIT_ANALYSIS_TOOL = {
  name: 'submit_analysis',
  description:
    "Rend l'analyse d'Eve. Chaque affirmation cite les ids des faits du FACTSHEET qui la fondent.",
  input_schema: {
    type: 'object',
    properties: {
      summary: { type: 'string', description: '2 à 4 lignes, sans chiffre absent du FACTSHEET.' },
      claims: { type: 'array', items: CLAIM_SCHEMA },
      risks: { type: 'array', items: CLAIM_SCHEMA },
      invalidation: { type: 'array', items: CLAIM_SCHEMA },
      missing_data: { type: 'array', items: { type: 'string' } },
    },
    required: ['summary', 'claims', 'risks', 'invalidation', 'missing_data'],
  },
} as const

const MODE_FOCUS: Partial<Record<AgentMode, string>> = {
  explain_decision:
    'Explique le verdict DÉJÀ rendu par le pipeline (pipeline.decision et ses étapes) : ce qui le porte, ce qui le freine. Tu ne votes pas et tu ne proposes aucun trade.',
  explain_signal:
    "Explique le signal courant (Ichimoku, participation, structure, location, régime) tel que les faits le montrent. Tu ne proposes aucun trade.",
}

export function buildFactsheetSystem(mode: AgentMode): string {
  const skills = loadSkills(FS_SKILLS).block ?? ''
  return [
    "Tu es Eve, l'analyste d'IchiVol. Tu expliques des faits calculés par les moteurs Python. Tu ne calcules rien et tu n'inventes rien.",
    MODE_FOCUS[mode] ?? MODE_FOCUS.explain_signal,
    'RÈGLES STRICTES :',
    '1. Tu réponds UNIQUEMENT via l’outil submit_analysis.',
    '2. Chaque chiffre que tu écris doit être la valeur « display » d’un fait que tu cites dans fact_ids, recopiée telle quelle. Aucun calcul, aucune différence, aucun pourcentage dérivé, aucun comptage.',
    '3. kind=fact exige au moins un fact_id. kind=interpretation ou scenario : relie des faits cités, sans nouveau chiffre.',
    '4. Un fait avec status différent de ok est une ABSENCE : dis-le avec kind=missing (et liste son id dans missing_data). Ne le déduis jamais.',
    '5. Tous les signaux du pipeline sont NON_VALIDE (programme VP3 : aucun edge mesuré). Rappelle-le quand tu cites pipeline.decision.',
    '6. Français clair, vocabulaire trading juste, 4 à 8 claims au total.',
    skills ? `MÉTHODE (skills, sans chiffres de marché) :\n${skills}` : '',
  ]
    .filter(Boolean)
    .join('\n')
}

/** Projection compacte envoyée au LLM (les champs de provenance restent côté serveur). */
export function compactFacts(fs: FactSheet): string {
  const lines = fs.facts.map((f) => {
    const st = f.status === 'ok' ? '' : ` [${f.status}${f.reason ? `: ${f.reason}` : ''}]`
    const val = f.status === 'ok' ? (f.display ?? 'aucun') : '—'
    return `${f.id} = ${val}${f.unit ? ` ${f.unit}` : ''} · ${f.timeframe} · ${f.validation_status}${st}`
  })
  const asOf = fs.as_of ? new Date(fs.as_of * 1000).toISOString().slice(0, 16).replace('T', ' ') + ' UTC' : '—'
  return [`FACTSHEET ${fs.symbol} ${fs.timeframe} · barre close ${asOf} · id ${fs.factsheet_id.slice(0, 12)}`, ...lines].join(
    '\n',
  )
}

export type LlmProviderName = 'anthropic' | 'openai' | 'openrouter'

export interface ForcedToolCall {
  provider: LlmProviderName
  apiKey: string
  model: string
  system: string
  user: string
  fetchImpl?: typeof fetch
  signal?: AbortSignal
}

export interface ForcedToolResult {
  input: unknown
  model: string
  usage: { input_tokens: number; output_tokens: number; cache_read_input_tokens?: number }
}

const OPENAI_BASE: Record<Exclude<LlmProviderName, 'anthropic'>, string> = {
  openai: 'https://api.openai.com/v1',
  openrouter: 'https://openrouter.ai/api/v1',
}

/** Appel unique, sortie forcée par l'outil submit_analysis. */
export async function callForcedTool(opts: ForcedToolCall): Promise<ForcedToolResult> {
  const doFetch = opts.fetchImpl ?? fetch
  const signal = opts.signal ?? AbortSignal.timeout(TIMEOUT_MS)
  if (opts.provider === 'anthropic') {
    const res = await doFetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-api-key': opts.apiKey, 'anthropic-version': '2023-06-01' },
      body: JSON.stringify({
        model: opts.model,
        max_tokens: MAX_TOKENS,
        system: [{ type: 'text', text: opts.system, cache_control: { type: 'ephemeral' } }],
        tools: [SUBMIT_ANALYSIS_TOOL],
        tool_choice: { type: 'tool', name: SUBMIT_ANALYSIS_TOOL.name },
        messages: [{ role: 'user', content: opts.user }],
      }),
      signal,
    })
    if (!res.ok) throw new Error(`Anthropic ${res.status}: ${await res.text()}`)
    const data = (await res.json()) as {
      model: string
      content: Array<{ type: string; name?: string; input?: unknown }>
      usage?: ForcedToolResult['usage']
    }
    const block = data.content.find((b) => b.type === 'tool_use' && b.name === SUBMIT_ANALYSIS_TOOL.name)
    return { input: block?.input ?? null, model: data.model, usage: data.usage ?? { input_tokens: 0, output_tokens: 0 } }
  }
  const res = await doFetch(`${OPENAI_BASE[opts.provider]}/chat/completions`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      authorization: `Bearer ${opts.apiKey}`,
      ...(opts.provider === 'openrouter' ? { 'X-Title': 'IchiVol' } : {}),
    },
    body: JSON.stringify({
      model: opts.model,
      max_tokens: MAX_TOKENS,
      messages: [
        { role: 'system', content: opts.system },
        { role: 'user', content: opts.user },
      ],
      tools: [
        {
          type: 'function',
          function: {
            name: SUBMIT_ANALYSIS_TOOL.name,
            description: SUBMIT_ANALYSIS_TOOL.description,
            parameters: SUBMIT_ANALYSIS_TOOL.input_schema,
          },
        },
      ],
      tool_choice: { type: 'function', function: { name: SUBMIT_ANALYSIS_TOOL.name } },
    }),
    signal,
  })
  if (!res.ok) throw new Error(`${opts.provider} ${res.status}: ${await res.text()}`)
  const data = (await res.json()) as {
    model: string
    choices: Array<{ message: { tool_calls?: Array<{ function: { name: string; arguments: string } }> } }>
    usage?: { prompt_tokens?: number; completion_tokens?: number }
  }
  const call = data.choices[0]?.message?.tool_calls?.find((c) => c.function.name === SUBMIT_ANALYSIS_TOOL.name)
  let input: unknown = null
  try {
    input = call ? JSON.parse(call.function.arguments) : null
  } catch {
    input = null
  }
  return {
    input,
    model: data.model,
    usage: { input_tokens: data.usage?.prompt_tokens ?? 0, output_tokens: data.usage?.completion_tokens ?? 0 },
  }
}

function asClaims(v: unknown): Claim[] {
  if (!Array.isArray(v)) return []
  return v
    .filter((c): c is Record<string, unknown> => !!c && typeof c === 'object')
    .map((c) => ({
      text: typeof c.text === 'string' ? c.text : '',
      kind: (['fact', 'interpretation', 'scenario', 'missing'].includes(String(c.kind)) ? c.kind : 'interpretation') as Claim['kind'],
      fact_ids: Array.isArray(c.fact_ids) ? c.fact_ids.map(String) : [],
    }))
    .filter((c) => c.text.trim().length > 0)
}

export function parseAnalysis(input: unknown): AnalysisOutput | null {
  if (!input || typeof input !== 'object') return null
  const o = input as Record<string, unknown>
  return {
    summary: typeof o.summary === 'string' ? o.summary : '',
    claims: asClaims(o.claims),
    risks: asClaims(o.risks),
    invalidation: asClaims(o.invalidation),
    missing_data: Array.isArray(o.missing_data) ? o.missing_data.map(String) : [],
  }
}

export interface FactChip {
  id: string
  display: string | null
  engine: string
  timeframe: string
  as_of: number | null
  known_at: number | null
  status: string
  validation_status: string
  source: string
}

export interface FactsheetClaimView {
  section: 'claims' | 'risks' | 'invalidation'
  text: string
  kind: Claim['kind']
  facts: FactChip[]
}

export interface FactsheetAnswer {
  answer: string
  factsheet: {
    id: string
    schema: string
    symbol: string
    timeframe: string
    as_of: number | null
    summary: string | null
    claims: FactsheetClaimView[]
    removed: number
    partial: boolean
    fallback: boolean
    missing: string[]
  }
  model: string
  attempts: number
  usage: { input_tokens: number; output_tokens: number }
  reports: ValidationReport[]
  promptVersion: string
}

function chip(f: Fact): FactChip {
  return {
    id: f.id,
    display: f.display,
    engine: f.engine,
    timeframe: f.timeframe,
    as_of: f.as_of,
    known_at: f.known_at,
    status: f.status,
    validation_status: f.validation_status,
    source: f.source,
  }
}

/** Rendu texte (compat. clients existants) + vue structurée. Seuls les claims validés sont gardés. */
export function renderAnswer(fs: FactSheet, out: AnalysisOutput | null, report: ValidationReport | null): FactsheetAnswer['factsheet'] & { text: string } {
  const byId = new Map(fs.facts.map((f) => [f.id, f]))
  const kept = (report?.verdicts ?? []).filter((v) => v.ok)
  const claims: FactsheetClaimView[] = kept.map((v) => ({
    section: v.section,
    text: v.claim.text,
    kind: v.claim.kind,
    facts: v.claim.fact_ids.map((id) => byId.get(id)).filter((f): f is Fact => !!f).map(chip),
  }))
  const summary = out && report?.summaryOk ? out.summary.trim() || null : null
  const removed = report ? report.rejected + (report.summaryOk ? 0 : 1) : 0
  const fallback = claims.length === 0
  const missing = fs.facts.filter((f) => f.status !== 'ok').map((f) => f.id)
  const lines: string[] = []
  if (fallback) {
    lines.push("Je n'ai pas pu formuler d'analyse vérifiable. Voici les faits moteur bruts :")
    for (const f of fs.facts.filter((x) => x.status === 'ok').slice(0, 20)) lines.push(`- ${f.id} : ${f.display ?? 'aucun'}`)
  } else {
    if (summary) lines.push(summary, '')
    const titles = { claims: 'Lecture', risks: 'Risques', invalidation: 'Invalidation' } as const
    for (const section of ['claims', 'risks', 'invalidation'] as const) {
      const items = claims.filter((c) => c.section === section)
      if (!items.length) continue
      lines.push(`**${titles[section]}**`)
      for (const c of items) lines.push(`- ${c.text}`)
      lines.push('')
    }
  }
  if (removed > 0) lines.push(`_Réponse partielle : ${removed} affirmation(s) non vérifiable(s) retirée(s)._`)
  if (missing.length) lines.push(`_Données indisponibles : ${missing.join(', ')}._`)
  return {
    text: lines.join('\n').trim(),
    id: fs.factsheet_id,
    schema: fs.schema,
    symbol: fs.symbol,
    timeframe: fs.timeframe,
    as_of: fs.as_of,
    summary,
    claims,
    removed,
    partial: removed > 0,
    fallback,
    missing,
  }
}

export async function fetchFactsheet(symbol: string, timeframe: string): Promise<FactSheet> {
  const res = await engineAgentCommand({ cmd: 'get_factsheet', args: { symbol, timeframe } })
  if (!res.ok) throw new Error(`FactSheet indisponible (${res.error})`)
  const fs = res.data as FactSheet
  if (!fs || !Array.isArray(fs.facts)) throw new Error('FactSheet invalide')
  return fs
}

export interface RunFactsheetInput {
  provider: LlmProviderName
  apiKey: string
  model: string
  mode: AgentMode
  question: string
  factsheet: FactSheet
  fetchImpl?: typeof fetch
  signal?: AbortSignal
}

/** 1 appel, validation, au plus 1 nouvel essai avec la liste des erreurs (spec §3). */
export async function runFactsheetAgent(input: RunFactsheetInput): Promise<FactsheetAnswer> {
  const system = buildFactsheetSystem(input.mode)
  const base = `${compactFacts(input.factsheet)}\n\nQUESTION : ${input.question}`
  const reports: ValidationReport[] = []
  const usage = { input_tokens: 0, output_tokens: 0 }
  let model = input.model
  let best: { out: AnalysisOutput | null; report: ValidationReport | null } = { out: null, report: null }
  let user = base
  let attempts = 0
  for (attempts = 1; attempts <= 2; attempts++) {
    const res = await callForcedTool({ ...input, system, user })
    model = res.model
    usage.input_tokens += res.usage.input_tokens
    usage.output_tokens += res.usage.output_tokens
    const out = parseAnalysis(res.input)
    const report = out ? validateAnalysis(input.factsheet, out) : null
    if (report) reports.push(report)
    if (!best.report || (report && report.accepted > best.report.accepted)) best = { out, report }
    if (report && !needsRetry(report)) break
    if (attempts === 2) break
    const errors = (report?.verdicts ?? [])
      .filter((v) => !v.ok)
      .map((v) => `- « ${v.claim.text.slice(0, 80)} » : ${v.errors.join(' ; ')}`)
      .concat(report?.summaryErrors.map((e) => `- résumé : ${e}`) ?? [])
    user = `${base}\n\nTA RÉPONSE PRÉCÉDENTE A ÉTÉ REJETÉE PAR LE VALIDATEUR :\n${errors.join('\n') || '- sortie absente ou illisible'}\nRecommence en respectant strictement les règles (chiffres = display des faits cités).`
  }
  const view = renderAnswer(input.factsheet, best.out, best.report)
  const { text, ...factsheet } = view
  return {
    answer: text,
    factsheet,
    model,
    attempts: Math.min(attempts, 2),
    usage,
    reports,
    promptVersion: FACTSHEET_PROMPT_VERSION,
  }
}
