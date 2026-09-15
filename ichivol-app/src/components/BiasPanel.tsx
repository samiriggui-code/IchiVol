import { signalLabel } from '../lib/signals'
import type { Signal } from '../lib/types'

interface Props {
  symbol: string
  signals: Signal[]
  bias: 'bull' | 'bear' | 'neutral'
  rvol: number
  price: number | null
}

export function BiasPanel({ symbol, signals, bias, rvol, price }: Props) {
  const recent = [...signals].reverse().slice(0, 8)
  return (
    <section className="panel bias-panel">
      <header className="panel-head">
        <h2>Lecture</h2>
        <span className="panel-meta">{symbol}</span>
      </header>
      <div className="bias-grid">
        <div>
          <span className="label">Biais cloud</span>
          <strong className={`bias bias-${bias}`}>{bias}</strong>
        </div>
        <div>
          <span className="label">RVOL live</span>
          <strong className="mono">{rvol.toFixed(2)}×</strong>
        </div>
        <div>
          <span className="label">Prix</span>
          <strong className="mono">
            {price != null
              ? price.toLocaleString(undefined, { maximumFractionDigits: 6 })
              : '—'}
          </strong>
        </div>
      </div>
      <h3 className="subhead">Signaux confirmés</h3>
      <ul className="signal-list">
        {recent.map((s) => (
          <li key={`${s.time}-${s.kind}`}>
            <span className="sig-chip">{signalLabel(s.kind)}</span>
            <span className="mono muted">{new Date(s.time * 1000).toLocaleString()}</span>
            <span className="mono">{s.rvol.toFixed(2)}×</span>
          </li>
        ))}
        {recent.length === 0 && (
          <li className="muted">Pas de signal volume-confirmé sur la fenêtre</li>
        )}
      </ul>
    </section>
  )
}
