/**
 * Textes en français des réglages Ève / JEV servis par le moteur (`engine/app/eve/settings_schema.py`).
 *
 * Le moteur fournit les clés, valeurs, défauts et droits d'écriture ; ce fichier dit ce que chaque
 * réglage fait vraiment, vérifié dans le code du moteur :
 * - JEV_MIN_CONFIDENCE / EVE_ENTRY_GATE_MIN_CONFIDENCE → calibration.active_policy → orchestrator
 * - JEV_TIMEOUT_SECONDS → jev/adapter (réponse en retard = Ève attend)
 * - EVENT_RADAR_* → eve/event_radar, résumé injecté dans le contexte JEV (eve/context)
 * - EVENT_RADAR_YAHOO_FINANCE_RSS_ENABLED / EVENT_RADAR_SEC_EDGAR_ENABLED → lus mais aucune source branchée
 *   (`source_status` = "not_wired") : affichés comme « pas encore utilisés par le moteur ».
 */

export type KnobUnit = 'pct' | 'seconds' | 'days' | 'count' | 'switch'

export type KnobGroup = 'decision' | 'news' | 'server' | 'autonomy'

export interface KnobCopy {
  group: KnobGroup
  label: string
  /** Une phrase : ce que fait le réglage. */
  explain: string
  up?: string
  down?: string
  unit?: KnobUnit
  min?: number
  max?: number
  step?: number
  /** Lu par le moteur mais sans effet aujourd'hui. */
  unused?: boolean
}

export const EVE_KNOBS: Record<string, KnobCopy> = {
  JEV_MIN_CONFIDENCE: {
    group: 'decision',
    label: 'Confiance minimale de JEV',
    explain:
      'Si JEV répond avec une confiance plus basse que ce seuil, Ève s’abstient au lieu de prendre position.',
    up: 'Ève trade moins souvent, seulement quand JEV est sûr de lui.',
    down: 'Ève suit aussi des avis hésitants : plus de trades, plus de faux signaux.',
    unit: 'pct',
    min: 0,
    max: 100,
    step: 5,
  },
  EVE_ENTRY_GATE_MIN_CONFIDENCE: {
    group: 'decision',
    label: 'Confiance exigée pour ouvrir une position',
    explain:
      'Dernier contrôle d’Ève avant une ouverture : sous ce seuil, l’achat ou la vente à découvert est refusé. Fermer une position reste toujours possible.',
    up: 'Moins d’ouvertures, réservées aux situations les plus nettes.',
    down: 'Plus d’ouvertures, y compris sur des signaux moyens.',
    unit: 'pct',
    min: 0,
    max: 100,
    step: 5,
  },
  JEV_TIMEOUT_SECONDS: {
    group: 'decision',
    label: 'Délai maximal de réponse de JEV',
    explain:
      'Au-delà de ce délai, la réponse de JEV est jugée périmée et Ève attend : jamais de trade sur une analyse en retard.',
    up: 'Ève patiente davantage : moins d’abstentions quand JEV est lent, décisions plus tardives.',
    down: 'Décisions plus fraîches, mais plus d’abstentions dès que JEV ralentit.',
    unit: 'seconds',
    min: 1,
    max: 300,
    step: 1,
  },
  EVENT_RADAR_ENABLED: {
    group: 'news',
    label: 'Activer la veille d’actualité',
    explain:
      'Ajoute un résumé des actualités récentes de l’actif à ce qu’Ève transmet à JEV. Purement informatif : une actualité ne déclenche jamais un trade à elle seule.',
    unit: 'switch',
  },
  EVENT_RADAR_JEV_MIN_CONFIDENCE: {
    group: 'news',
    label: 'Confiance minimale pour la lecture des actualités',
    explain:
      'JEV lit les actualités et en tire une tendance. Sous ce seuil, sa lecture est écartée et remplacée par une lecture simple par règles.',
    up: 'La lecture de JEV n’est gardée que lorsqu’elle est très sûre.',
    down: 'La lecture de JEV est gardée plus souvent, même hésitante.',
    unit: 'pct',
    min: 0,
    max: 100,
    step: 5,
  },
  EVENT_RADAR_NEWS_LOOKBACK_DAYS: {
    group: 'news',
    label: 'Ancienneté maximale des actualités',
    explain: 'Seules les actualités publiées dans cette fenêtre sont prises en compte.',
    up: 'Plus d’actualités, dont certaines déjà intégrées dans le prix.',
    down: 'Uniquement le très récent, parfois rien du tout.',
    unit: 'days',
    min: 1,
    max: 30,
    step: 1,
  },
  EVENT_RADAR_MAX_EVENTS: {
    group: 'news',
    label: 'Nombre maximal d’actualités retenues',
    explain: 'Plafond d’actualités résumées pour chaque actif (le moteur le limite à 20).',
    up: 'Contexte plus riche, analyse un peu plus longue.',
    down: 'Contexte plus court, centré sur les titres les plus pertinents.',
    unit: 'count',
    min: 1,
    max: 20,
    step: 1,
  },
  EVENT_RADAR_CRYPTO_RSS_ENABLED: {
    group: 'news',
    label: 'Source : actualités crypto (CoinDesk, Cointelegraph)',
    explain: 'La seule source branchée aujourd’hui. Si vous la coupez, la veille ne trouve plus rien.',
    unit: 'switch',
  },
  EVENT_RADAR_YAHOO_FINANCE_RSS_ENABLED: {
    group: 'news',
    label: 'Source : Yahoo Finance',
    explain: 'Prévue pour les actions et indices. Le moteur ne la consulte pas encore.',
    unit: 'switch',
    unused: true,
  },
  EVENT_RADAR_SEC_EDGAR_ENABLED: {
    group: 'news',
    label: 'Source : documents officiels SEC (actions américaines)',
    explain: 'Prévue pour les publications réglementaires. Le moteur ne la consulte pas encore.',
    unit: 'switch',
    unused: true,
  },
  EVE_PAPER_AUTONOMY: { group: 'autonomy', label: 'Pilote automatique d’Ève', explain: '' },
  JEV_API_KEY: { group: 'server', label: 'Clé d’accès JEV', explain: '' },
  JEV_PROVIDER: { group: 'server', label: 'Service JEV principal', explain: '' },
  JEV_FALLBACK: { group: 'server', label: 'Secours si les crédits sont épuisés', explain: '' },
  JEV_URL: { group: 'server', label: 'Adresse du service local', explain: '' },
  JEV_MODEL: { group: 'server', label: 'Version du modèle JEV', explain: '' },
}

/** Les cinq modes d'Ève — noms gardés en anglais, comme dans l'application. */
export const EVE_MODES: Array<{ name: string; text: string }> = [
  {
    name: 'Copilot',
    text: 'Le chat avec qui vous discutez. Il explique les décisions et répond à vos questions, sans jamais passer d’ordre. Il utilise le modèle choisi dans « Modèles d’IA ».',
  },
  {
    name: 'Analyst',
    text: 'Lit les signaux du moteur et propose un scénario : acheter, vendre à découvert, attendre ou s’abstenir.',
  },
  {
    name: 'Challenger',
    text: 'Cherche les arguments contraires. S’il trouve trop de contradictions, Ève s’abstient.',
  },
  {
    name: 'Guardian',
    text: 'Passe en revue les risques (données manquantes, arrêt d’urgence, anomalies). Un risque critique force l’abstention.',
  },
  {
    name: 'Shadow',
    text: 'Donne un second avis indépendant sur la décision du moteur, pour repérer les désaccords.',
  },
]

/** Valeur moteur → valeur affichée dans le champ (les confiances 0–1 deviennent des %). */
export function toDisplay(unit: KnobUnit | undefined, raw: unknown): string {
  if (raw === undefined || raw === null || raw === '') return ''
  const n = Number(raw)
  if (!Number.isFinite(n)) return String(raw)
  if (unit === 'pct') return String(Math.round(n * 1000) / 10)
  return String(n)
}

/** Valeur saisie → valeur envoyée au moteur ; `null` si invalide. */
export function fromDisplay(copy: KnobCopy | undefined, text: string): number | null {
  const n = Number(text.replace(',', '.'))
  if (text.trim() === '' || !Number.isFinite(n)) return null
  if (copy?.min != null && n < copy.min) return null
  if (copy?.max != null && n > copy.max) return null
  if (copy?.unit === 'pct') return Math.round(n * 10) / 1000
  if (copy?.unit === 'days' || copy?.unit === 'count') return Math.round(n)
  return n
}

export function formatKnob(unit: KnobUnit | undefined, raw: unknown): string {
  if (raw === undefined || raw === null || raw === '') return '—'
  if (typeof raw === 'boolean') return raw ? 'Activé' : 'Désactivé'
  const n = Number(raw)
  if (!Number.isFinite(n)) return String(raw)
  const fr = (v: number, d = 1) => v.toLocaleString('fr-FR', { maximumFractionDigits: d })
  switch (unit) {
    case 'pct':
      return `${fr(n * 100)} %`
    case 'seconds':
      return `${fr(n)} s`
    case 'days':
      return `${fr(n, 0)} jour${n > 1 ? 's' : ''}`
    case 'count':
      return fr(n, 0)
    default:
      return fr(n, 2)
  }
}

/** Service JEV : jamais de marque ni d'adresse à l'écran, seulement « Cloud » ou « Local ». */
export function jevServiceLabel(provider: unknown): string {
  const p = String(provider ?? '').toLowerCase()
  if (!p) return '—'
  if (p === 'jevos' || p === 'local') return 'Local'
  if (p === 'none' || p === 'off') return 'Aucun'
  return 'Cloud'
}
