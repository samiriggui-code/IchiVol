export interface ChartColors {
  bull: string
  bear: string
  neutral: string
  weak: string
  tenkan: string
  kijun: string
  spanA: string
  spanB: string
  cloud: string
  grid: string
  background: string
  foreground: string
  muted: string
  border: string
}

/** ~0.28 alpha for volume bars (maquette). */
export function withAlpha(hexOrCss: string, alpha: number): string {
  const a = Math.max(0, Math.min(1, alpha))
  const hex = hexOrCss.trim()
  if (hex.startsWith('#') && (hex.length === 7 || hex.length === 4)) {
    const full =
      hex.length === 4
        ? `#${hex[1]}${hex[1]}${hex[2]}${hex[2]}${hex[3]}${hex[3]}`
        : hex
    const r = parseInt(full.slice(1, 3), 16)
    const g = parseInt(full.slice(3, 5), 16)
    const b = parseInt(full.slice(5, 7), 16)
    return `rgba(${r}, ${g}, ${b}, ${a})`
  }
  return hexOrCss
}

export function readChartColors(): ChartColors {
  const style = getComputedStyle(document.documentElement)
  const v = (name: string) => style.getPropertyValue(name).trim()
  return {
    bull: v('--bull'),
    bear: v('--bear'),
    neutral: v('--neutral'),
    weak: v('--weak'),
    tenkan: v('--tenkan'),
    kijun: v('--kijun'),
    spanA: v('--span-a'),
    spanB: v('--span-b'),
    cloud: v('--cloud') || '#d5e8df',
    grid: v('--chart-grid') || v('--border'),
    background: v('--card') || v('--background'),
    foreground: v('--foreground'),
    muted: v('--muted-foreground'),
    border: v('--border'),
  }
}
