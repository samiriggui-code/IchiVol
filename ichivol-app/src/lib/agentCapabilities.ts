/** Thin client for GET /api/engine/agent/capabilities (engine agent channel). */

export interface AgentCapabilities {
  version?: string
  read_only?: boolean
  write_tier_enabled?: boolean
  write_scopes?: string[]
  write_commands?: string[]
  max_batch_items?: number
  commands?: string[]
}

export type CapabilityBadgeStatus = 'available' | 'human_confirm' | 'unavailable'

export interface CapabilityBadge {
  id: 'read_context' | 'explain_refusal' | 'place_order'
  label: string
  status: CapabilityBadgeStatus
  statusLabel: string
  detail: string
}

const READ_CONTEXT_COMMANDS = [
  'get_symbol_context',
  'scan_market',
  'detect_signal',
  'compare_timeframes',
  'list_tools',
] as const

async function parseError(res: Response): Promise<string> {
  const body = (await res.json().catch(() => null)) as
    | { detail?: string; message?: string; error?: string }
    | null
  return body?.detail ?? body?.message ?? body?.error ?? `Erreur ${res.status}`
}

export async function getAgentCapabilities(): Promise<AgentCapabilities> {
  const res = await fetch('/api/engine/agent/capabilities', { credentials: 'include' })
  if (!res.ok) throw new Error(await parseError(res))
  return (await res.json()) as AgentCapabilities
}

function hasAnyCommand(commands: string[] | undefined, names: readonly string[]): boolean {
  if (!commands?.length) return false
  const set = new Set(commands)
  return names.some((n) => set.has(n))
}

/**
 * Map engine capabilities to Copilot UI badges — honest:
 * - Lecture / explication = canal lecture (tools read).
 * - Passer un ordre = paper hors canal agent → confirmation humaine requise.
 */
export function mapCapabilityBadges(caps: AgentCapabilities | null): CapabilityBadge[] {
  const commands = caps?.commands
  const canRead = hasAnyCommand(commands, READ_CONTEXT_COMMANDS)
  const scopes = caps?.write_scopes ?? []
  const paperOnChannel = scopes.includes('paper') || scopes.includes('orders')
  const writeCmds = caps?.write_commands ?? []
  const hasPaperWriteCmd = writeCmds.some(
    (c) => c.includes('paper') || c.includes('order') || c.includes('position'),
  )

  return [
    {
      id: 'read_context',
      label: 'Lecture contexte',
      status: canRead ? 'available' : 'unavailable',
      statusLabel: canRead ? 'Disponible' : 'Indisponible',
      detail: canRead
        ? 'Outils moteur en lecture (contexte symbole, scan, signal).'
        : 'Canal agent sans outils de lecture contexte.',
    },
    {
      id: 'explain_refusal',
      label: 'Explication refus',
      status: canRead ? 'available' : 'unavailable',
      statusLabel: canRead ? 'Disponible' : 'Indisponible',
      detail: canRead
        ? 'Le Copilot peut expliquer un refus à partir du contexte moteur.'
        : 'Sans lecture contexte, l’explication de refus n’est pas ancrée.',
    },
    {
      id: 'place_order',
      label: 'Passer un ordre',
      status: 'human_confirm',
      statusLabel: 'Confirmation humaine requise',
      detail:
        paperOnChannel || hasPaperWriteCmd
          ? 'Écriture paper possible via le canal — confirmation UI obligatoire.'
          : 'Paper hors canal agent (POST /paper/positions) — confirmation humaine requise.',
    },
  ]
}
