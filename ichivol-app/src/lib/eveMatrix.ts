/**
 * Overlay matrice Opportunités : dossiers Ève / JEV → cellules lisibles.
 * Les 5 portes restent le Decision Engine ; Ève ajoute action + garde-fous JEV.
 */

export type EveDossierLite = {
  id: string
  symbol: string
  timeframe?: string
  eve_action?: string | null
  baseline_decision?: string | null
  execution_status?: string | null
  created_at?: string | null
  decision_time?: {
    degradation?: { level?: string; mean_confidence?: number | null } | null
    entry_gate?: { decision?: string; allowed?: boolean; reason?: string } | null
    heuristic?: { label?: string } | null
  } | null
  jev?: Record<string, unknown> | null
  modes?: Record<string, unknown> | null
  verdict?: {
    action?: string
    body?: { risk_authorization?: string; paper_submit_status?: string }
  } | null
}

export type EveMatrixOverlay = {
  dossierId: string
  action: string
  baseline: string
  /** healthy | late | low_confidence | jev_down | — */
  jevHealth: string
  entryGate: string
  risk: string
  confidenceLabel: string
}

function modeJevOk(pack: unknown): boolean | null {
  if (!pack || typeof pack !== 'object') return null
  const p = pack as Record<string, unknown>
  if (p.ok === false || p.error) return false
  if (p.late === true) return false
  if (p.ok === true) return true
  return null
}

/** Agrège ok/late des packs JEV modes (analyst/challenger/guardian/shadow). */
/** Libellé court pour la matrice : OK / LENT / DOWN / FAIBLE / — */
export function summarizeJevHealth(dossier: EveDossierLite): string {
  const deg = dossier.decision_time?.degradation?.level
  if (deg === 'late') return 'lent'
  if (deg === 'jev_down') return 'down'
  if (deg === 'low_confidence') return 'faible'
  if (deg && deg !== 'healthy') return String(deg)

  const jev = dossier.jev
  if (!jev || typeof jev !== 'object') return '—'

  const packs = ['analyst', 'challenger', 'guardian', 'shadow'].map((k) =>
    modeJevOk((jev as Record<string, unknown>)[k]),
  )
  if (packs.every((x) => x === null)) return '—'
  if (packs.some((x) => x === false)) return 'panne'
  if (packs.some((x) => x === true)) return 'ok'
  return '—'
}

export function entryGateLabel(dossier: EveDossierLite): string {
  const g = dossier.decision_time?.entry_gate
  if (!g) return '—'
  if (g.allowed === true || g.decision === 'allow') return 'PASS'
  if (g.decision === 'reject' || g.allowed === false) return 'BLOQUÉ'
  return String(g.decision || '—').toUpperCase()
}

export function riskLabel(dossier: EveDossierLite): string {
  const auth = dossier.verdict?.body?.risk_authorization
  const exec = dossier.execution_status || ''
  if (auth && auth !== 'not_submitted' && auth !== 'not_applicable') {
    return String(auth).replace(/_/g, ' ')
  }
  if (!exec || exec === 'not_executed') return '—'
  return exec.replace(/_/g, ' ')
}

export function overlayFromDossier(dossier: EveDossierLite): EveMatrixOverlay {
  const action = String(
    dossier.eve_action || dossier.verdict?.action || '—',
  ).toUpperCase()
  const mean = dossier.decision_time?.degradation?.mean_confidence
  const confidenceLabel =
    typeof mean === 'number' && Number.isFinite(mean)
      ? `${Math.round(mean * 100)} %`
      : '—'
  return {
    dossierId: dossier.id,
    action,
    baseline: String(dossier.baseline_decision || '—'),
    jevHealth: summarizeJevHealth(dossier),
    entryGate: entryGateLabel(dossier),
    risk: riskLabel(dossier),
    confidenceLabel,
  }
}

/** Dernier dossier par symbole (liste déjà triée created_at desc). */
export function latestDossierBySymbol(
  dossiers: EveDossierLite[],
): Map<string, EveDossierLite> {
  const map = new Map<string, EveDossierLite>()
  for (const d of dossiers) {
    const sym = String(d.symbol || '').toUpperCase()
    if (!sym || map.has(sym)) continue
    map.set(sym, d)
  }
  return map
}

export function eveActionTone(
  action: string,
): 'green' | 'red' | 'amber' | 'gray' | '' {
  const a = action.toUpperCase()
  if (a === 'LONG') return 'green'
  if (a === 'SHORT') return 'red'
  if (a === 'HOLD' || a === 'CLOSE') return 'amber'
  if (a === 'ABSTAIN') return 'gray'
  return ''
}

export function jevHealthTone(
  level: string,
): 'green' | 'red' | 'amber' | 'gray' | '' {
  if (level === 'ok' || level === 'healthy') return 'green'
  if (
    level === 'late' ||
    level === 'lent' ||
    level === 'low_confidence' ||
    level === 'faible' ||
    level === 'jev_down' ||
    level === 'down' ||
    level === 'panne'
  )
    return 'red'
  if (level === 'degraded') return 'amber'
  return 'gray'
}
