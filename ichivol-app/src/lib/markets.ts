import { WATCHLIST } from './binance'
import type { ExchangeId } from './sources/types'

/** Classes d’actifs visibles sur Marché (feeds data publics — pas de broker). */
export type MarketClassId = 'crypto' | 'metals' | 'equities'

export type SpecialtyId =
  | 'crypto_majors'
  | 'crypto_alts'
  | 'crypto_memes'
  | 'metals_gold'
  | 'equities_us'
  | 'equities_etf'

export interface MarketInstrument {
  symbol: string
  /** Libellé court (BTC, Or PAXG, Tesla…) */
  label: string
  /** Sous-titre (USDT, tokenisé…) */
  hint?: string
}

export interface SpecialtyDef {
  id: SpecialtyId
  label: string
  classId: MarketClassId
  instruments: MarketInstrument[]
}

export interface MarketClassDef {
  id: MarketClassId
  label: string
  blurb: string
  /** Sources qui listent typiquement cet univers en public. */
  preferredSources: ExchangeId[]
  specialties: SpecialtyId[]
}

const CRYPTO_MAJORS: MarketInstrument[] = [
  { symbol: 'BTCUSDT', label: 'BTC' },
  { symbol: 'ETHUSDT', label: 'ETH' },
  { symbol: 'BNBUSDT', label: 'BNB' },
  { symbol: 'SOLUSDT', label: 'SOL' },
  { symbol: 'XRPUSDT', label: 'XRP' },
]

const CRYPTO_ALTS: MarketInstrument[] = [
  { symbol: 'ADAUSDT', label: 'ADA' },
  { symbol: 'AVAXUSDT', label: 'AVAX' },
  { symbol: 'LINKUSDT', label: 'LINK' },
  { symbol: 'DOTUSDT', label: 'DOT' },
  { symbol: 'LTCUSDT', label: 'LTC' },
  { symbol: 'ATOMUSDT', label: 'ATOM' },
  { symbol: 'UNIUSDT', label: 'UNI' },
  { symbol: 'NEARUSDT', label: 'NEAR' },
  { symbol: 'APTUSDT', label: 'APT' },
  { symbol: 'ARBUSDT', label: 'ARB' },
  { symbol: 'OPUSDT', label: 'OP' },
  { symbol: 'SUIUSDT', label: 'SUI' },
  { symbol: 'TONUSDT', label: 'TON' },
]

const CRYPTO_MEMES: MarketInstrument[] = [
  { symbol: 'DOGEUSDT', label: 'DOGE' },
  { symbol: 'PEPEUSDT', label: 'PEPE' },
]

/** Or tokenisé (pas de lingot LME). */
const METALS_GOLD: MarketInstrument[] = [
  { symbol: 'PAXGUSDT', label: 'PAXG', hint: 'Or · Paxos' },
  { symbol: 'XAUTUSDT', label: 'XAUT', hint: 'Or · Tether' },
]

/** Actions / ETF tokenisés Binance (*B) — pas le titre coté NYSE. */
const EQUITIES_US: MarketInstrument[] = [
  { symbol: 'TSLABUSDT', label: 'TSLA', hint: 'tokenisé' },
  { symbol: 'AAPLBUSDT', label: 'AAPL', hint: 'tokenisé' },
  { symbol: 'NVDABUSDT', label: 'NVDA', hint: 'tokenisé' },
  { symbol: 'MSFTBUSDT', label: 'MSFT', hint: 'tokenisé' },
  { symbol: 'GOOGLBUSDT', label: 'GOOGL', hint: 'tokenisé' },
  { symbol: 'METABUSDT', label: 'META', hint: 'tokenisé' },
  { symbol: 'AMDBUSDT', label: 'AMD', hint: 'tokenisé' },
  { symbol: 'PLTRBUSDT', label: 'PLTR', hint: 'tokenisé' },
  { symbol: 'COINBUSDT', label: 'COIN', hint: 'tokenisé' },
  { symbol: 'MSTRBUSDT', label: 'MSTR', hint: 'tokenisé' },
]

const EQUITIES_ETF: MarketInstrument[] = [
  { symbol: 'SPYBUSDT', label: 'SPY', hint: 'ETF tokenisé' },
  { symbol: 'QQQBUSDT', label: 'QQQ', hint: 'ETF tokenisé' },
]

export const SPECIALTIES: Record<SpecialtyId, SpecialtyDef> = {
  crypto_majors: {
    id: 'crypto_majors',
    label: 'Majors',
    classId: 'crypto',
    instruments: CRYPTO_MAJORS,
  },
  crypto_alts: {
    id: 'crypto_alts',
    label: 'Alts',
    classId: 'crypto',
    instruments: CRYPTO_ALTS,
  },
  crypto_memes: {
    id: 'crypto_memes',
    label: 'Memes',
    classId: 'crypto',
    instruments: CRYPTO_MEMES,
  },
  metals_gold: {
    id: 'metals_gold',
    label: 'Or tokenisé',
    classId: 'metals',
    instruments: METALS_GOLD,
  },
  equities_us: {
    id: 'equities_us',
    label: 'Actions US',
    classId: 'equities',
    instruments: EQUITIES_US,
  },
  equities_etf: {
    id: 'equities_etf',
    label: 'ETF',
    classId: 'equities',
    instruments: EQUITIES_ETF,
  },
}

export const MARKET_CLASSES: MarketClassDef[] = [
  {
    id: 'crypto',
    label: 'Crypto',
    blurb: 'Spot crypto via feeds publics (Vision / Bybit / OKX). IchiVol ne trade sur aucun CEX.',
    preferredSources: ['binance', 'bybit', 'okx'],
    specialties: ['crypto_majors', 'crypto_alts', 'crypto_memes'],
  },
  {
    id: 'metals',
    label: 'Métaux',
    blurb: 'Or via tokens spot (PAXG / XAUT) — pas de métaux physiques LME.',
    preferredSources: ['binance'],
    specialties: ['metals_gold'],
  },
  {
    id: 'equities',
    label: 'Actions',
    blurb: 'Actions & ETF tokenisés Binance — pas le titre coté classique.',
    preferredSources: ['binance'],
    specialties: ['equities_us', 'equities_etf'],
  },
]

export const DEFAULT_MARKET_CLASS: MarketClassId = 'crypto'
export const DEFAULT_SPECIALTY: SpecialtyId = 'crypto_majors'

/** Univers crypto historique (engine / backtests) — inchangé. */
export const CRYPTO_WATCHLIST = WATCHLIST

export function getClass(id: MarketClassId): MarketClassDef {
  const found = MARKET_CLASSES.find((c) => c.id === id)
  if (!found) throw new Error(`Unknown market class: ${id}`)
  return found
}

export function getSpecialty(id: SpecialtyId): SpecialtyDef {
  return SPECIALTIES[id]
}

export function defaultSpecialtyFor(classId: MarketClassId): SpecialtyId {
  return getClass(classId).specialties[0]
}

export function instrumentsFor(specialtyId: SpecialtyId): MarketInstrument[] {
  return SPECIALTIES[specialtyId].instruments
}

export function symbolsFor(specialtyId: SpecialtyId): string[] {
  return instrumentsFor(specialtyId).map((i) => i.symbol)
}

export function findInstrument(symbol: string): MarketInstrument | undefined {
  for (const spec of Object.values(SPECIALTIES)) {
    const hit = spec.instruments.find((i) => i.symbol === symbol)
    if (hit) return hit
  }
  return undefined
}

export function displaySymbol(symbol: string): string {
  return findInstrument(symbol)?.label ?? symbol.replace(/USDT$/i, '')
}

export function sourceSupportsClass(sourceId: ExchangeId, classId: MarketClassId): boolean {
  return getClass(classId).preferredSources.includes(sourceId)
}
