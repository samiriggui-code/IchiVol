/**
 * Les quatre modes d'Ève : LA source des textes affichés (page Ève, fiches, réglages, landing).
 * Vérifié dans le moteur (`engine/app/eve/modes.py`) : chaque mode pose à JEV les trois types de questions
 * (NOUL, CHOICE, SCORE) ; la synthèse d'Ève tranche, et le Risk Kernel garde le dernier mot.
 */

export type EveModeId = 'analyst' | 'challenger' | 'guardian' | 'shadow'

export type EveMode = {
  id: EveModeId
  /** Nom propre du mode, gardé en anglais (c'est son nom). */
  name: string
  icon: string
  /** Une phrase, ce que fait le mode. */
  blurb: string
  /** Ce qui se passe quand le mode n'est pas d'accord, tel que le moteur l'applique. */
  effect: string
  /** Version courte pour une liste. */
  short: string
}

export const EVE_MODES: EveMode[] = [
  {
    id: 'analyst',
    name: 'Analyst',
    icon: '◇',
    blurb: 'Lit les calculs du moteur et la structure du marché, puis propose un scénario : acheter, vendre à découvert, attendre ou s’abstenir.',
    effect: 'Son scénario sert de base ; si JEV lui désigne un scénario principal, c’est celui-là qu’Ève retient.',
    short: 'lit les calculs du moteur et propose un scénario',
  },
  {
    id: 'challenger',
    name: 'Challenger',
    icon: '↺',
    blurb: 'Cherche ce qui contredit le scénario retenu et les autres possibilités.',
    effect: 'S’il juge le scénario trop fragile, Ève s’abstient au lieu de prendre position.',
    short: 'cherche ce qui contredit le scénario',
  },
  {
    id: 'guardian',
    name: 'Guardian',
    icon: '◈',
    blurb: 'Passe en revue les risques et les anomalies : données manquantes, arrêt d’urgence, niveau de risque.',
    effect: 'Un risque critique fait abstenir Ève. Le Risk Kernel et l’arrêt d’urgence restent au-dessus de lui.',
    short: 'signale les risques et les anomalies',
  },
  {
    id: 'shadow',
    name: 'Shadow',
    icon: '◉',
    blurb: 'Refait l’évaluation de son côté, sans voir les autres modes, comme un second avis indépendant.',
    effect: 'S’il contredit la décision ou n’a pas confiance, Ève s’abstient. Il n’exécute jamais rien.',
    short: 'refait l’évaluation de son côté, sans voir les autres modes',
  },
]

/** Les trois types de questions posées à JEV, par tous les modes. */
export const JEV_PRIMITIVES = 'NOUL + CHOICE + SCORE'

export const JEV_PRIMITIVES_EXPLAIN =
  'JEV répond à trois types de questions : NOUL (oui ou non, avec une probabilité), CHOICE (choisir une option) et SCORE (noter sur une échelle).'

export function eveModeById(id: string): EveMode | undefined {
  return EVE_MODES.find((m) => m.id === id)
}
