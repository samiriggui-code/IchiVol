/** Helpers de lecture « humaine » des trades paper (libellés FR, montants €). */

export function eur(v: number | null | undefined, digits = 2): string {
  if (v == null || !Number.isFinite(v)) return '—'
  const s = Math.abs(v).toLocaleString('fr-FR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
  return `${v < 0 ? '−' : ''}${s} €`
}

export function signedEur(v: number | null | undefined, digits = 2): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return `${v > 0 ? '+' : ''}${eur(v, digits)}`
}

export function pct(v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return `${v > 0 ? '+' : ''}${(v * 100).toFixed(digits)} %`
}

export function price(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—'
  const digits = v >= 100 ? 2 : v >= 1 ? 4 : 6
  return v.toLocaleString('fr-FR', { maximumFractionDigits: digits })
}

export function assetName(symbol: string): string {
  return symbol.replace(/USDT$/i, '')
}

export function directionWords(direction: string | null | undefined): {
  title: string
  detail: string
} {
  if (direction === 'LONG') {
    return { title: 'Achat', detail: 'on achète, on gagne si le prix monte' }
  }
  if (direction === 'SHORT') {
    return { title: 'Vente à découvert', detail: 'on parie à la baisse, on gagne si le prix baisse' }
  }
  return { title: 'Aucune position', detail: 'pas d’entrée prévue' }
}

export function exitReasonLabel(reason: string | null | undefined): string {
  switch (reason) {
    case 'stop_hit':
      return 'Le stop (perte maximale prévue) a été touché'
    case 'take_profit_hit':
      return 'L’objectif de gain a été atteint'
    case 'pipeline_flipped':
      return 'Le signal s’est retourné dans l’autre sens'
    case 'pipeline_downgraded':
      return 'Le signal s’est affaibli (plus assez convaincant)'
    case 'manual_close':
      return 'Fermé manuellement'
    default:
      return reason ?? '—'
  }
}

/** Les règles de sortie du profil baseline, expliquées simplement. */
export const EXIT_RULES: { title: string; text: string }[] = [
  {
    title: 'Stop touché',
    text: 'Si le prix va contre nous jusqu’au stop, on sort. La perte est limitée à ce qui était prévu.',
  },
  {
    title: 'Objectif atteint',
    text: 'Si le prix atteint l’objectif (2× le risque pris), on encaisse le gain.',
  },
  {
    title: 'Signal retourné ou affaibli',
    text: 'Si IchiVol change d’avis (signal inversé ou plus assez fort), on sort sans attendre le stop.',
  },
  {
    title: 'Fermeture manuelle',
    text: 'Vous pouvez toujours clôturer vous-même depuis Synthèse ou Paper (manuel et auto).',
  },
]

export function stageStatusLabel(status: string | null | undefined): string {
  switch ((status ?? '').toLowerCase()) {
    case 'pass':
      return 'OK'
    case 'fail':
      return 'Bloque'
    case 'watch':
      return 'À surveiller'
    case 'skip':
      return 'Ignoré'
    case 'pending':
      return 'En attente'
    default:
      return status ?? '—'
  }
}

export function holdingLabel(entry: string, exit: string | null): string {
  const start = new Date(entry).getTime()
  const end = exit ? new Date(exit).getTime() : Date.now()
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return '—'
  const h = (end - start) / 3_600_000
  if (h < 1) return `${Math.max(1, Math.round(h * 60))} min`
  if (h < 48) return `${h.toFixed(1)} h`
  return `${(h / 24).toFixed(1)} jours`
}

export function hoursLabel(hours: number | null | undefined): string {
  if (hours == null || !Number.isFinite(hours)) return '—'
  if (hours < 1) return `${Math.round(hours * 60)} min`
  if (hours < 48) return `${hours.toFixed(1)} h`
  return `${(hours / 24).toFixed(1)} jours`
}
