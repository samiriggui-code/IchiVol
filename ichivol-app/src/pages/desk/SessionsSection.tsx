import { Link } from 'react-router-dom'
import { VerdictBadge } from '../../components/VerdictBadge'
import type { ScreenerDecisionRow } from '../../lib/decisions'
import type { FearGreed, GlobalMarketData } from '../../lib/marketContext'
import {
  MARKET_SESSIONS,
  formatSessionHoursLocal,
  sessionStatus,
  sessionStatusLabel,
  type MarketSessionDef,
  type SessionId,
} from '../../lib/marketSessions'
import { CardShell } from './CardShell'
import { fmtDec, fmtPct, fmtPctPoints, fmtPrice } from './deskFormat'

export function SessionsSection({
  now,
  sessionId,
  setSessionId,
  selectedSession,
  loading,
  primaryMarkets,
  changeBySymbol,
  climateError,
  market,
  fng,
}: {
  now: Date
  sessionId: SessionId
  setSessionId: (id: SessionId) => void
  selectedSession: MarketSessionDef
  loading: boolean
  primaryMarkets: ScreenerDecisionRow[]
  changeBySymbol: Record<string, number>
  climateError: string | null
  market: GlobalMarketData | null
  fng: FearGreed | null
}) {
  return (
    <div className="desk-overview iv-animate-in-delay">
      <CardShell title="Sessions de marché" meta="Horaires locaux · crypto 24/7">
        <div className="world-view">
          <img src="/world-map.svg" alt="" width={720} height={290} />
          {MARKET_SESSIONS.map((s) => {
            const st = sessionStatus(s, now)
            return (
              <button
                key={s.id}
                type="button"
                className={`map-marker${sessionId === s.id ? ' selected' : ''}`}
                style={{ left: `${s.mapLeftPct}%`, top: `${s.mapTopPct}%` }}
                aria-label={`Session ${s.city}`}
                aria-pressed={sessionId === s.id}
                onClick={() => setSessionId(s.id)}
              >
                <span className={`is-${st}`} />
                <b>{s.city}</b>
              </button>
            )
          })}
        </div>
        <div className="session-selector">
          {MARKET_SESSIONS.map((s) => {
            const st = sessionStatus(s, now)
            return (
              <button
                key={s.id}
                type="button"
                className={sessionId === s.id ? 'active' : undefined}
                aria-pressed={sessionId === s.id}
                onClick={() => setSessionId(s.id)}
              >
                {s.region}
                <small className={`session-status is-${st}`}>{sessionStatusLabel(st)}</small>
              </button>
            )
          })}
        </div>
        <div className="session-detail" id="desk-session-detail">
          <strong>
            {selectedSession.city}{' '}
            <span className={`session-status is-${sessionStatus(selectedSession, now)}`}>
              {sessionStatusLabel(sessionStatus(selectedSession, now))}
            </span>
          </strong>
          <span className="mono">{formatSessionHoursLocal(selectedSession, now)}</span>
        </div>
        <p className="map-foot muted">
          Crypto <b>24/7</b> · sessions FX fermées le week-end
        </p>
      </CardShell>

      <CardShell
        title="Marchés principaux"
        footer={
          <Link to="/app/market" className="link">
            Tout le marché ↗
          </Link>
        }
      >
        {loading && !primaryMarkets.length ? (
          <p className="muted">Chargement…</p>
        ) : !primaryMarkets.length ? (
          <p className="muted">Aucun ticker screener.</p>
        ) : (
          <div className="desk-tickers">
            {primaryMarkets.map((r) => (
              <Link
                key={r.symbol}
                className="desk-ticker"
                to={`/app/market?symbol=${encodeURIComponent(r.symbol)}`}
              >
                <span>
                  <b>
                    {r.symbol.replace(/USDT$/i, '')}
                    <small className="desk-quote"> / USDT</small>
                  </b>
                  <small>
                    <VerdictBadge decision={r.decision} pipeline={r.pipeline} hideDiagnostic />
                  </small>
                </span>
                <span className="right">
                  <b className="mono">{fmtPrice(r.price)}</b>
                  {(() => {
                    const chg = changeBySymbol[r.symbol.toUpperCase()]
                    if (chg == null || Number.isNaN(chg)) {
                      return (
                        <small className="muted">
                          {r.rvol != null
                            ? `RVOL ${fmtDec(r.rvol, 2)}×`
                            : `conf ${fmtPct(r.confidence, 0, false)}`}
                        </small>
                      )
                    }
                    const tone = chg > 0 ? 'is-up' : chg < 0 ? 'is-down' : ''
                    return (
                      <small className={`mono desk-chg ${tone}`.trim()}>
                        {fmtPctPoints(chg, 2, true)}
                      </small>
                    )
                  })()}
                </span>
              </Link>
            ))}
          </div>
        )}
      </CardShell>

      <CardShell title="Lecture du marché">
        {climateError && !market ? (
          <p className="muted">{climateError}</p>
        ) : loading && !market && !fng ? (
          <p className="muted">Chargement…</p>
        ) : !market && !fng ? (
          <p className="muted">Climat crypto indisponible.</p>
        ) : (
          <div className="desk-climate">
            {fng ? (
              <div className="climate-head">
                <span className="climate-symbol" aria-hidden>
                  {fng.value >= 55 ? '↗' : fng.value <= 45 ? '↘' : '→'}
                </span>
                <div>
                  <small>SENTIMENT (FEAR &amp; GREED)</small>
                  <h3>{fng.classification}</h3>
                </div>
              </div>
            ) : null}
            {market ? (
              <dl className="desk-climate-stats">
                <div>
                  <dt>Capitalisation crypto 24h</dt>
                  <dd className={market.marketCapChangePercent24h >= 0 ? 'up' : 'down'}>
                    {fmtPctPoints(market.marketCapChangePercent24h, 2, true)}
                  </dd>
                </div>
                {(() => {
                  const btc = market.dominance.find((d) => d.symbol.toUpperCase() === 'BTC')
                  if (!btc) return null
                  return (
                    <div>
                      <dt>Dominance BTC</dt>
                      <dd className="mono">{fmtPctPoints(btc.percent, 1, false)}</dd>
                    </div>
                  )
                })()}
              </dl>
            ) : null}
            <Link to="/app/context" className="link">
              Ouvrir le contexte ↗
            </Link>
          </div>
        )}
      </CardShell>
    </div>
  )
}
