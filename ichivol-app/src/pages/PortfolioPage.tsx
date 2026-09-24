import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Card,
  Metric,
  RiskTrack,
  StatLine,
  Tag,
  WorkspacePageHead,
} from '../components/maquette'
import {
  getPaperOverview,
  type PaperOverview,
  type PaperOverviewPosition,
} from '../lib/paper'
import { PaperPage } from './PaperPage'

const BASELINE = 'ICHIVOL_BASELINE_V1'

function fmtPct(v: number | null | undefined, digits = 1): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return `${(v * 100).toFixed(digits)} %`
}

function fmtMoney(v: number | null | undefined, digits = 2): string {
  if (v == null || !Number.isFinite(v)) return '—'
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(v)
}

function displaySymbol(symbol: string): string {
  return symbol.replace(/USDT$/i, '').replace(/USD$/i, '')
}

function positionNotional(p: PaperOverviewPosition): number {
  if (p.market_value != null && Number.isFinite(p.market_value)) return Math.abs(p.market_value)
  if (p.notional != null && Number.isFinite(p.notional)) return Math.abs(p.notional)
  return 0
}

/** Portefeuille — maquette `portefeuille()`. */
export function PortfolioPage() {
  const [params] = useSearchParams()
  const detailTab = params.get('tab') === 'positions' || params.get('tab') === 'paper'
  const [overview, setOverview] = useState<PaperOverview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(() => {
    setLoading(true)
    getPaperOverview(BASELINE)
      .then((ov) => {
        setOverview(ov)
        setError(null)
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Portefeuille indisponible')
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const acct = overview?.account
  const risk = overview?.risk
  const openBook = useMemo(
    () => (overview?.positions ?? []).filter((p) => p.status === 'OPEN'),
    [overview],
  )

  const exposed = risk?.exposed ?? acct?.invested ?? 0
  const capital = risk?.capital ?? acct?.equity ?? 0
  const cash = risk?.cash ?? acct?.cash ?? 0
  const exposedShare = capital > 0 ? exposed / capital : null
  const drawdown = overview?.progress?.max_drawdown_pct ?? null

  const riskTracks = useMemo(() => {
    const openRiskPct = risk?.open_risk_pct ?? null
    const maxOpenRisk = risk?.max_open_risk_pct ?? 0.03
    const maxPositions = risk?.max_open_positions ?? 6
    const openPositions = risk?.open_positions ?? openBook.length
    const exposurePct = exposedShare ?? 0
    const exposureCap = 0.4
    return [
      {
        label: 'Risque par trade',
        value:
          openRiskPct != null && openPositions > 0
            ? `${((openRiskPct / Math.max(openPositions, 1)) * 100).toFixed(1)} / ${(maxOpenRisk * 100).toFixed(0)} %`
            : `— / ${(maxOpenRisk * 100).toFixed(0)} %`,
        pct:
          openRiskPct != null && openPositions > 0
            ? Math.min(100, ((openRiskPct / Math.max(openPositions, 1)) / maxOpenRisk) * 100)
            : 0,
      },
      {
        label: 'Risque par jour',
        value:
          openRiskPct != null
            ? `${(openRiskPct * 100).toFixed(1)} / ${(maxOpenRisk * 100).toFixed(0)} %`
            : `— / ${(maxOpenRisk * 100).toFixed(0)} %`,
        pct: openRiskPct != null ? Math.min(100, (openRiskPct / maxOpenRisk) * 100) : 0,
        warn: openRiskPct != null && openRiskPct > maxOpenRisk * 0.85,
      },
      {
        label: 'Exposition globale',
        value: `${(exposurePct * 100).toFixed(1)} / ${(exposureCap * 100).toFixed(0)} %`,
        pct: Math.min(100, (exposurePct / exposureCap) * 100),
        warn: exposurePct > exposureCap * 0.85,
      },
      {
        label: 'Positions simultanées',
        value: `${openPositions} / ${maxPositions}`,
        pct: maxPositions > 0 ? Math.min(100, (openPositions / maxPositions) * 100) : 0,
        warn: openPositions >= maxPositions,
      },
    ]
  }, [risk, openBook.length, exposedShare])

  const verdictPass =
    risk == null || (risk.open_risk_pct ?? 0) <= (risk.max_open_risk_pct ?? 1)

  const concentration = useMemo(() => {
    const total = openBook.reduce((s, p) => s + positionNotional(p), 0)
    if (total <= 0) return []
    return [...openBook]
      .map((p) => ({
        symbol: displaySymbol(p.symbol),
        pct: (positionNotional(p) / total) * 100,
      }))
      .sort((a, b) => b.pct - a.pct)
      .slice(0, 6)
  }, [openBook])

  if (detailTab) {
    return (
      <div>
        <WorkspacePageHead
          path="/app/portefeuille"
          subtitleExtra={
            <>
              {' '}
              · <Link to="/app/portefeuille" className="link">Vue synthèse</Link>
            </>
          }
        />
        <PaperPage />
      </div>
    )
  }

  return (
    <div>
      <WorkspacePageHead
        path="/app/portefeuille"
        actions={
          <>
            <Link to="/app/portefeuille?tab=positions" className="link">
              Détail positions →
            </Link>
            <button type="button" onClick={() => load()} disabled={loading}>
              {loading ? '…' : 'Actualiser'}
            </button>
          </>
        }
      />

      {error && (
        <div className="notice" role="alert">
          <span>△</span>
          <span>{error}</span>
        </div>
      )}

      <div className="metrics" aria-label="Capital & exposition">
        <Metric label="Capital" value={fmtMoney(capital)} hint="Portefeuille paper" />
        <Metric
          label="Exposition"
          value={fmtMoney(exposed)}
          hint={
            exposedShare != null
              ? `${(exposedShare * 100).toFixed(1)} % du capital`
              : 'Capital engagé'
          }
        />
        <Metric label="Disponible" value={fmtMoney(cash)} hint="Réserve non engagée" />
        <Metric
          label="Drawdown"
          value={drawdown != null ? `−${drawdown.toFixed(1)} %` : '—'}
          hint="Depuis le plus haut"
          tone={drawdown != null && drawdown > 0 ? 'down' : ''}
        />
      </div>

      <div className="grid">
        <section className="card" aria-label="Risk Kernel">
          <div className="card-head">
            <h2>Risk Kernel</h2>
            <Tag tone={verdictPass ? 'green' : 'red'}>{verdictPass ? 'PASSE' : 'REFUSÉ'}</Tag>
          </div>
          <div className="card-body">
            <div style={{ display: 'flex', alignItems: 'center', gap: 20, padding: '10px 0 22px' }}>
              <span
                style={{
                  font: '42px Newsreader, Georgia, serif',
                  color: verdictPass ? 'var(--green)' : 'var(--red)',
                }}
              >
                {verdictPass ? 'PASSE' : 'REFUSÉ'}
              </span>
              <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                Verdict Risk Kernel
                <br />
                {openBook.length} position{openBook.length === 1 ? '' : 's'} sous surveillance
              </span>
            </div>
            {riskTracks.map((t) => (
              <RiskTrack key={t.label} {...t} />
            ))}
          </div>
        </section>

        <section className="card" aria-label="Allocation du capital">
          <div className="card-head">
            <h2>Allocation du capital</h2>
            <Tag tone="gray">CRYPTO SPOT</Tag>
          </div>
          <div className="card-body">
            <div
              className="donut"
              style={
                exposedShare != null
                  ? {
                      background: `conic-gradient(#347d78 0 ${exposedShare * 100}%, #e9e6df ${exposedShare * 100}% 100%)`,
                    }
                  : undefined
              }
              aria-hidden
            />
            {/* CSS :before shows fixed 27.8% — override via overlay text when live */}
            <StatLine label="Capital engagé" value={fmtMoney(exposed)} />
            <StatLine label="Liquidités" value={fmtMoney(cash)} />
            {exposedShare != null && (
              <p style={{ fontSize: 11, color: 'var(--muted)', textAlign: 'center' }}>
                {(exposedShare * 100).toFixed(1)} % engagé
              </p>
            )}
          </div>
        </section>
      </div>

      <section className="card" aria-label="Positions ouvertes">
        <div className="card-head">
          <h2>Positions ouvertes</h2>
          <Tag tone="gray">
            {openBook.length} POSITION{openBook.length === 1 ? '' : 'S'}
          </Tag>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ACTIF / STRATÉGIE</th>
                <th>ENGAGÉ</th>
                <th>PERFORMANCE</th>
                <th>P&L LATENT</th>
                <th>ÉTAT</th>
              </tr>
            </thead>
            <tbody>
              {openBook.map((p) => (
                <tr key={p.id} className="clickable">
                  <td>
                    <b>{displaySymbol(p.symbol)}</b>
                    <small>Ichimoku × RVOL · {p.timeframe}</small>
                  </td>
                  <td>
                    <span className="mono">{fmtMoney(positionNotional(p))}</span>
                  </td>
                  <td>
                    <span
                      className={`mono${
                        p.unrealized_pct != null && p.unrealized_pct !== 0
                          ? p.unrealized_pct > 0
                            ? ' up'
                            : ' down'
                          : ''
                      }`}
                    >
                      {fmtPct(p.unrealized_pct)}
                    </span>
                  </td>
                  <td>
                    <span
                      className={`mono${
                        p.unrealized_pnl != null && p.unrealized_pnl !== 0
                          ? p.unrealized_pnl > 0
                            ? ' up'
                            : ' down'
                          : ''
                      }`}
                    >
                      {fmtMoney(p.unrealized_pnl)}
                    </span>
                  </td>
                  <td>
                    <Tag>OUVERTE</Tag>
                  </td>
                </tr>
              ))}
              {!loading && openBook.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', color: 'var(--muted)' }}>
                    Aucune position ouverte.
                  </td>
                </tr>
              )}
              {loading && openBook.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', color: 'var(--muted)' }}>
                    Chargement…
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <div style={{ height: 20 }} aria-hidden />

      <Card
        title="Concentration des positions"
        extra={
          <Tag tone={concentration.length >= 3 ? 'amber' : 'gray'}>
            {concentration.length >= 3 ? 'PRUDENCE' : String(concentration.length)}
          </Tag>
        }
      >
        {concentration.length === 0 ? (
          <p style={{ fontSize: 12, color: 'var(--muted)' }}>Pas d’exposition ouverte.</p>
        ) : (
          concentration.map((c) => (
            <RiskTrack
              key={c.symbol}
              label={c.symbol}
              value={`${c.pct.toFixed(1)} % de l’exposition`}
              pct={c.pct}
            />
          ))
        )}
        <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 12 }}>
          {concentration.length >= 2
            ? 'Plusieurs actifs : surveiller leur corrélation avant d’ajouter une position.'
            : 'Exposition paper baseline.'}
        </p>
      </Card>

    </div>
  )
}
