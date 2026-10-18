import type { ReactNode } from 'react'

type IconProps = { className?: string }

/** Icônes au trait de la maquette premium (24×24, trait 1,6, couleur = currentColor). */
function Svg({ className, children }: IconProps & { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={['iv-icon', className].filter(Boolean).join(' ')}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      focusable="false"
    >
      {children}
    </svg>
  )
}

export function IconOverview({ className }: IconProps) {
  return (
    <Svg className={className}>
      <rect x="3" y="3" width="7.5" height="9" rx="1.5" />
      <rect x="13.5" y="3" width="7.5" height="5" rx="1.5" />
      <rect x="13.5" y="11" width="7.5" height="10" rx="1.5" />
      <rect x="3" y="15" width="7.5" height="6" rx="1.5" />
    </Svg>
  )
}

export function IconMarket({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M7 3v4M7 17v4M17 5v3M17 16v4" />
      <rect x="4.5" y="7" width="5" height="10" rx="1" />
      <rect x="14.5" y="8" width="5" height="8" rx="1" />
    </Svg>
  )
}

export function IconGlobe({ className }: IconProps) {
  return (
    <Svg className={className}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M3.5 12h17M12 3.5c2.5 2.6 3.5 5.4 3.5 8.5s-1 5.9-3.5 8.5c-2.5-2.6-3.5-5.4-3.5-8.5s1-5.9 3.5-8.5z" />
    </Svg>
  )
}

export function IconDecisions({ className }: IconProps) {
  return (
    <Svg className={className}>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="4.5" />
      <circle cx="12" cy="12" r="0.8" />
    </Svg>
  )
}

export function IconPaper({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M3.5 7.5h15a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z" />
      <path d="M3.5 7.5V6a2 2 0 0 1 2-2h10.5v3.5" />
      <path d="M15.5 13.5h5" />
    </Svg>
  )
}

export function IconSynthese({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M12 3.5a8.5 8.5 0 1 0 8.5 8.5H12z" />
      <path d="M15 3.9A8.5 8.5 0 0 1 20.1 9H15z" />
    </Svg>
  )
}

export function IconJournal({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5z" />
      <path d="M5 19.5A1.5 1.5 0 0 0 6.5 21H19v-3" />
      <path d="M9 7.5h6M9 11h4" />
    </Svg>
  )
}

export function IconWatchlist({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="m12 3.8 2.5 5.1 5.6.8-4 4 .9 5.6-5-2.7-5 2.7.9-5.6-4-4 5.6-.8z" />
    </Svg>
  )
}

export function IconActivity({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M3 12h4l2.5-6 5 12 2.5-6h4" />
    </Svg>
  )
}

export function IconBacktests({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M9.5 3h5M10.5 3v6L5 18.5A1.7 1.7 0 0 0 6.5 21h11a1.7 1.7 0 0 0 1.5-2.5L13.5 9V3" />
      <path d="M7.5 15h9" />
    </Svg>
  )
}

export function IconSettings({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M4 7h9M17 7h3M4 17h3M11 17h9" />
      <circle cx="15" cy="7" r="2" />
      <circle cx="9" cy="17" r="2" />
    </Svg>
  )
}

export function IconChevronLeft({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="m14.5 6-6 6 6 6" />
    </Svg>
  )
}

export function IconBell({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 2h-15z" />
      <path d="M10 20.5a2 2 0 0 0 4 0" />
    </Svg>
  )
}

export function IconChat({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v9a1.5 1.5 0 0 1-1.5 1.5H10l-4.5 4v-4A1.5 1.5 0 0 1 4 14.5z" />
      <path d="M8.5 9h7M8.5 12h4.5" />
    </Svg>
  )
}

export function IconMenu({ className }: IconProps) {
  return (
    <Svg className={className}>
      <circle cx="5.5" cy="12" r="1.2" />
      <circle cx="12" cy="12" r="1.2" />
      <circle cx="18.5" cy="12" r="1.2" />
    </Svg>
  )
}

export function IconClose({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M6 6l12 12M18 6 6 18" />
    </Svg>
  )
}

/** Ève : losange double, comme le logo. */
export function IconAgents({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M12 2.8 21.2 12 12 21.2 2.8 12z" />
      <path d="M12 8 16 12 12 16 8 12z" />
    </Svg>
  )
}
