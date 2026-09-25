import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import type { Interval, ScreenerRow, Signal } from './types'

export interface MarketSnapshot {
  symbol: string
  interval: Interval
  live: { bias: 'bull' | 'bear' | 'neutral'; rvol: number; price: number | null }
  signals: Signal[]
  rows: ScreenerRow[]
}

interface MarketSnapshotContextValue {
  snapshot: MarketSnapshot | null
  setSnapshot: (snapshot: MarketSnapshot | null) => void
}

const MarketSnapshotContext = createContext<MarketSnapshotContextValue | null>(null)

export function MarketSnapshotProvider({ children }: { children: ReactNode }) {
  const [snapshot, setSnapshot] = useState<MarketSnapshot | null>(null)
  const value = useMemo(() => ({ snapshot, setSnapshot }), [snapshot])
  return <MarketSnapshotContext.Provider value={value}>{children}</MarketSnapshotContext.Provider>
}

export function useMarketSnapshot(): MarketSnapshotContextValue {
  const ctx = useContext(MarketSnapshotContext)
  if (!ctx) throw new Error('useMarketSnapshot must be used within MarketSnapshotProvider')
  return ctx
}
