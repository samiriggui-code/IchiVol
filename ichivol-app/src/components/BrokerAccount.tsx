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
  if (p.valuation_status != null) return p.valuation_status !== 'priced'
  // Compat si l’engine n’expose pas encore valuation_status
  return p.qty == null || p.current_price == null || p.notional == null
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
  const asOf =
    p.price_as_of != null
      ? new Date(p.price_as_of * 1000).toLocaleString('fr-FR', {
          day: '2-digit',
          month: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
        })
      : null
  return (
    <li className="invest-lot">
      <div className="invest-lot-main">
        <strong>
          {p.timeframe} · {p.source}
        </strong>
        <span className="muted mono">
          {new Date(p.entry_time).toLocaleString('fr-FR', {
            day: '2-digit',
            month: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
          })}
        </span>
      </div>
      <dl className="invest-lot-grid">
        <div>
          <dt>Coût</dt>
          <dd>{eur(p.notional)}</dd>
        </div>
        <div>
          <dt>Qté</dt>
          <dd className="mono">{p.qty != null ? p.qty.toPrecision(4) : '—'}</dd>
        </div>
        <div>
          <dt>Entrée</dt>
          <dd className="mono">{price(p.entry_price)}</dd>
        </div>
        <div>
          <dt title={asOf ? `Cours du ${asOf}` : undefined}>Cours</dt>
          <dd className="mono">{price(p.current_price)}</dd>
        </div>
        <div>
          <dt>Valeur</dt>
          <dd>{value != null ? eur(value) : '—'}</dd>
        </div>
        <div>
          <dt title="(cours − entrée) / entrée · hors frais de sortie">Latent</dt>
          <dd className={tone(p.unrealized_pnl)}>
            {p.unrealized_pnl != null ? signedEur(p.unrealized_pnl) : '—'}
            {p.unrealized_pct != null && <small> · {pct(p.unrealized_pct, 1)}</small>}
          </dd>
        </div>
        {p.entry_fee != null && p.entry_fee > 0 && (
          <div>
            <dt>Frais entrée</dt>
            <dd className="mono">{eur(p.entry_fee)}</dd>
          </div>
        )}
        {(p.stop_price != null || p.take_profit_price != null) && (
          <div>
            <dt>Stop / TP</dt>
            <dd className="mono">
              {price(p.stop_price)} / {price(p.take_profit_price)}
            </dd>
          </div>
        )}
      </dl>
      <div className="invest-card-actions">
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
            Fermer…
          </button>
        )}
      </div>
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
  const [open, setOpen] = useState(group.lots.length > 1)
  const dir = directionWords(group.direction)
  const share = group.value != null && equity > 0 ? (group.value / equity) * 100 : null
  const multi = group.lots.length > 1

  return (
    <article className="invest-card">
      <header className="invest-card-head">
        <div>
          <strong className="invest-card-asset">{assetName(group.symbol)}</strong>
          <span className="muted">
            {' '}
            · {multi ? `${group.lots.length} lots` : group.lots[0].timeframe}
          </span>
        </div>
        <span className={`invest-card-dir is-${group.direction.toLowerCase()}`}>{dir.title}</span>
      </header>
      <p className="invest-card-invested">
        <span className="context-label">Coût d’acquisition</span>
        <strong>{eur(group.notional)}</strong>
      </p>
      <dl className="invest-card-grid">
        <div>
          <dt>Valeur actuelle</dt>
          <dd>{group.value != null ? eur(group.value) : '—'}</dd>
        </div>
        <div>
          <dt title="Mark-to-market · hors frais de sortie estimés · non acquis">Latent</dt>
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
      {multi && (
        <button
          type="button"
          className="ghost invest-lots-toggle"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? 'Masquer les lots' : `Détail des ${group.lots.length} lots`}
        </button>
      )}
      {(open || !multi) && (
        <ul className="invest-lots">
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
}: {
  p: PaperOverviewPosition
  onSelect: (p: PaperOverviewPosition) => void
}) {
  const dir = directionWords(p.direction)
  return (
    <article className="invest-card invest-card--incomplete">
      <header className="invest-card-head">
        <div>
          <strong className="invest-card-asset">{assetName(p.symbol)}</strong>
          <span className="muted"> · {p.timeframe}</span>
        </div>
        <span className={`invest-card-dir is-${p.direction.toLowerCase()}`}>{dir.title}</span>
      </header>
      <p className="invest-incomplete-badge">{valuationLabel(p.valuation_status)}</p>
      <dl className="invest-card-grid">
        <div>
          <dt>Coût</dt>
          <dd>{p.notional != null ? eur(p.notional) : '—'}</dd>
        </div>
        <div>
          <dt>Entrée</dt>
          <dd className="mono">{price(p.entry_price)}</dd>
        </div>
        <div>
          <dt>Cours</dt>
          <dd className="mono">{price(p.current_price)}</dd>
        </div>
        <div>
          <dt title="Performance prix seule — pas un rendement de portefeuille">Δ prix</dt>
          <dd className={tone(p.unrealized_pct)}>
            {p.unrealized_pct != null ? pct(p.unrealized_pct, 1) : '—'}
          </dd>
        </div>
        <div>
          <dt>Valeur / P&amp;L €</dt>
          <dd>—</dd>
        </div>
        <div>
          <dt>Statut</dt>
          <dd className="muted">Hors totaux capitalisés</dd>
        </div>
      </dl>
      <footer className="invest-card-actions">
        <button type="button" className="ghost" onClick={() => onSelect(p)}>
          Fiche
        </button>
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
              <IncompleteCard key={p.id} p={p} onSelect={onSelect} />
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

  return (
    <div className="broker-account">
      <div className="broker-equity-row">
        <div className="broker-equity">
          <span className="context-label">Valeur totale du compte</span>
          <strong className="broker-equity-value">{eur(a.equity)}</strong>
          <span className={`broker-equity-delta ${tone(a.total_pnl)}`}>
            {signedEur(a.total_pnl)} ({pct(totalPct, 2)}) depuis la création · capital{' '}
            {eur(a.initial_cash, 0)}
          </span>
          <p className="muted broker-equity-hint">
            Liquidités + coût des positions + latent mark-to-market. Période de perf = depuis le
            capital initial (pas la date de maj logicielle).
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
                    {isIncomplete(p) && (
                      <span className="muted"> · {valuationLabel(p.valuation_status)}</span>
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
                        Fermer…
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
