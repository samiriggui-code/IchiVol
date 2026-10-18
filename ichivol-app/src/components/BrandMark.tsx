type BrandMarkProps = {
  className?: string
}

/** Logo IchiVol de la maquette premium : losange cyan, cœur ambre (couleurs = jetons du thème). */
export function BrandMark({ className }: BrandMarkProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} width={32} height={32} aria-hidden focusable="false">
      <path d="M12 1.5 22.5 12 12 22.5 1.5 12z" fill="none" stroke="var(--cyan)" strokeWidth={1.4} />
      <path d="M12 7l5 5-5 5-5-5z" fill="var(--amber)" />
    </svg>
  )
}
