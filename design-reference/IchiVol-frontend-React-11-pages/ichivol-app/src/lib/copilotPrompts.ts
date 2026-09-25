import type { AgentDecisionPayload, AgentLivePayload, AgentMode } from './agent'

/** Prompts métier préremplis — l’utilisateur land sur le Copilot en sachant quoi demander. */

export function promptExplainDecision(d: AgentDecisionPayload): string {
  const gate = d.gateDecision ?? '—'
  const stages =
    d.stages.length > 0
      ? d.stages
          .map((s) => `${s.id}:${s.status}`)
          .join(', ')
      : 'non fournis'
  return (
    `Explique la décision sur ${d.symbol} (${d.timeframe}).\n` +
    `• Verdict portes : ${gate}\n` +
    `• Badge combiner (diagnostic) : ${d.combiner}\n` +
    `• Direction structure : ${d.direction}\n` +
    `• Étages : ${stages}\n\n` +
    `Dis clairement ce qui confirme, ce qui bloque, et les risques / invalidation. ` +
    `Ne propose pas un autre sens LONG/SHORT et ne recalcule aucun chiffre.`
  )
}

export function promptExplainSignal(live: AgentLivePayload): string {
  const sig = live.lastSignal
    ? `${live.lastSignal.kind} @ ${live.lastSignal.price}`
    : 'aucun signal récent'
  return (
    `Explique le signal live sur ${live.symbol} (${live.interval}).\n` +
    `• Biais : ${live.bias}\n` +
    `• RVOL : ${live.rvol}\n` +
    `• Prix : ${live.price ?? '—'}\n` +
    `• Dernier signal : ${sig}\n\n` +
    `Reste factuel sur ces données. Ne vote pas une direction différente du biais fourni.`
  )
}

export function promptTradeIdea(symbol?: string): string {
  const focus = symbol ? ` sur ${symbol}` : ''
  return (
    `Propose une idée de trade${focus} à partir du screener / contexte fourni. ` +
    `Rappelle le disclaimer : pas un conseil financier. ` +
    `Appuie-toi uniquement sur les données injectées, sans inventer d’OHLC ni de RVOL.`
  )
}

export function promptResearch(topic: string): string {
  const t = topic.trim()
  if (!t) {
    return 'Explique le rôle d’Ichimoku et du RVOL dans la méthode IchiVol, avec citations KB si possible.'
  }
  return t
}

export function promptCompareGates(d: AgentDecisionPayload): string {
  return (
    `Sur ${d.symbol} (${d.timeframe}), le badge combiner dit « ${d.combiner} » ` +
    `et les portes disent « ${d.gateDecision ?? '—'} ».\n` +
    `Explique l’écart (si écart) : quelles portes supplémentaires ont rétrogradé ou confirmé. ` +
    `Ne choisis pas « le vrai » trade à ma place — clarifie seulement la lecture.`
  )
}

export type CopilotLaunchKind =
  | 'explain_decision'
  | 'explain_signal'
  | 'trade_idea'
  | 'research'
  | 'compare_gates'

export function defaultPromptFor(
  kind: CopilotLaunchKind,
  ctx: {
    decision?: AgentDecisionPayload | null
    live?: AgentLivePayload | null
    topic?: string
    symbol?: string
  },
): { mode: AgentMode; prompt: string } {
  switch (kind) {
    case 'explain_decision':
      if (!ctx.decision) {
        return {
          mode: 'research',
          prompt: 'Explique comment lire une décision IchiVol (portes vs badge combiner).',
        }
      }
      return { mode: 'explain_decision', prompt: promptExplainDecision(ctx.decision) }
    case 'compare_gates':
      if (!ctx.decision) {
        return {
          mode: 'research',
          prompt: 'Explique la différence entre badge combiner et verdict portes.',
        }
      }
      return { mode: 'explain_decision', prompt: promptCompareGates(ctx.decision) }
    case 'explain_signal':
      if (!ctx.live) {
        return {
          mode: 'research',
          prompt: 'Explique comment lire biais + RVOL sur le chart Marché.',
        }
      }
      return { mode: 'explain_signal', prompt: promptExplainSignal(ctx.live) }
    case 'trade_idea':
      return { mode: 'trade_idea', prompt: promptTradeIdea(ctx.symbol) }
    case 'research':
      return { mode: 'research', prompt: promptResearch(ctx.topic ?? '') }
    default: {
      const _exhaustive: never = kind
      return _exhaustive
    }
  }
}
