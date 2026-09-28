/**
 * AG-FS0 — réponse d'Eve fondée sur le FactSheet : chaque affirmation porte ses faits moteur
 * (puces cliquables → moteur, champ, barre, statut). Seuls les claims validés arrivent ici.
 */
import { useState } from 'react'
import type { FactChip, FactsheetView } from '../lib/agent'
import './FactsheetAnswer.css'

const SECTION_TITLE = { claims: 'Lecture', risks: 'Risques', invalidation: 'Invalidation' } as const

function hhmm(unix: number | null): string {
  if (!unix) return '—'
  return new Date(unix * 1000).toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
  })
}

function chipLabel(f: FactChip): string {
  const name = f.id.replace(/^[^.]+\./, '').replace(/\./g, ' ')
  return `${f.engine} ${name} ${f.display ?? '—'}`
}

export function FactsheetAnswer({ view }: { view: FactsheetView }) {
  const [open, setOpen] = useState<FactChip | null>(null)
  return (
    <div className="fs-answer">
      {view.summary && <p className="fs-summary">{view.summary}</p>}
      {(['claims', 'risks', 'invalidation'] as const).map((section) => {
        const items = view.claims.filter((c) => c.section === section)
        if (!items.length) return null
        return (
          <div className="fs-section" key={section}>
            <span className="eyebrow">{SECTION_TITLE[section]}</span>
            <ul>
              {items.map((c, i) => (
                <li key={`${section}-${i}`} className={`fs-claim fs-${c.kind}`}>
                  <span>{c.text}</span>
                  {c.facts.length > 0 && (
                    <span className="fs-chips">
                      {c.facts.map((f) => (
                        <button
                          type="button"
                          key={f.id}
                          className={`fs-chip${open?.id === f.id ? ' is-open' : ''}${f.status !== 'ok' ? ' is-missing' : ''}`}
                          onClick={() => setOpen(open?.id === f.id ? null : f)}
                          title={`${f.id} · ${f.timeframe} · barre ${hhmm(f.as_of)} UTC`}
                        >
                          {chipLabel(f)}
                        </button>
                      ))}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )
      })}
      {open && (
        <dl className="fs-detail" aria-label="Provenance du fait">
          <dt>Fait</dt>
          <dd>
            <code>{open.id}</code>
          </dd>
          <dt>Valeur</dt>
          <dd>{open.display ?? '—'}</dd>
          <dt>Moteur · source</dt>
          <dd>
            {open.engine} · {open.source}
          </dd>
          <dt>Timeframe · barre close</dt>
          <dd>
            {open.timeframe} · {hhmm(open.as_of)} UTC
          </dd>
          <dt>Connu à</dt>
          <dd>{hhmm(open.known_at)} UTC</dd>
          <dt>Statut</dt>
          <dd>
            {open.status} · {open.validation_status === 'NON_VALIDE' ? 'Signal non validé (VP3)' : open.validation_status}
          </dd>
        </dl>
      )}
      <div className="fs-foot">
        <span className="tag gray">Faits moteur · {view.symbol} {view.timeframe}</span>
        {view.partial && (
          <span className="tag amber">
            {view.removed} affirmation{view.removed > 1 ? 's' : ''} non vérifiable{view.removed > 1 ? 's' : ''} retirée
            {view.removed > 1 ? 's' : ''}
          </span>
        )}
        {view.missing.length > 0 && <span className="tag gray">Indisponible : {view.missing.join(', ')}</span>}
      </div>
    </div>
  )
}
