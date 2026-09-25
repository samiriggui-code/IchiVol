type BrandMarkProps = {
  className?: string
}

/** Logo IchiVol — même SVG que le favicon (`/favicon.svg`). */
export function BrandMark({ className }: BrandMarkProps) {
  return (
    <img
      src="/favicon.svg"
      alt=""
      className={className}
      width={32}
      height={32}
      decoding="async"
      aria-hidden
    />
  )
}
