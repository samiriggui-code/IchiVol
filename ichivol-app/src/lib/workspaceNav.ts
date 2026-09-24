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
} from '../components/NavIcons'

export type NavItem = {
  to: string
  label: string
  Icon: ComponentType<{ className?: string }>
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
      { to: '/app/desk', label: 'Desk', Icon: IconOverview },
      { to: '/app/market', label: 'Marché', Icon: IconMarket },
      { to: '/app/opportunites', label: 'Opportunités', Icon: IconDecisions },
      { to: '/app/portefeuille', label: 'Portefeuille', Icon: IconPaper },
    ],
  },
  {
    id: 'research',
    label: 'Recherche',
    items: [
      { to: '/app/strategy-lab', label: 'Strategy Lab', Icon: IconBacktests },
      { to: '/app/journal', label: 'Journal', Icon: IconJournal },
      { to: '/app/context', label: 'Contexte', Icon: IconGlobe },
    ],
  },
  {
    id: 'automation',
    label: 'Automatisation',
    items: [
      { to: '/app/agent', label: 'Copilot', Icon: IconChat },
      { to: '/app/operations', label: 'Opérations', Icon: IconActivity },
    ],
  },
  {
    id: 'system',
    label: 'Système',
    items: [{ to: '/app/settings', label: 'Paramètres', Icon: IconSettings }],
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

/** Legacy path → canonical (T14a redirects). */
export const LEGACY_REDIRECTS: Record<string, string> = {
  '/app/overview': '/app/desk',
  '/app/decisions': '/app/opportunites',
  '/app/activite': '/app/operations',
  '/app/synthese': '/app/portefeuille',
  '/app/paper': '/app/portefeuille?tab=positions',
  '/app/watchlist': '/app/market?filter=pinned',
}
