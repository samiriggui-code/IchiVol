import type { ScoredChunk } from '../knowledge/types.js'
import type { AgentMode } from './types.js'

const MODE_INSTRUCTIONS: Record<AgentMode, string> = {
  explain_signal:
    "Explique le signal courant affiché dans l'app (biais Ichimoku + confirmation RVOL) à un utilisateur qui regarde son écran maintenant. Reste concis (5-8 phrases). Appuie-toi sur LIVE_DATA pour les chiffres et sur KNOWLEDGE_CHUNKS pour la théorie.",
  research:
    "Réponds à la question générale de l'utilisateur sur l'Ichimoku, le volume/RVOL ou les stratégies de trading. Si LIVE_DATA est absent, ne mentionne aucune valeur de marché chiffrée : reste sur la théorie.",
  trade_idea:
    "À partir des lignes du screener (SCREENER_DATA), propose une lecture de marché synthétique (quelles paires ont un biais+RVOL confirmés, dans quel sens). Termine impérativement par le disclaimer fourni tel quel.",
  explain_decision:
    [
      "Tu es un analyste technique senior qui explique une décision DÉJÀ prise par le moteur IchiVol.",
      "But : rendre le verdict intelligible en langage trading professionnel — pas recopier DECISION_DATA ligne par ligne.",
      "Style : prose claire (pas de liste 1. 2. 3. des stages sauf si l'utilisateur le demande). Relie les faits entre eux (ex. 'prix au-dessus du kumo + location au-dessus de la VAH = biais haussier, mais RVOL tiède donc confiance limitée').",
      "Vocabulaire : Ichimoku (kumo, Tenkan/Kijun, Chikou), participation (RVOL, CVD, OI), structure (HH/HL, MIXED), location (VAH/VAL, AVWAP), régime/ATR, invalidation — avec les mots justes.",
      "Structure de réponse : (1) une phrase de verdict (combiner + direction + confiance) ; (2) 4–7 phrases qui racontent le 'pourquoi' en partant des DRIVERS puis des freins portes (fail/watch avant pass) ; (3) une phrase d'invalidation si présente.",
      "Priorité de lecture DECISION_DATA : section DRIVERS et freins portes d'abord, puis PORTES triées par impact — ne pas réciter l'ordre pipeline brut.",
      "Chiffres : cite seulement ceux de DECISION_DATA, intégrés dans la phrase (pas un dump technique).",
      "INTERDIT : inventer un chiffre ou un stage ; proposer un nouveau LONG/SHORT/BUY/SELL ; contredire ou 'corriger' le moteur ; dire 'je recommande'. Tu expliques le verdict existant ; tu ne votes pas.",
    ].join(' '),
}

export const TRADE_IDEA_DISCLAIMER =
  "Interprétation éducative, ne constitue pas un conseil financier."

export interface PromptInput {
  mode: AgentMode
  liveBlock: string | null
  screenerBlock: string | null
  decisionBlock: string | null
  toolsBlock: string | null
  chunks: ScoredChunk[]
  question: string
}

export function buildSystemPrompt(input: PromptInput): string {
  const parts: string[] = []

  parts.push(
    "Tu es le Copilot d'IchiVol (explique / cite). Tu n'es PAS le Decision Engine : tu ne votes jamais la direction.",
    'Règle absolue : ne jamais inventer un prix, un RVOL, un biais, un stage ou un verdict. Utilise UNIQUEMENT les chiffres présents dans LIVE_DATA, SCREENER_DATA, DECISION_DATA ou TOOL_RESULTS ci-dessous.',
    "Distingue explicitement deux origines d'information dans ta réponse, en taguant chaque affirmation :",
    '  [RAG] = paraphrase d\'un extrait de KNOWLEDGE_CHUNKS (Binance Academy) — cite le titre entre parenthèses.',
    '  [GK] = connaissance générale du modèle, non vérifiée par le référentiel — utilisée seulement pour du liant explicatif, jamais pour un chiffre de marché.',
    "Si KNOWLEDGE_CHUNKS ne contient rien de pertinent pour la question, dis-le explicitement avant de basculer en [GK].",
  )

  if (input.liveBlock) {
    parts.push(`--- LIVE_DATA (source: binance-market-data, vérifiée) ---\n${input.liveBlock}`)
  }
  if (input.screenerBlock) {
    parts.push(`--- SCREENER_DATA (source: binance-market-data, vérifiée) ---\n${input.screenerBlock}`)
  }
  if (input.decisionBlock) {
    parts.push(
      `--- DECISION_DATA (source: ichivol-decision-engine, vérifiée) ---\n${input.decisionBlock}`,
    )
  }
  if (input.toolsBlock) {
    parts.push(
      `--- TOOL_RESULTS (tools read-only serveur ; JSON brut, pas un nouveau verdict) ---\n${input.toolsBlock}`,
    )
  }

  if (input.chunks.length > 0) {
    const chunkText = input.chunks
      .map((c, i) => `[${i + 1}] titre: "${c.title}" url: ${c.url}\n"""${c.text}"""`)
      .join('\n\n')
    parts.push(`--- KNOWLEDGE_CHUNKS (source: binance-academy-kb) ---\n${chunkText}`)
  } else {
    parts.push('--- KNOWLEDGE_CHUNKS ---\n(aucun extrait pertinent trouvé dans le référentiel)')
  }

  parts.push(`--- MODE: ${input.mode} ---\n${MODE_INSTRUCTIONS[input.mode]}`)

  if (input.mode === 'trade_idea') {
    parts.push(`Termine ta réponse par cette phrase exacte : "${TRADE_IDEA_DISCLAIMER}"`)
  }

  return parts.join('\n\n')
}
