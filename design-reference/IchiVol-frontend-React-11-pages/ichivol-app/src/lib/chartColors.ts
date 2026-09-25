export interface ChartColors {
  bull: string
  bear: string
  neutral: string
  weak: string
  tenkan: string
  kijun: string
  spanA: string
  spanB: string
  background: string
  foreground: string
  muted: string
  border: string
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
    background: v('--background'),
    foreground: v('--foreground'),
    muted: v('--muted-foreground'),
    border: v('--border'),
  }
}
