/** Types for GET /api/engine/structure/{symbol} (raw engine payload).

Selection / overlay mapping moved to ChartObjects (T2a): see ``chartObjects.ts``
and engine ``structure_to_chart_objects``. Kept for typed access to the raw
structure API if needed by tools / debugging.
*/

export interface StructureZone {
  side: 'support' | 'resistance'
  low: number
  high: number
  mid: number
  score: number
  touch_count: number
}

export interface StructureTrendline {
  side: 'support' | 'resistance'
  score: number
  touch_count: number
  source: string
  start_time?: number
  end_time?: number
  start_price?: number
  end_price?: number
}

export interface EngineStructure {
  consensus: {
    structure_score: number
    support_zones: StructureZone[]
    resistance_zones: StructureZone[]
  }
  detectors: Record<
    string,
    {
      support_trendlines: StructureTrendline[]
      resistance_trendlines: StructureTrendline[]
    }
  >
}
