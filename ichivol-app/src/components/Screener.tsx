import { displaySymbol } from '../lib/markets'
import { signalLabel } from '../lib/signals'
import type { ScreenerRow } from '../lib/types'
import { VerdictBadge } from './VerdictBadge'

interface Props {
  rows: ScreenerRow[]
  loading: boolean
  selected: string
  onSelect: (symbol: string) => void
  title?: string
  showEngine?: boolean
}

function fmtVol(n: number): string {
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K`
  return n.toFixed(0)
}

export function Screener({
  rows,
  loading,
  selected,
  onSelect,
  title = 'Screener',
  showEngine = false,
}: Props) {
  const cols = showEngine ? 6 : 5
  return (
    <section className="panel screener">
      <header className="panel-head">
        <h2>{title}</h2>
        <span className="panel-meta">{loading ? 'scan…' : `${rows.length} paires`}</span>
      </header>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Symbole</th>
              <th>Biais</th>
              <th>RVOL</th>
              {showEngine && <th>Moteur</th>}
              <th>24h</th>
              <th>Signal</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.symbol}
                className={r.symbol === selected ? 'is-active' : undefined}
                onClick={() => onSelect(r.symbol)}
              >
                <td>
                  <div className="sym">
                    <strong>{displaySymbol(r.symbol)}</strong>
                    <small>
                      {r.symbol} · {fmtVol(r.quoteVolume)}
                    </small>
                  </div>
                </td>
                <td>
                  <span className={`bias bias-${r.bias}`}>{r.bias}</span>
                </td>
                <td className="mono">{r.rvol.toFixed(2)}×</td>
                {showEngine && (
                  <td>
                    {r.engineDecision ? (
                      <VerdictBadge decision={r.engineDecision} pipeline={r.enginePipeline} />
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                )}
                <td className={r.change24h >= 0 ? 'up' : 'down'}>
                  {r.change24h.toFixed(1)}%
                </td>
                <td>
                  {r.lastSignal ? (
                    <span className="sig-chip">{signalLabel(r.lastSignal.kind)}</span>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
              </tr>
            ))}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={cols} className="muted center">
                  Aucun symbole sur ce timeframe
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}
