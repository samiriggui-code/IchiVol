import type { Explanation } from '../lib/labExplain'
import { pct } from '../lib/labFormat'
import { ModalSheetHost } from './ModalSheetHost'

const EXIT_WORDS: Record<string, string> = {
  target: 'Objectif atteint',
  stop: 'Stop touché',
  eod: 'Fin de période',
  max_hold: 'Durée max',
}

function fmtTime(s: number): string {
  const d = new Date(s * 1000)
  return Number.isNaN(d.getTime())
    ? '—'
    : d.toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function fmtIso(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? '—'
    : d.toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

const VERDICT_TONE: Record<string, string> = { green: 'is-mint', amber: 'is-amber', red: 'is-sell', gray: 'is-muted' }

/** Fiche « Examiner » du Strategy Lab : le résultat expliqué en clair, le calcul, la conclusion. */
export function LabExplainSheet({ explanation: x, onClose }: { explanation: Explanation; onClose: () => void }) {
  return (
    <ModalSheetHost ariaLabel={`Explication : ${x.title}`} onCancel={onClose}>
      <aside className="panel trade-sheet lab-sheet">
        <header className="panel-head trade-sheet-head">
          <div>
            <h2>{x.title}</h2>
            <p className="muted">{x.subtitle}</p>
          </div>
          <button type="button" className="iv-btn" onClick={onClose}>
            Fermer
          </button>
        </header>

        <div className="trade-sheet-scroll">
          <section className="lab-sheet-block">
            <p className="subhead">
              En bref <span className={`iv-tag ${VERDICT_TONE[x.verdict.tone] ?? 'is-muted'}`}>{x.verdict.text}</span>
            </p>
            {x.summary.map((s) => (
              <p key={s}>{s}</p>
            ))}
          </section>

          <section className="lab-sheet-block lab-sheet-takeaway">
            <p className="subhead">Ce qu’il faut en retenir</p>
            <p>{x.takeaway}</p>
          </section>

          <dl className="propose-stats lab-sheet-stats">
            {x.stats.map((s) => (
              <div key={s.label}>
                <dt>{s.label}</dt>
                <dd className={`mono ${s.tone ?? ''}`}>{s.value}</dd>
                <small className="muted">{s.hint}</small>
              </div>
            ))}
          </dl>

          <section className="lab-sheet-block">
            <p className="subhead">Comment c’est calculé</p>
            <ol>
              {x.method.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ol>
          </section>

          {x.history && x.history.length > 0 && (
            <section className="lab-sheet-block">
              <p className="subhead">Évolution sur les derniers calculs</p>
              <table className="iv-table is-compact">
                <thead>
                  <tr>
                    <th>CALCUL</th>
                    <th>TRADES</th>
                    <th>RÉUSSITE</th>
                    <th>ESPÉRANCE</th>
                    <th>PF</th>
                  </tr>
                </thead>
                <tbody>
                  {x.history.map((h) => (
                    <tr key={h.when}>
                      <td>{fmtIso(h.when)}</td>
                      <td>{h.trades}</td>
                      <td>{h.winRate}</td>
                      <td>{h.expectancy}</td>
                      <td>{h.profitFactor}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          {x.trades && x.trades.length > 0 && (
            <section className="lab-sheet-block">
              <p className="subhead">
                Les {x.trades.length} trades simulés <small className="muted">(variation du prix, avant frais)</small>
              </p>
              <table className="iv-table is-compact">
                <thead>
                  <tr>
                    <th>ENTRÉE</th>
                    <th>SORTIE</th>
                    <th>RÉSULTAT</th>
                    <th>POURQUOI</th>
                  </tr>
                </thead>
                <tbody>
                  {x.trades.map((t) => (
                    <tr key={`${t.entry_time}-${t.exit_time}`}>
                      <td>{fmtTime(t.entry_time)}</td>
                      <td>{fmtTime(t.exit_time)}</td>
                      <td className={t.pnl_pct > 0 ? 'pos' : t.pnl_pct < 0 ? 'neg' : ''}>
                        {pct(t.pnl_pct, 2, true)}
                      </td>
                      <td>{EXIT_WORDS[t.exit_reason] ?? t.exit_reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
        </div>
      </aside>
    </ModalSheetHost>
  )
}
