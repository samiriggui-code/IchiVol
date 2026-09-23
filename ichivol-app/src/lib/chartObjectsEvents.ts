/** Lightweight bus: Copilot chart writes → Market chart refetch (T2b). */

export const CHART_OBJECTS_CHANGED_EVENT = 'ichivol:chart-objects-changed'

const CHART_MUTATING_TOOLS = /^(draw_|delete_chart_object)/

export function isChartMutatingTool(name: string): boolean {
  return CHART_MUTATING_TOOLS.test(name)
}

export function notifyChartObjectsChanged(detail?: { tool?: string; ok?: boolean }): void {
  if (typeof window === 'undefined') return
  window.dispatchEvent(
    new CustomEvent(CHART_OBJECTS_CHANGED_EVENT, { detail: detail ?? {} }),
  )
}

export function onChartObjectsChanged(handler: () => void): () => void {
  if (typeof window === 'undefined') return () => {}
  const listener = () => handler()
  window.addEventListener(CHART_OBJECTS_CHANGED_EVENT, listener)
  return () => window.removeEventListener(CHART_OBJECTS_CHANGED_EVENT, listener)
}
