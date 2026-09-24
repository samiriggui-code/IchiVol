/**
 * T14a — navigation workspace (maquette design-reference/ichivol-workspace).
 * Labels & groups only; pages keep existing engines / APIs.
 */

import type { ComponentType } from 'react'
import {
  IconActivity,
  IconBacktests,
  IconChat,
  IconDecisions,
  IconGlobe,
  IconJournal,
  IconMarket,
  IconOverview,
  IconPaper,
  IconSettings,
  IconWatchlist,
} from '../components/NavIcons'

export type NavItem = {
  to: string
  label: string
  Icon: ComponentType<{ className?: string }>
  /** Glyph maquette (▦ ⌁ …). */
  glyph: string
  /** Hide from sidebar (still reachable via redirect / deep link). */
  sidebarHidden?: boolean
}

export type NavGroup = {
  id: string
  label: string
  items: NavItem[]
}

/** Primary IA — 4 groups (rév.58 T14a + maquette). */
export const NAV_GROUPS: NavGroup[] = [
  {
    id: 'trading',
    label: 'Trading',
    items: [
      { to: '/app/desk', label: 'Desk', Icon: IconOverview, glyph: '▦' },
      { to: '/app/market', label: 'Marché', Icon: IconMarket, glyph: '⌁' },
      { to: '/app/opportunites', label: 'Opportunités', Icon: IconDecisions, glyph: '◇' },
      { to: '/app/portefeuille', label: 'Portefeuille', Icon: IconPaper, glyph: '◫' },
    ],
  },
  {
    id: 'research',
    label: 'Recherche',
    items: [
      { to: '/app/strategy-lab', label: 'Strategy Lab', Icon: IconBacktests, glyph: '⚗' },
      { to: '/app/journal', label: 'Journal', Icon: IconJournal, glyph: '▤' },
      { to: '/app/context', label: 'Contexte', Icon: IconGlobe, glyph: '◎' },
    ],
  },
  {
    id: 'automation',
    label: 'Automatisation',
    items: [
      { to: '/app/agent', label: 'Copilot', Icon: IconChat, glyph: '✧' },
      { to: '/app/agents', label: 'Agents', Icon: IconWatchlist, glyph: '⬡' },
      { to: '/app/operations', label: 'Opérations', Icon: IconActivity, glyph: '≋' },
    ],
  },
  {
    id: 'system',
    label: 'Système',
    items: [{ to: '/app/settings', label: 'Paramètres', Icon: IconSettings, glyph: '⚙' }],
  },
]

export const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((g) => g.items)

/** Mobile tab bar — maquette + T14a : Desk · Opportunités · Portefeuille · Copilot · Plus */
export const MOBILE_PRIMARY_PATHS = new Set([
  '/app/desk',
  '/app/opportunites',
  '/app/portefeuille',
  '/app/agent',
])

export const MOBILE_PRIMARY_ITEMS = NAV_ITEMS.filter((item) =>
  MOBILE_PRIMARY_PATHS.has(item.to),
)

export const MOBILE_MORE_ITEMS = NAV_ITEMS.filter(
  (item) => !MOBILE_PRIMARY_PATHS.has(item.to),
)

/**
 * Métadonnées maquette (ichivol-studio · 11 pages) — index + sous-titre partagés.
 * Source : design-reference/ichivol-workspace `pages` array.
 */
export type WorkspacePageMeta = {
  /** Fragment maquette (#desk, #marche, …) */
  hash: string
  path: string
  label: string
  subtitle: string
  index: number
}

export const WORKSPACE_PAGES: WorkspacePageMeta[] = [
  { hash: 'desk', path: '/app/desk', label: 'Desk', subtitle: 'Votre marché, en un regard.', index: 1 },
  { hash: 'marche', path: '/app/market', label: 'Marché', subtitle: 'Lire le prix. Comprendre le mouvement.', index: 2 },
  {
    hash: 'opportunites',
    path: '/app/opportunites',
    label: 'Opportunités',
    subtitle: 'Chaque décision commence par une preuve.',
    index: 3,
  },
  {
    hash: 'portefeuille',
    path: '/app/portefeuille',
    label: 'Portefeuille',
    subtitle: 'Le capital d’abord. Le risque toujours.',
    index: 4,
  },
  {
    hash: 'lab',
    path: '/app/strategy-lab',
    label: 'Strategy Lab',
    subtitle: 'Comparer, comprendre, améliorer.',
    index: 5,
  },
  {
    hash: 'journal',
    path: '/app/journal',
    label: 'Journal',
    subtitle: 'La mémoire de vos décisions.',
    index: 6,
  },
  {
    hash: 'contexte',
    path: '/app/context',
    label: 'Contexte',
    subtitle: 'Prendre du recul sur le marché.',
    index: 7,
  },
  {
    hash: 'copilot',
    path: '/app/agent',
    label: 'Copilot',
    subtitle: 'Explorer et expliquer chaque décision.',
    index: 8,
  },
  {
    hash: 'agents',
    path: '/app/agents',
    label: 'Agents',
    subtitle: 'Une chaîne de décision sous contrôle.',
    index: 9,
  },
  {
    hash: 'operations',
    path: '/app/operations',
    label: 'Opérations',
    subtitle: 'L’activité du système, sans angle mort.',
    index: 10,
  },
  {
    hash: 'parametres',
    path: '/app/settings',
    label: 'Paramètres',
    subtitle: 'Votre environnement de travail.',
    index: 11,
  },
]

export function workspacePageMeta(path: string): WorkspacePageMeta | undefined {
  const base = path.split('?')[0]
  return WORKSPACE_PAGES.find((p) => p.path === base)
}

export function workspaceEyebrow(path: string): string {
  const meta = workspacePageMeta(path)
  if (!meta) return 'ICHIVOL WORKSPACE'
  return `${String(meta.index).padStart(2, '0')} / ICHIVOL WORKSPACE`
}

/** Legacy path → canonical (T14a redirects). */
export const LEGACY_REDIRECTS: Record<string, string> = {
  '/app/overview': '/app/desk',
  '/app/decisions': '/app/opportunites',
  '/app/activite': '/app/operations',
  '/app/synthese': '/app/portefeuille',
  '/app/paper': '/app/portefeuille?tab=positions',
  '/app/watchlist': '/app/market?filter=pinned',
}
