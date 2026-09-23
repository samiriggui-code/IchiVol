import { useMemo, useState } from 'react'
import type { PaperOverview, PaperOverviewPosition, ValuationStatus } from '../lib/paper'
import { assetName, directionWords, eur, pct, price, signedEur } from '../lib/tradeStory'

function tone(v: number | null | undefined): string {
  if (v == null || v === 0) return ''
  return v > 0 ? 'up' : 'down'
}

function valuationLabel(status: ValuationStatus | null | undefined): string {
  switch (status) {
    case 'missing_qty':
      return 'Quantité manquante'
    case 'missing_mark':
      return 'Cours indisponible'
    case 'missing_notional':
      return 'Coût manquant'
    case 'stale_mark':
      return 'Cours périmé'
    case 'priced':
      return 'Valorisée'
    case null:
    case undefined:
      return 'Statut inconnu'
    default: {
      const _exhaustive: never = status
      return _exhaustive
    }
  }
}

function marketValue(p: PaperOverviewPosition): number | null {
  if (p.market_value != null) return p.market_value
  if (p.current_price != null && p.qty != null) return p.qty * p.current_price
  return null
}

function isIncomplete(p: PaperOverviewPosition): boolean {
  if (p.valuation_status != null) {
    return p.valuation_status !== 'priced' && p.valuation_status !== 'stale_mark'
  }
  // Compat si l’engine n’expose pas encore valuation_status
  return p.qty == null || p.current_price == null || p.notional == null
}

function isStaleMark(p: PaperOverviewPosition): boolean {
  return p.mark_stale === true || p.valuation_status === 'stale_mark'
}

/** Human-readable age of the mark used for valuation. */
function formatMarkAge(ageS: number | null | undefined): string | null {
  if (ageS == null || !Number.isFinite(ageS) || ageS < 0) return null
  if (ageS < 60) return `${Math.round(ageS)} s`
  if (ageS < 3600) return `${Math.round(ageS / 60)} min`
  if (ageS < 86400) return `${(ageS / 3600).toFixed(1)} h`
  return `${(ageS / 86400).toFixed(1)} j`
}

type SymbolGroup = {
  key: string
  symbol: string
  direction: string
  lots: PaperOverviewPosition[]
  notional: number
  qty: number | null
  avgEntry: number | null
  value: number | null
  unrealized: number | null
  unrealizedPct: number | null
  entryFee: number
}

function groupBySymbolDir(rows: PaperOverviewPosition[]): SymbolGroup[] {
  const map = new Map<string, PaperOverviewPosition[]>()
  for (const p of rows) {
    const key = `${p.symbol}::${p.direction}`
    const list = map.get(key)
    if (list) list.push(p)
    else map.set(key, [p])
  }
  return [...map.entries()]
    .map(([key, lots]) => {
      const notional = lots.reduce((s, p) => s + (p.notional ?? 0), 0)
      const qtyParts = lots.map((p) => p.qty).filter((q): q is number => q != null)
      const qty = qtyParts.length === lots.length ? qtyParts.reduce((a, b) => a + b, 0) : null
      const costQty = lots.filter((p) => p.qty != null && p.entry_price != null)
      const avgEntry =
        qty != null && qty > 0 && costQty.length === lots.length
          ? lots.reduce((s, p) => s + (p.qty ?? 0) * p.entry_price, 0) / qty
          : lots.length === 1
            ? lots[0].entry_price
            : null
      const values = lots.map(marketValue)
      const value = values.every((v) => v != null) ? values.reduce((a, b) => a! + b!, 0) : null
      const pnls = lots.map((p) => p.unrealized_pnl)
      const unrealized = pnls.every((v) => v != null) ? pnls.reduce((a, b) => a! + b!, 0) : null
      const unrealizedPct =
        avgEntry != null && lots[0].current_price != null
          ? lots[0].direction === 'LONG'
            ? (lots[0].current_price - avgEntry) / avgEntry
            : (avgEntry - lots[0].current_price) / avgEntry
          : lots.length === 1
            ? lots[0].unrealized_pct
            : null
      const entryFee = lots.reduce((s, p) => s + (p.entry_fee ?? 0), 0)
      return {
        key,
        symbol: lots[0].symbol,
        direction: lots[0].direction,
        lots: [...lots].sort((a, b) => +new Date(a.entry_time) - +new Date(b.entry_time)),
        notional,
        qty,
        avgEntry,
        value,
        unrealized,
        unrealizedPct,
        entryFee,
      }
    })
    .sort((a, b) => b.notional - a.notional)
}

function LotRow({
  p,
  onSelect,
  onClose,
  closingId,
}: {
  p: PaperOverviewPosition
  onSelect: (p: PaperOverviewPosition) => void
  onClose?: (id: string) => void
  closingId?: string | null
}) {
  const value = marketValue(p)
  return (
    <li className="invest-lot invest-lot--compact">
      <button type="button" className="invest-lot-pick" onClick={() => onSelect(p)}>
        <strong>
          {p.timeframe} · {p.source === 'user_confirmed' ? 'Manuel' : 'Auto'}
        </strong>
        <span className="mono muted">{eur(p.notional)}</span>
        <span className={tone(p.unrealized_pnl)}>
          {p.unrealized_pnl != null ? signedEur(p.unrealized_pnl) : '—'}
        </span>
        <span className="muted mono">{value != null ? eur(value) : '—'}</span>
      </button>
      {onClose && (
        <button
          type="button"
          className="ghost"
          disabled={closingId === p.id}
          onClick={() => onClose(p.id)}
        >
          Clôturer…
        </button>
      )}
    </li>
  )
}

function GroupCard({
  group,
  equity,
  onSelect,
  onClose,
  closingId,
}: {
  group: SymbolGroup
  equity: number
  onSelect: (p: PaperOverviewPosition) => void
  onClose?: (id: string) => void
  closingId?: string | null
}) {
  const [lotsOpen, setLotsOpen] = useState(false)
  const dir = directionWords(group.direction)
  const share = group.value != null && equity > 0 ? (group.value / equity) * 100 : null
  const multi = group.lots.length > 1
  const primary = group.lots.reduce((a, b) => ((a.notional ?? 0) >= (b.notional ?? 0) ? a : b))

  return (
    <article className="invest-card invest-card--compact">
      <header className="invest-card-head">
        <div>
          <strong className="invest-card-asset">{assetName(group.symbol)}</strong>
          <span className="muted">
            {' '}
            · {multi ? `${group.lots.length} lots` : group.lots[0].timeframe}
          </span>
          {group.lots.some(isStaleMark) && (
            <span className="invest-stale-badge" title="Cours de valorisation périmé">
              {' '}
              · Cours périmé
            </span>
          )}
          {(() => {
            const age = formatMarkAge(
              Math.max(...group.lots.map((p) => p.mark_age_s ?? -1)),
            )
            return age ? (
              <span className="muted" title="Âge du cours de valorisation">
                {' '}
                · mark {age}
              </span>
            ) : null
          })()}
        </div>
        <span className={`invest-card-dir is-${group.direction.toLowerCase()}`}>{dir.title}</span>
      </header>
      <p className="invest-card-invested">
        <span className="context-label">Coût d’acquisition</span>
        <strong>{eur(group.notional)}</strong>
      </p>
      <dl className="invest-card-grid invest-card-grid--compact">
        <div>
          <dt>Valeur actuelle</dt>
          <dd>{group.value != null ? eur(group.value) : '—'}</dd>
        </div>
        <div>
          <dt title="Mark-to-market · hors frais de sortie · non acquis">Latent</dt>
          <dd className={tone(group.unrealized)}>
            {group.unrealized != null ? signedEur(group.unrealized) : '—'}
            {group.unrealizedPct != null && <small> · {pct(group.unrealizedPct, 1)}</small>}
          </dd>
        </div>
        <div>
          <dt>Part</dt>
          <dd>{share != null ? `${share.toFixed(1)} %` : '—'}</dd>
        </div>
        <div>
          <dt>{multi ? 'Prix moyen' : 'Entrée'}</dt>
          <dd className="mono">{price(group.avgEntry)}</dd>
        </div>
      </dl>
      <footer className="invest-card-actions">
        <button type="button" className="ghost" onClick={() => onSelect(primary)}>
          Fiche…
        </button>
        {multi ? (
          <button
            type="button"
            className="ghost"
            aria-expanded={lotsOpen}
            onClick={() => setLotsOpen((v) => !v)}
          >
            {lotsOpen ? 'Masquer lots' : `Lots (${group.lots.length})…`}
          </button>
        ) : (
          onClose && (
            <button
              type="button"
              className="ghost"
              disabled={closingId === primary.id}
              onClick={() => onClose(primary.id)}
            >
              Clôturer…
            </button>
          )
        )}
      </footer>
      {multi && lotsOpen && (
        <ul className="invest-lots" aria-label={`Lots ${assetName(group.symbol)}`}>
          {group.lots.map((p) => (
            <LotRow
              key={p.id}
              p={p}
              onSelect={onSelect}
              onClose={onClose}
              closingId={closingId}
            />
          ))}
        </ul>
      )}
    </article>
  )
}

function IncompleteCard({
  p,
  onSelect,
  onClose,
  closingId,
}: {
  p: PaperOverviewPosition
  onSelect: (p: PaperOverviewPosition) => void
  onClose?: (id: string) => void
  closingId?: string | null
}) {
  const dir = directionWords(p.direction)
  return (
    <article className="invest-card invest-card--incomplete invest-card--compact">
      <header className="invest-card-head">
        <div>
          <strong className="invest-card-asset">{assetName(p.symbol)}</strong>
          <span className="muted"> · {p.timeframe}</span>
        </div>
        <span className={`invest-card-dir is-${p.direction.toLowerCase()}`}>{dir.title}</span>
      </header>
      <p className="invest-incomplete-badge">{valuationLabel(p.valuation_status)}</p>
      <dl className="invest-card-grid invest-card-grid--compact">
        <div>
          <dt>Coût</dt>
          <dd>{p.notional != null ? eur(p.notional) : '—'}</dd>
        </div>
        <div>
          <dt>Entrée</dt>
          <dd className="mono">{price(p.entry_price)}</dd>
        </div>
      </dl>
      <footer className="invest-card-actions">
        <button type="button" className="ghost" onClick={() => onSelect(p)}>
          Fiche…
        </button>
        {onClose && (
          <button
            type="button"
            className="ghost"
            disabled={closingId === p.id}
            onClick={() => onClose(p.id)}
          >
            Clôturer…
          </button>
        )}
      </footer>
    </article>
  )
}

/** Cartes investissement — agrégat par symbole + lots dépliables. */
export function InvestmentCards({
  overview,
  onSelect,
  onClose,
  closingId,
}: {
  overview: PaperOverview
  onSelect: (p: PaperOverviewPosition) => void
  onClose?: (id: string) => void
  closingId?: string | null
}) {
  const open = overview.positions.filter((p) => p.status === 'OPEN')
  const equity = overview.account.equity || 1

  const { complete, incomplete } = useMemo(() => {
    const completeRows: PaperOverviewPosition[] = []
    const incompleteRows: PaperOverviewPosition[] = []
    for (const p of open) {
      if (isIncomplete(p)) incompleteRows.push(p)
      else completeRows.push(p)
    }
    return { complete: groupBySymbolDir(completeRows), incomplete: incompleteRows }
  }, [open])

  if (open.length === 0) {
    return (
      <p className="muted synthese-empty">
        Aucun investissement ouvert — {eur(overview.account.cash)} de liquidités.
      </p>
    )
  }

  return (
    <div className="invest-sections">
      {complete.length > 0 && (
        <div className="invest-cards">
          {complete.map((g) => (
            <GroupCard
              key={g.key}
              group={g}
              equity={equity}
              onSelect={onSelect}
              onClose={onClose}
              closingId={closingId}
            />
          ))}
        </div>
      )}
      {incomplete.length > 0 && (
        <div className="invest-incomplete">
          <h3 className="invest-incomplete-title">Données incomplètes</h3>
          <p className="muted invest-incomplete-lead">
            Positions ouvertes sans quantité capitalisée ou sans cours de valorisation. Le %
            affiché (s’il existe) est un mouvement de prix, pas un P&amp;L de portefeuille. Les
            montants manquants restent « — » (jamais 0 inventé).
          </p>
          <div className="invest-cards">
            {incomplete.map((p) => (
              <IncompleteCard
                key={p.id}
                p={p}
                onSelect={onSelect}
                onClose={onClose}
                closingId={closingId}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

/** Bandeau compte — définitions explicites + réconciliation frais d’entrée ouverts. */
export function BrokerAccount({ overview }: { overview: PaperOverview }) {
  const a = overview.account
  const totalPct = a.initial_cash ? a.total_pnl / a.initial_cash : null
  const openFees = a.open_entry_fees ?? 0
  const realizedPlus = a.realized_plus_unrealized ?? a.realized_pnl + a.unrealized_pnl
  const showReconcile = openFees > 0.005 || Math.abs(realizedPlus - a.total_pnl) > 0.005
  const liquidation = a.liquidation_value
  const staleOpen = a.stale_open ?? 0

  return (
    <div className="broker-account">
      <div className="broker-equity-row">
        <div className="broker-equity">
          <span className="context-label">Equity (valeur de marché)</span>
          <strong className="broker-equity-value">{eur(a.equity)}</strong>
          <span className={`broker-equity-delta ${tone(a.total_pnl)}`}>
            {signedEur(a.total_pnl)} ({pct(totalPct, 2)}) depuis la création · capital{' '}
            {eur(a.initial_cash, 0)}
          </span>
          {liquidation != null && (
            <p className="broker-liquidation" title="Cash après clôture de toutes les lignes au cours actuel, frais de sortie inclus">
              <span className="context-label">Valeur si tout est clôturé maintenant</span>
              <strong className="mono">{eur(liquidation)}</strong>
            </p>
          )}
          {staleOpen > 0 && (
            <p className="broker-stale-hint" role="status">
              {staleOpen} cours périmé{staleOpen > 1 ? 's' : ''} — valorisation indicative
            </p>
          )}
          <p className="muted broker-equity-hint">
            Liquidités + coût des positions + latent mark-to-market. La valeur de clôture déduit les
            frais de sortie estimés. Période de perf = depuis le capital initial.
          </p>
        </div>
        <div className="context-grid broker-equity-stats">
          <div className="context-card" title="Cash disponible pour de nouveaux trades">
            <span className="context-label">Liquidités</span>
            <strong className="context-value">{eur(a.cash)}</strong>
          </div>
          <div
            className="context-card"
            title="Somme des coûts d’acquisition (notional) des positions ouvertes — pas la valeur de marché"
          >
            <span className="context-label">Engagé (coût)</span>
            <strong className="context-value">{eur(a.invested)}</strong>
          </div>
          <div
            className="context-card"
            title="Mark-to-market qty×(cours−entrée). Non acquis. Hors frais de sortie estimés."
          >
            <span className="context-label">Latent</span>
            <strong className={`context-value ${tone(a.unrealized_pnl)}`}>
              {signedEur(a.unrealized_pnl)}
            </strong>
          </div>
          <div
            className="context-card"
            title="P&L des trades clôturés, net des frais d’entrée et de sortie"
          >
            <span className="context-label">Réalisé (net frais)</span>
            <strong className={`context-value ${tone(a.realized_pnl)}`}>
              {signedEur(a.realized_pnl)}
            </strong>
          </div>
        </div>
      </div>

      {showReconcile && (
        <div className="broker-reconcile" role="note">
          <h3 className="broker-reconcile-title">Réconciliation P&amp;L</h3>
          <dl className="broker-reconcile-grid">
            <div>
              <dt>Réalisé + latent</dt>
              <dd className="mono">{signedEur(realizedPlus)}</dd>
            </div>
            <div>
              <dt title="Commissions d’entrée déjà sorties du cash, pas encore dans le réalisé">
                − Frais d’entrée ouverts
              </dt>
              <dd className="mono">{signedEur(-openFees)}</dd>
            </div>
            <div className="broker-reconcile-total">
              <dt>= P&amp;L compte</dt>
              <dd className={`mono ${tone(a.total_pnl)}`}>{signedEur(a.total_pnl)}</dd>
            </div>
          </dl>
          <p className="muted broker-reconcile-note">
            Les frais d’entrée des positions encore ouvertes réduisent déjà les liquidités ; ils
            n’entrent dans le « réalisé » qu’à la clôture. Le latent n’inclut pas les frais de
            sortie futurs.
          </p>
        </div>
      )}
    </div>
  )
}

/** Tableau « positions » façon broker (vue technique / détail). */
export function BrokerPositions({
  overview,
  onSelect,
  onClose,
  closingId,
}: {
  overview: PaperOverview
  onSelect: (p: PaperOverviewPosition) => void
  onClose?: (id: string) => void
  closingId?: string | null
}) {
  const open = overview.positions.filter((p) => p.status === 'OPEN')
  const total = overview.account.equity || 1
  return (
    <div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Actif</th>
              <th>Sens</th>
              <th>Coût</th>
              <th>Quantité</th>
              <th>Prix d’entrée</th>
              <th>Prix actuel</th>
              <th>Valeur actuelle</th>
              <th>Gain / perte</th>
              <th>Stop</th>
              <th>Objectif</th>
              <th>% du portefeuille</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {open.map((p) => {
              const value = marketValue(p)
              return (
                <tr key={p.id}>
                  <td>
                    <strong>{assetName(p.symbol)}</strong>
                    <span className="muted"> · {p.timeframe}</span>
                    {(isIncomplete(p) || isStaleMark(p)) && (
                      <span className="muted"> · {valuationLabel(p.valuation_status)}</span>
                    )}
                    {formatMarkAge(p.mark_age_s) && (
                      <span className="muted"> · mark {formatMarkAge(p.mark_age_s)}</span>
                    )}
                  </td>
                  <td>{directionWords(p.direction).title}</td>
                  <td className="mono">
                    <strong>{eur(p.notional)}</strong>
                  </td>
                  <td className="mono">{p.qty != null ? p.qty.toPrecision(4) : '—'}</td>
                  <td className="mono">{price(p.entry_price)}</td>
                  <td className="mono">{price(p.current_price)}</td>
                  <td className="mono">{value != null ? eur(value) : '—'}</td>
                  <td className={`mono ${tone(p.unrealized_pnl)}`}>
                    {p.unrealized_pnl != null ? signedEur(p.unrealized_pnl) : '—'}
                    {p.unrealized_pct != null && <small> ({pct(p.unrealized_pct, 2)})</small>}
                  </td>
                  <td className="mono down">{price(p.stop_price)}</td>
                  <td className="mono up">{price(p.take_profit_price)}</td>
                  <td className="mono muted">
                    {value != null ? `${((value / total) * 100).toFixed(1)} %` : '—'}
                  </td>
                  <td>
                    <button type="button" className="ghost" onClick={() => onSelect(p)}>
                      Fiche
                    </button>
                    {onClose && (
                      <button
                        type="button"
                        className="ghost"
                        disabled={closingId === p.id}
                        onClick={() => onClose(p.id)}
                      >
                        Clôturer…
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
            {open.length === 0 && (
              <tr>
                <td colSpan={12} className="muted center">
                  Aucune position ouverte — {eur(overview.account.cash)} disponibles.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
