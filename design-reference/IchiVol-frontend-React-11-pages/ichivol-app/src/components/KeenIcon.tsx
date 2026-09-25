import type { HTMLAttributes } from 'react'

export type KeeniconsStyle = 'duotone' | 'outline'

export type KeenIconProps = HTMLAttributes<HTMLElement> & {
  icon: string
  style?: KeeniconsStyle
}

/** Metronic Keenicons — font icon via `ki-{style} ki-{name}`. */
export function KeenIcon({
  icon,
  style = 'outline',
  className = '',
  ...props
}: KeenIconProps) {
  const classes = [`ki-${style}`, `ki-${icon}`, className].filter(Boolean).join(' ')
  return <i className={classes} aria-hidden="true" {...props} />
}
