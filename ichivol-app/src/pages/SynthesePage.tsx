import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ActivityJournal } from '../components/ActivityJournal'
import {
  BrokerAccount,
  InvestmentCards,
} from '../components/BrokerAccount'
import { PaperTradeSheet } from '../components/PaperTradeSheet'
import {
  closePaperPosition,
  getPaperActivity,
  getPaperOverview,
  getShadowStats,
  listPaperPositions,
  type PaperOrderRow,
  type PaperOverview,
  type PaperPosition,
  type ShadowStats,
} from '../lib/paper'
import {
  assetName,
  directionWords,
  eur,
  EXIT_RULES,
  exitReasonLabel,
  pct,
  signedEur,
} from '../lib/tradeStory'

type Tab = 'synthese' | 'historique'

function tone(v: number | null | undefined): string {
  if (v == null || v === 0) return ''
  return v > 0 ? 'up' : 'down'
}

function shadowPlain(stats: ShadowStats | null): string {
  if (!stats || stats.n_closed < 5) {
    return 'Pas encore assez de cas pour juger les filtres (il en faut au moins 5 fermés).'
  }
  if (stats.filter_verdict === 'filter_too_aggressive') {
    return 'Les filtres ont souvent bloqué des trades qui auraient gagné — ils sont peut‑être trop stricts.'
  }
  if (stats.filter_verdict === 'filter_helpful') {
    return 'Les filtres ont surtout bloqué des trades qui auraient perdu — utiles pour l’instant.'
  }
  return 'Résultat mitigé : les filtres n’améliorent ni ne dégradent clairement le résultat.'
}

function ClosedHistory({
  rows,
  onSelect,
}: {
  rows: PaperPosition[]
  onSelect: (p: PaperPosition) => void
}) {
  const closed = useMemo(
    () =>
      rows
        .filter((p) => p.status === 'CLOSED')
        .sort((a, b) => +new Date(b.exit_time ?? b.entry_time) - +new Date(a.exit_time ?? a.entry_time))
        .slice(0, 40),
    [rows],
  )

  if (closed.length === 0) {
    return (
      <p className="muted">
        Aucun trade terminé pour l’instant. Quand une position se ferme (stop, objectif, ou à la
        main), elle apparaîtra ici avec la somme investie et le résultat en euros.
      </p>
    )
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Quand</th>
            <th>Quoi</th>
            <th>Somme investie</th>
            <th>Résultat</th>
            <th>Pourquoi sorti</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {closed.map((p) => {
            const dir = directionWords(p.direction)
            const when = p.exit_time ?? p.entry_time
            return (
              <tr key={p.id}>
                <td className="mono muted">
                  {new Date(when).toLocaleString('fr-FR', {
                    day: '2-digit',
                    month: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </td>
                <td>
                  {dir.title} de <strong>{assetName(p.symbol)}</strong>
                  <span className="muted"> · {p.timeframe}</span>
                  <br />
                  <span className="muted">
                    {p.source === 'auto_watchlist' ? 'Ouvert auto (screener)' : 'Confirmé par vous'}
                  </span>
                </td>
                <td className="mono muted">{eur(p.notional)}</td>
                <td className={`mono ${tone(p.realized_pnl ?? p.pnl_pct)}`}>
                  {p.realized_pnl != null ? signedEur(p.realized_pnl) : pct(p.pnl_pct, 2)}
                </td>
                <td>{exitReasonLabel(p.exit_reason)}</td>
                <td>
                  <button type="button" className="ghost" onClick={() => onSelect(p)}>
                    Voir l’histoire
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export function SynthesePage() {
  const [tab, setTab] = useState<Tab>('synthese')
  const [overview, setOverview] = useState<PaperOverview | null>(null)
  const [activity, setActivity] = useState<PaperOrderRow[]>([])
  const [history, setHistory] = useState<PaperPosition[]>([])
  const [shadow, setShadow] = useState<ShadowStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [closingId, setClosingId] = useState<string | null>(null)
  const [sheetPos, setSheetPos] = useState<PaperPosition | null>(null)

  const reload = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [ov, act, mine, auto, sh] = await Promise.all([
        getPaperOverview('ICHIVOL_BASELINE_V1'),
        getPaperActivity('ICHIVOL_BASELINE_V1', 60).catch(() => [] as PaperOrderRow[]),
        listPaperPositions({ source: 'user_confirmed' }).catch(() => [] as PaperPosition[]),
        listPaperPositions({ source: 'auto_watchlist' }).catch(() => [] as PaperPosition[]),
        getShadowStats().catch(() => null),
      ])
      setOverview(ov)
      setActivity(act)
      setHistory([...mine, ...auto])
      setShadow(sh)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Impossible de charger le compte')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  async function onClose(id: string) {
    setClosingId(id)
    try {
      await closePaperPosition(id)
      await reload()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Fermeture impossible')
    } finally {
      setClosingId(null)
    }
  }

  const closedCount = useMemo(
    () => history.filter((p) => p.status === 'CLOSED').length,
    [history],
  )

  return (
    <div className="synthese-page">
      <header className="page-head">
        <h1>Synthèse</h1>
        <p className="muted">
          Compte virtuel en langage clair : cash, investissements en cartes, courbe chiffrée, et
          historique des trades.
        </p>
      </header>

      <div className="synthese-tabs journal-tabs" role="tablist" aria-label="Volets synthèse">
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'synthese'}
          className={tab === 'synthese' ? 'is-active ghost' : 'ghost'}
          onClick={() => setTab('synthese')}
        >
          Synthèse
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'historique'}
          className={tab === 'historique' ? 'is-active ghost' : 'ghost'}
          onClick={() => setTab('historique')}
        >
          Historique{closedCount > 0 ? ` (${closedCount})` : ''}
        </button>
        <button type="button" className="ghost" onClick={() => void reload()} disabled={loading}>
          {loading ? '…' : 'Actualiser'}
        </button>
      </div>

      {error && (
        <div className="banner error" role="alert">
          {error}
        </div>
      )}

      {!overview && loading && <p className="muted">Chargement du compte…</p>}

      {!overview && !loading && (
        <div className="panel">
          <p className="muted">
            Compte pas encore prêt (moteur / migration). Réessayez après un redémarrage, ou ouvrez
            une position depuis <Link to="/app/decisions">Décisions</Link>.
          </p>
        </div>
      )}

      {overview && tab === 'synthese' && (
        <>
          <section className="panel">
            <header className="panel-head">
              <h2>Compte · {overview.portfolio.label}</h2>
            </header>
            <BrokerAccount overview={overview} orders={activity} />
            <p className="muted paper-perf-note">
              Règle simple : on risque environ 1 % du capital par trade, objectif ≈ 2× ce risque
              (2R). Maximum 5 positions en même temps.
            </p>
          </section>

          <section className="panel">
            <header className="panel-head">
              <h2>Mes investissements</h2>
              <span className="panel-meta">
                {overview.account.open_positions} ouvert
                {overview.account.open_positions > 1 ? 's' : ''} · {eur(overview.account.invested)}{' '}
                placés
              </span>
            </header>
            <InvestmentCards
              overview={overview}
              onSelect={setSheetPos}
              onClose={onClose}
              closingId={closingId}
            />
            <details className="paper-rules-details">
              <summary>Comment une position se termine ?</summary>
              <ul className="trade-plan-rules">
                {EXIT_RULES.map((r) => (
                  <li key={r.title}>
                    <strong>{r.title}.</strong> {r.text}
                  </li>
                ))}
              </ul>
            </details>
          </section>

          <section className="panel">
            <header className="panel-head">
              <h2>Dernières actions du moteur</h2>
              <span className="panel-meta">achats et ventes virtuels</span>
            </header>
            <ActivityJournal orders={activity} />
          </section>

          <section className="panel">
            <header className="panel-head">
              <h2>Filtres (lecture simple)</h2>
            </header>
            <p className="paper-shadow-plain">{shadowPlain(shadow)}</p>
            {shadow && shadow.n_closed > 0 && (
              <p className="muted paper-perf-note">
                {shadow.n_closed} cas fermés · mean R {shadow.mean_pnl_r?.toFixed(2) ?? '—'} (hors
                cash — ShadowBroker).
              </p>
            )}
          </section>
        </>
      )}

      {overview && tab === 'historique' && (
        <section className="panel">
          <header className="panel-head">
            <h2>Historique des trades</h2>
            <span className="panel-meta">fermetures récentes · somme investie + résultat</span>
          </header>
          <ClosedHistory rows={history} onSelect={setSheetPos} />
        </section>
      )}

      {sheetPos && <PaperTradeSheet position={sheetPos} onClose={() => setSheetPos(null)} />}
    </div>
  )
}
