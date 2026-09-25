import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AgentPanel } from '../components/AgentPanel'
import { useAgentSession } from '../lib/agentSession'
import {
  getAgentCapabilities,
  mapCapabilityBadges,
  type CapabilityBadge,
} from '../lib/agentCapabilities'
import { getActivityFeed, type ActivityItem } from '../lib/activity'
import { getScreener, type ScreenerDecisionRow } from '../lib/decisions'
import { verdictBucket } from '../lib/deskSummarize'
import { useMarketSnapshot } from '../lib/marketSnapshot'
import { getPaperOverview, type PaperOverviewPosition } from '../lib/paper'

interface CopilotSuggestion {
  id: string
  label: string
  prompt: string
  symbol?: string
}

function bestBuySellRow(rows: ScreenerDecisionRow[]): ScreenerDecisionRow | null {
  let best: ScreenerDecisionRow | null = null
  let bestScore = -1
  for (const row of rows) {
    const bucket = verdictBucket(row)
    if (bucket !== 'buy' && bucket !== 'sell') continue
    const score = Number.isFinite(row.confidence) ? row.confidence : 0
    if (score > bestScore) {
      best = row
      bestScore = score
    }
  }
  return best
}

function latestRefusal(items: ActivityItem[]): ActivityItem | null {
  for (const it of items) {
    if (it.kind === 'shadow_blocked') return it
  }
  return null
}

function firstOpenPosition(positions: PaperOverviewPosition[]): PaperOverviewPosition | null {
  return positions.find((p) => String(p.status).toUpperCase() === 'OPEN') ?? null
}

function buildSuggestions(ctx: {
  screenerRow: ScreenerDecisionRow | null
  refusal: ActivityItem | null
  position: PaperOverviewPosition | null
}): CopilotSuggestion[] {
  const out: CopilotSuggestion[] = []
  if (ctx.screenerRow) {
    const r = ctx.screenerRow
    const bucket = verdictBucket(r)
    const side = bucket === 'buy' ? 'BUY' : 'SELL'
    out.push({
      id: `screener-${r.symbol}`,
      label: `Pourquoi ${r.symbol} est en ${side} ?`,
      prompt:
        `Explique pourquoi ${r.symbol} (${r.timeframe}) est classé ${side} ` +
        `(confiance ${(r.confidence * 100).toFixed(0)} %). ` +
        `Appuie-toi sur les portes / le contexte moteur. Ne propose pas un autre sens.`,
      symbol: r.symbol,
    })
  }
  if (ctx.refusal) {
    const it = ctx.refusal
    out.push({
      id: `refusal-${it.symbol}-${it.time}`,
      label: `Explique le refus ${it.symbol}`,
      prompt:
        `Explique le refus / blocage shadow sur ${it.symbol}.\n` +
        `• Titre : ${it.title}\n` +
        `• Détail : ${it.detail}\n` +
        `Clarifie ce qui a bloqué et ce qu’il faudrait pour débloquer — sans voter une direction.`,
      symbol: it.symbol,
    })
  }
  if (ctx.position) {
    const p = ctx.position
    out.push({
      id: `position-${p.id}`,
      label: `Risque de la position ${p.symbol}`,
      prompt:
        `Analyse la position paper ouverte ${p.symbol} (${p.direction}). ` +
        `Explique le risque, les invalidations possibles et ce que le moteur surveille. ` +
        `Ne propose pas d’ordre sans confirmation humaine.`,
      symbol: p.symbol,
    })
  }
  return out.slice(0, 3)
}

/**
 * Agent Claude : il interroge le moteur en lecture seule (outils) puis explique.
 */
export function AgentPage() {
  const { snapshot } = useMarketSnapshot()
  const { decisionPayload, assumedSymbol, assumedTimeframe, launch, queueLaunch } = useAgentSession()
  const [badges, setBadges] = useState<CapabilityBadge[]>(() => mapCapabilityBadges(null))
  const [capsError, setCapsError] = useState<string | null>(null)
  const [suggestions, setSuggestions] = useState<CopilotSuggestion[]>([])

  const symbol =
    launch?.decision?.symbol ??
    launch?.live?.symbol ??
    assumedSymbol ??
    decisionPayload?.symbol ??
    snapshot?.symbol ??
    null
  const timeframe =
    launch?.decision?.timeframe ??
    launch?.live?.interval ??
    assumedTimeframe ??
    decisionPayload?.timeframe ??
    snapshot?.interval ??
    '1h'

  const hasSession = Boolean(symbol)

  useEffect(() => {
    let cancelled = false
    getAgentCapabilities()
      .then((caps) => {
        if (!cancelled) {
          setBadges(mapCapabilityBadges(caps))
          setCapsError(null)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setBadges(mapCapabilityBadges(null))
          setCapsError(err instanceof Error ? err.message : 'Capacités indisponibles')
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    Promise.all([
      getScreener('1h').catch(() => null),
      getActivityFeed(80).catch(() => null),
      getPaperOverview().catch(() => null),
    ]).then(([screener, feed, overview]) => {
      if (cancelled) return
      const screenerRow = screener ? bestBuySellRow(screener.rows) : null
      const refusal = feed ? latestRefusal(feed.items) : null
      const position = overview ? firstOpenPosition(overview.positions) : null
      setSuggestions(buildSuggestions({ screenerRow, refusal, position }))
    })
    return () => {
      cancelled = true
    }
  }, [])

  function onSuggestion(s: CopilotSuggestion) {
    queueLaunch({
      kind: 'research',
      symbol: s.symbol,
      promptOverride: s.prompt,
      autoSend: true,
    })
  }

  return (
    <div className="page agent-atelier">
      <header className="iv-page-header agent-atelier-hero">
        <div className="agent-atelier-hero-copy">
          <p className="iv-page-eyebrow">Automatisation · Copilot</p>
          <h1>Copilot</h1>
          <p className="iv-page-question">Pourquoi le moteur a-t-il classé ainsi ?</p>
          <p className="agent-atelier-lede">
            Le <strong>moteur Python</strong> calcule. Claude <strong>interroge le moteur</strong> avec ses outils, puis explique.
            Depuis Décisions ou Journal, un clic « Expliquer » t’amène ici avec la
            question déjà prête.
          </p>
          <div className="agent-atelier-roles" aria-label="Rôles">
            <span className="agent-role-pill is-engine">Moteur = chiffres</span>
            <span className="agent-role-pill is-llm">Claude = outils + explication</span>
            <span className="agent-role-pill is-you">Toi = confirmation</span>
          </div>
        </div>

        <div className="agent-atelier-hero-aside">
          <div className={`agent-session-chip ${hasSession ? 'is-live' : ''}`}>
            <span className="agent-session-label">Session</span>
            {hasSession ? (
              <span className="agent-session-value">
                {symbol}
                <span className="muted"> · {timeframe}</span>
              </span>
            ) : (
              <span className="agent-session-value muted">Aucun symbole — lance depuis Décisions</span>
            )}
          </div>
          <nav className="agent-atelier-jump" aria-label="Raccourcis">
            <Link to="/app/opportunites">Opportunités</Link>
            <Link to="/app/journal">Journal</Link>
            <Link to="/app/context">Contexte</Link>
            <Link to="/app/market">Marché</Link>
          </nav>
        </div>
      </header>

      <div className="agent-atelier-grid">
        <section className="agent-atelier-chat panel">
          <header className="agent-atelier-panel-head">
            <div>
              <h2>Conversation</h2>
              <p className="muted">
                Modes : expliquer une décision, un signal, rechercher, ou une idée —
                toujours ancré sur les données injectées.
              </p>
            </div>
          </header>
          <AgentPanel snapshot={snapshot} />
        </section>

        <aside className="agent-atelier-explore panel" aria-label="Suggestions et capacités">
          <header className="agent-atelier-panel-head">
            <div>
              <h2>Explorer une décision</h2>
              <p className="muted">Suggestions ancrées sur le screener, l’activité et le paper.</p>
            </div>
          </header>
          <div className="agent-atelier-suggestions">
            {suggestions.length === 0 ? (
              <p className="muted agent-atelier-empty-suggest">
                Aucune suggestion contextuelle pour l’instant (pas de BUY/SELL, refus ou position ouverte).
              </p>
            ) : (
              suggestions.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className="agent-suggestion-btn"
                  onClick={() => onSuggestion(s)}
                >
                  {s.label}
                </button>
              ))
            )}
          </div>

          <div className="agent-atelier-caps" aria-label="Capacités">
            <h3>Capacités</h3>
            {capsError && (
              <p className="muted agent-caps-error" role="status">
                {capsError}
              </p>
            )}
            <ul className="agent-caps-list">
              {badges.map((b) => (
                <li key={b.id} className={`agent-caps-row is-${b.status}`} title={b.detail}>
                  <span className="agent-caps-label">{b.label}</span>
                  <span className={`iv-badge agent-caps-badge is-${b.status}`}>{b.statusLabel}</span>
                </li>
              ))}
            </ul>
            <p className="muted agent-caps-note">
              Passer un ordre paper exige toujours une confirmation humaine — hors exécution autonome.
            </p>
          </div>
        </aside>
      </div>
    </div>
  )
}
