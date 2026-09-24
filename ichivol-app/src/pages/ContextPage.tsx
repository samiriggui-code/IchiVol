import { useEffect, useMemo, useState } from 'react'
import { CorrelationHeatmap } from '../components/CorrelationHeatmap'
import { Metric, StatLine, Tag, WorkspacePageHead } from '../components/maquette'
import {
  fetchContextCalendar,
  fetchSymbolContext,
  impactLabelFr,
  type ContextCalendarEvent,
  type SymbolContextSnapshot,
} from '../lib/contextFeeds'
import {
  fetchFearGreed,
  fetchGlobalMarket,
  type FearGreed,
  type GlobalMarketData,
} from '../lib/marketContext'
import {
  CLASS_LABELS,
  getEngineUniverse,
  type EngineAssetClass,
  type EngineInstrument,
} from '../lib/universe'

const CLASS_ORDER: EngineAssetClass[] = [
  'crypto',
  'forex',
  'metal',
  'index',
  'equity',
  'energy',
]

const FLAGSHIP: Partial<Record<EngineAssetClass, string>> = {
  crypto: 'BTCUSDT',
  forex: 'EURUSD',
  metal: 'XAUUSD',
  index: 'SPX',
  energy: 'WTI',
}

type ClassVerdict = 'PASSE' | 'PRUDENCE' | 'NEUTRE'

function regimeVolLabel(regime: string): string {
  switch (regime.toLowerCase()) {
    case 'extreme':
      return 'Élevée'
    case 'dead':
      return 'Faible'
    case 'normal':
      return 'Modérée'
    case 'unknown':
      return '—'
    default:
      return regime || '—'
  }
}

function climateFromFng(fng: FearGreed | null, market: GlobalMarketData | null): string {
  if (fng) {
    if (fng.value >= 55) return 'Tendance'
    if (fng.value <= 45) return 'Prudence'
    return 'Neutre'
  }
  if (market && market.marketCapChangePercent24h >= 1) return 'Tendance'
  if (market && market.marketCapChangePercent24h <= -1) return 'Pression'
  return 'Observation'
}

function classVerdictFromSnap(snap: SymbolContextSnapshot | null): ClassVerdict {
  if (!snap) return 'NEUTRE'
  const r = snap.atr.regime.toLowerCase()
  if (r === 'extreme') return 'PRUDENCE'
  if (r === 'dead') return 'NEUTRE'
  if (snap.rsi.bias === 'overbought' || snap.rsi.bias === 'oversold') return 'PRUDENCE'
  if (r === 'normal') return 'PASSE'
  return 'NEUTRE'
}

function verdictTone(v: ClassVerdict): 'green' | 'amber' | 'gray' {
  switch (v) {
    case 'PASSE':
      return 'green'
    case 'PRUDENCE':
      return 'amber'
    case 'NEUTRE':
      return 'gray'
    default: {
      const _exhaustive: never = v
      return _exhaustive
    }
  }
}

function fmtEventWhen(iso: string): string {
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    const now = new Date()
    const sameDay =
      d.getFullYear() === now.getFullYear() &&
      d.getMonth() === now.getMonth() &&
      d.getDate() === now.getDate()
    if (sameDay) {
      return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
    }
    const tomorrow = new Date(now)
    tomorrow.setDate(now.getDate() + 1)
    if (
      d.getFullYear() === tomorrow.getFullYear() &&
      d.getMonth() === tomorrow.getMonth() &&
      d.getDate() === tomorrow.getDate()
    ) {
      return 'Demain'
    }
    return d.toLocaleDateString('fr-FR', { weekday: 'short', day: 'numeric', month: 'short' })
  } catch {
    return iso
  }
}

function countryCode(country: string): string {
  const c = country.trim().toUpperCase()
  if (c.length <= 3) return c
  if (/united states|usa|u\.s/i.test(country)) return 'USD'
  if (/euro|ecb|germany|france|italy/i.test(country)) return 'EUR'
  if (/japan|boj/i.test(country)) return 'JPY'
  if (/uk|britain|boe/i.test(country)) return 'GBP'
  return country.slice(0, 3).toUpperCase()
}

/** Contexte — maquette `contexte()`. */
export function ContextPage() {
  const [instruments, setInstruments] = useState<EngineInstrument[]>([])
  const [market, setMarket] = useState<GlobalMarketData | null>(null)
  const [fng, setFng] = useState<FearGreed | null>(null)
  const [events, setEvents] = useState<ContextCalendarEvent[]>([])
  const [classSnaps, setClassSnaps] = useState<
    Partial<Record<EngineAssetClass, SymbolContextSnapshot | null>>
  >({})
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    void Promise.allSettled([
      getEngineUniverse(),
      fetchGlobalMarket(),
      fetchFearGreed(),
      fetchContextCalendar({ limit: 12 }),
    ]).then(async (results) => {
      if (cancelled) return
      const [uni, mkt, fear, cal] = results
      if (uni.status === 'fulfilled') setInstruments(uni.value.instruments)
      if (mkt.status === 'fulfilled') setMarket(mkt.value)
      if (fear.status === 'fulfilled') setFng(fear.value)
      if (cal.status === 'fulfilled') setEvents(cal.value)
      if (
        mkt.status === 'rejected' &&
        fear.status === 'rejected' &&
        cal.status === 'rejected'
      ) {
        setError('Contexte indisponible')
      } else {
        setError(null)
      }

      const wired = uni.status === 'fulfilled' ? uni.value.instruments : []
      const snaps: Partial<Record<EngineAssetClass, SymbolContextSnapshot | null>> = {}
      await Promise.all(
        CLASS_ORDER.map(async (cls) => {
          const flag = FLAGSHIP[cls]
          if (!flag) {
            snaps[cls] = null
            return
          }
          const ok = wired.some((i) => i.id === flag && i.wired)
          if (!ok && cls !== 'crypto') {
            snaps[cls] = null
            return
          }
          try {
            snaps[cls] = await fetchSymbolContext(flag, '1h')
          } catch {
            snaps[cls] = null
          }
        }),
      )
      if (!cancelled) {
        setClassSnaps(snaps)
        setLoading(false)
      }
    })
    return () => {
      cancelled = true
    }
  }, [])

  const btcDom = useMemo(() => {
    const hit = market?.dominance.find((d) => d.symbol.toUpperCase() === 'BTC')
    return hit?.percent ?? null
  }, [market])

  const climate = climateFromFng(fng, market)
  const volSnap = classSnaps.crypto
  const volLabel = volSnap ? regimeVolLabel(volSnap.atr.regime) : loading ? '…' : '—'
  const cryptoRegime = classVerdictFromSnap(volSnap ?? null)
  const agenda = events.slice(0, 5)

  const regimeRows = useMemo(
    () =>
      CLASS_ORDER.filter((c) => CLASS_LABELS[c]).map((cls) => ({
        cls,
        label: CLASS_LABELS[cls],
        verdict: classVerdictFromSnap(classSnaps[cls] ?? null),
      })),
    [classSnaps],
  )

  const wiredCrypto = instruments.filter((i) => i.asset_class === 'crypto' && i.wired).length

  return (
    <div>
      <WorkspacePageHead path="/app/context" />

      {error && (
        <div className="notice" role="alert">
          <span>△</span>
          <span>{error}</span>
        </div>
      )}

      <div className="metrics" aria-label="Climat & régime">
        <Metric
          label="Climat du marché"
          value={climate}
          hint={
            fng
              ? `Fear & Greed ${fng.value} · ${fng.classification}`
              : 'Lecture CoinGecko / sentiment'
          }
        />
        <Metric
          label="Dominance BTC"
          value={btcDom != null ? `${btcDom.toFixed(1)} %` : '—'}
          hint="Part de marché · CoinGecko"
        />
        <Metric label="Volatilité" value={volLabel} hint="ATR / prix · BTC" />
        <Metric
          label="Régime crypto"
          value={<Tag tone={verdictTone(cryptoRegime)}>{cryptoRegime}</Tag>}
          hint="Concentration à surveiller"
        />
      </div>

      <div className="grid">
        <section className="card" aria-label="Agenda économique">
          <div className="card-head">
            <h2>Agenda économique</h2>
            <Tag tone="gray">LIVE</Tag>
          </div>
          <div className="card-body">
            <div className="eyebrow">ÉVÉNEMENTS À VENIR</div>
            {agenda.length === 0 ? (
              <p style={{ fontSize: 12, color: 'var(--muted)' }}>
                {loading ? 'Chargement…' : 'Aucun événement macro.'}
              </p>
            ) : (
              agenda.map((e, i) => (
                <div key={`${e.date}-${e.title}-${i}`} className="session">
                  <span className="mono">{fmtEventWhen(e.date)}</span>
                  <b>{countryCode(e.country)}</b>
                  <span>{e.title}</span>
                  <Tag tone={e.impact.toLowerCase() === 'high' ? 'amber' : 'gray'}>
                    {impactLabelFr(e.impact)}
                  </Tag>
                </div>
              ))
            )}
            <p style={{ fontSize: 11, color: 'var(--muted)' }}>
              Le contexte macro éclaire la décision, sans voter dans le signal technique.
            </p>
          </div>
        </section>

        <section className="card" aria-label="Régime par classe d’actifs">
          <div className="card-head">
            <h2>Régime par classe d’actifs</h2>
          </div>
          <div className="card-body">
            {regimeRows.map((r) => (
              <StatLine
                key={r.cls}
                label={r.label}
                value={<Tag tone={verdictTone(r.verdict)}>{r.verdict}</Tag>}
              />
            ))}
          </div>
        </section>
      </div>

      <div className="grid equal">
        <CorrelationHeatmap assetClass="crypto" />
        <section className="card" aria-label="Points de vigilance">
          <div className="card-head">
            <h2>Points de vigilance</h2>
          </div>
          <div className="card-body">
            <div className="step">
              <b>Exposition corrélée</b>
              <p>
                Plusieurs positions crypto peuvent réagir au même mouvement de BTC
                {btcDom != null ? ` (dominance ${btcDom.toFixed(0)} %)` : ''}.
              </p>
            </div>
            <div className="step">
              <b>Volume inhabituel</b>
              <p>
                Un pic de volume peut accompagner un événement. Vérifier le calendrier avant
                d’agir.
              </p>
            </div>
            <div className="step">
              <b>Gap et volatilité</b>
              <p>
                {volSnap
                  ? `Régime ATR actuel : ${regimeVolLabel(volSnap.atr.regime)}. Relire le plan de risque si les conditions changent.`
                  : 'Relire le plan de risque si les conditions de marché changent.'}
                {wiredCrypto > 0 ? ` · ${wiredCrypto} paires crypto câblées.` : ''}
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
