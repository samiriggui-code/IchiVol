import type { AgentMode } from './types.js'

/** Intents allowlist E3 — mute = needsConfirm (E5 exécutera). */
export const ALLOWED_INTENTS = [
  'explain_decision',
  'explain_signal',
  'research',
  'trade_idea',
  'save_decision',
  'pin_symbol',
  'open_paper_position',
  'fallback',
] as const

export type AgentIntent = (typeof ALLOWED_INTENTS)[number]

export interface PlannerParams {
  symbol?: string
  timeframe?: string
}

export interface PlannerResult {
  intent: AgentIntent
  params: PlannerParams
  /** Source de la décision d'intent. */
  source: 'ui_mode' | 'rules' | 'fallback'
  needsConfirm: boolean
  /** Message immédiat sans LLM (fallback / confirm). */
  shortCircuitAnswer?: string
}

const MUTE_INTENTS = new Set<AgentIntent>(['save_decision', 'pin_symbol', 'open_paper_position'])

const FALLBACK_MENU = [
  'Je n’ai pas compris l’intention. Tu peux :',
  '• Expliquer une décision (ex. « explique la décision NEARUSDT 1h »)',
  '• Expliquer le signal marché (ex. « explique le signal BTC »)',
  '• Poser une question théorie Ichimoku / RVOL',
  '• Demander une idée de screener (« quelles paires sont confirmées ? »)',
].join('\n')

/** Paires crypto usuelles → SYMBOLUSDT si l’user dit juste BTC. */
const BASE_ALIASES: Record<string, string> = {
  btc: 'BTCUSDT',
  bitcoin: 'BTCUSDT',
  eth: 'ETHUSDT',
  ethereum: 'ETHUSDT',
  sol: 'SOLUSDT',
  solana: 'SOLUSDT',
  near: 'NEARUSDT',
  avax: 'AVAXUSDT',
  link: 'LINKUSDT',
  doge: 'DOGEUSDT',
  xrp: 'XRPUSDT',
  bnb: 'BNBUSDT',
}

const SYMBOL_RE = /\b([A-Z]{2,12}USDT)\b/i
const BASE_RE = /\b(btc|bitcoin|eth|ethereum|sol|solana|near|avax|link|doge|xrp|bnb)\b/i
const TF_RE = /\b(1m|3m|5m|15m|30m|1h|2h|4h|6h|12h|1d|3d|1w)\b/i

type Rule = {
  intent: AgentIntent
  /** All groups must match (AND of ORs). */
  anyOf: RegExp[]
}

const RULES: Rule[] = [
  {
    intent: 'save_decision',
    anyOf: [
      /\b(sauve|sauvegarde|enregistre|confirme)\b.*\b(d[eé]cision|trade|setup)\b/i,
      /\b(save|confirm)\b.*\b(decision|trade)\b/i,
      /\bajoute\b.*\bjournal\b/i,
    ],
  },
  {
    intent: 'pin_symbol',
    anyOf: [
      /\b(pin|epine|épingle|watchlist|liste de suivi)\b/i,
      /\bsuis\b.*\b(paire|symbole|symbol)\b/i,
      /\bajoute\b.*\b(watchlist|suivi)\b/i,
    ],
  },
  {
    intent: 'open_paper_position',
    anyOf: [
      /\b(ouvre|ouvrir|lance)\b.*\b(position|trade)\b/i,
      /\b(ach[eè]te|vends?|long|short)\b.*\b(papier|paper|fictif|fictive|virtuel|virtuelle)\b/i,
      /\bposition\s+(papier|paper|fictive|virtuelle)\b/i,
      /\bpaper[\s_-]?trad(e|ing)\b/i,
    ],
  },
  {
    intent: 'explain_decision',
    anyOf: [
      /\b(explique|expliquer|pourquoi|why)\b.*\b(d[eé]cision|verdict|porte|pipeline|combiner|buy|sell|watch|no[_ ]?trade)\b/i,
      /\b(d[eé]cision|verdict|pipeline|portes?)\b.*\b(explique|pourquoi|why)\b/i,
      /\bpourquoi\b.*\b(ce|cette)?\s*(buy|sell|watch|strong[_ ]?buy)/i,
    ],
  },
  {
    intent: 'explain_signal',
    anyOf: [
      /\b(explique|expliquer)\b.*\b(signal|biais|rvol|march[eé])\b/i,
      /\b(signal|biais)\b.*\b(explique|pourquoi)\b/i,
      /\bichimoku\b.*\b(maintenant|actuel|live)\b/i,
    ],
  },
  {
    intent: 'trade_idea',
    anyOf: [
      /\b(id[eé]e|screener|quelles paires|quoi trader|setups? confirm)/i,
      /\b(paires?|symbols?)\b.*\b(confirm|rvol|biais)\b/i,
    ],
  },
  {
    intent: 'research',
    anyOf: [
      /\b(c['’]est quoi|qu['’]est[- ]ce|d[eé]finition|th[eé]orie|comment (marche|fonctionne))\b/i,
      /\b(tenkan|kijun|kumo|chikou|senkou|rvol|relative volume|atr|vwap|vah|val)\b/i,
    ],
  },
]

function normalizeQuestion(q: string): string {
  return q
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{M}/gu, '')
    .replace(/\s+/g, ' ')
    .trim()
}

export function extractSymbolFromText(text: string): string | undefined {
  const usdt = text.match(SYMBOL_RE)
  if (usdt) return usdt[1].toUpperCase()
  const base = text.match(BASE_RE)
  if (base) {
    const key = base[1].toLowerCase()
    return BASE_ALIASES[key]
  }
  return undefined
}

export function extractTimeframeFromText(text: string): string | undefined {
  const m = text.match(TF_RE)
  return m ? m[1].toLowerCase() : undefined
}

function matchRules(question: string): AgentIntent | null {
  const q = normalizeQuestion(question)
  if (!q) return null
  for (const rule of RULES) {
    if (rule.anyOf.some((re) => re.test(q) || re.test(question))) {
      return rule.intent
    }
  }
  return null
}

function isAgentMode(intent: AgentIntent): intent is AgentMode {
  return (
    intent === 'explain_decision' ||
    intent === 'explain_signal' ||
    intent === 'research' ||
    intent === 'trade_idea'
  )
}

function confirmPrompt(intent: AgentIntent, params: PlannerParams): string {
  const sym = params.symbol ?? 'ce symbole'
  if (intent === 'save_decision') {
    return `Action proposée : enregistrer la décision sur **${sym}** (${params.timeframe ?? '1h'}) dans le journal. Confirme ou annule ci-dessous.`
  }
  if (intent === 'open_paper_position') {
    return `Action proposée : ouvrir une position **papier** (fictive, jamais un ordre réel) sur **${sym}** (${params.timeframe ?? '1h'}) — seulement si le moteur confirme encore un BUY/SELL au moment où tu confirmes. Confirme ou annule ci-dessous.`
  }
  return `Action proposée : épingler **${sym}** en watchlist. Confirme ou annule ci-dessous.`
}

/**
 * Router intent E3 (règles + synonyme).
 * Priorité : intents mute → règles question → mode UI → fallback.
 */
export function planIntent(input: {
  question: string
  uiMode: AgentMode
  knownSymbol?: string
  knownTimeframe?: string
}): PlannerResult {
  const question = input.question ?? ''
  const symbol =
    extractSymbolFromText(question) ??
    (input.knownSymbol ? input.knownSymbol.toUpperCase() : undefined)
  const timeframe =
    extractTimeframeFromText(question) ?? input.knownTimeframe ?? '1h'
  const params: PlannerParams = { symbol, timeframe }

  const fromRules = matchRules(question)

  if (fromRules && MUTE_INTENTS.has(fromRules)) {
    return {
      intent: fromRules,
      params,
      source: 'rules',
      needsConfirm: true,
      shortCircuitAnswer: confirmPrompt(fromRules, params),
    }
  }

  if (fromRules && isAgentMode(fromRules)) {
    return {
      intent: fromRules,
      params,
      source: 'rules',
      needsConfirm: false,
    }
  }

  // Mode UI explicite (onglet Copilot)
  if (input.uiMode) {
    const emptyQ = !question.trim()
    if (emptyQ && input.uiMode === 'research') {
      return {
        intent: 'fallback',
        params,
        source: 'fallback',
        needsConfirm: false,
        shortCircuitAnswer: FALLBACK_MENU,
      }
    }
    return {
      intent: input.uiMode,
      params,
      source: 'ui_mode',
      needsConfirm: false,
    }
  }

  return {
    intent: 'fallback',
    params,
    source: 'fallback',
    needsConfirm: false,
    shortCircuitAnswer: FALLBACK_MENU,
  }
}

export function intentToMode(intent: AgentIntent, fallback: AgentMode): AgentMode {
  if (isAgentMode(intent)) return intent
  return fallback
}

export { FALLBACK_MENU }
