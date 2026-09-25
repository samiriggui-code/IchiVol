/**
 * FichePosition — skeleton phase B (paper only).
 * Classes maquette dialog ; donnée manquante → « — » + raison.
 */

import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { PaperCloseConfirmSheet } from '../PaperCloseConfirmSheet'
import { PositionScenariosDisclosure } from '../ScenariosPanel'
import {
  afterPaperOrJournalAction,
  actionNoticeStyle,
} from '../../lib/actionFeedback'
import { displaySymbol } from '../../lib/markets'
import {
  closePaperPosition,
  getPaperOverview,
  listPaperPositions,
  type PaperOverviewPosition,
  type PaperPosition,
} from '../../lib/paper'
import {
  directionWords,
  eur,
  exitReasonLabel,
  holdingLabel,
  pct,
  price,
  signedEur,
} from '../../lib/tradeStory'
import { useFicheNav } from '../../lib/useFicheNav'
import './ficheDialog.css'

type BadgeTone = 'green' | 'amber' | 'red' | 'gray' | ''

function badge(text: string, tone: BadgeTone = ''): ReactNode {
  let inferred = tone
  if (!inferred) {
    inferred = /OUVERTE|EN COURS|PASSE/i.test(text)
      ? 'green'
      : /CLÔTUR|FERMÉ|STOP|REFUS/i.test(text)
        ? 'red'
        : /STALE|PRUDENCE/i.test(text)
          ? 'amber'
          : ''
  }
  return <span className={`tag ${inferred}`.trim()}>{text}</span>
}

function toneClass(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return ''
  return v > 0 ? 'up' : v < 0 ? 'down' : ''
}

async function loadPositionById(
  id: string,
): Promise<{ pos: PaperPosition; live: PaperOverviewPosition | null }> {
  const [all, overview] = await Promise.all([
    listPaperPositions().catch(() => [] as PaperPosition[]),
    getPaperOverview().catch(() => null),
  ])
  const fromList = all.find((p) => p.id === id) ?? null
  const fromOv =
    overview?.positions.find((p) => p.id === id) ??
    (fromList
      ? overview?.positions.find(
          (p) => p.symbol.toUpperCase() === fromList.symbol.toUpperCase(),
        )
      : null) ??
    null
  const pos = fromList ?? fromOv
  if (!pos) throw new Error('Position introuvable')
  return { pos, live: fromOv }
}

export function FichePosition({
  positionId,
  onClose,
}: {
  positionId: string
  onClose: () => void
}) {
  const navigate = useNavigate()
  const { openDecisionFiche } = useFicheNav()
  const dialogRef = useRef<HTMLDialogElement>(null)
  const closeLock = useRef(false)

  const [pos, setPos] = useState<PaperPosition | null>(null)
  const [live, setLive] = useState<PaperOverviewPosition | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [closeConfirm, setCloseConfirm] = useState(false)
  const [closeConfirming, setCloseConfirming] = useState(false)
  const [closeError, setCloseError] = useState<string | null>(null)
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null)

  useEffect(() => {
    const el = dialogRef.current
    if (!el) return
    if (!el.open) el.showModal()
    const onDialogClose = () => onClose()
    el.addEventListener('close', onDialogClose)
    return () => el.removeEventListener('close', onDialogClose)
  }, [onClose])

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const { pos: p, live: l } = await loadPositionById(positionId)
      setPos(p)
      setLive(l)
    } catch (err: unknown) {
      setPos(null)
      setLive(null)
      setError(err instanceof Error ? err.message : 'Chargement impossible')
    } finally {
      setLoading(false)
    }
  }, [positionId])

  useEffect(() => {
    void refresh()
  }, [refresh])

  async function executeClose() {
    if (!pos?.id || closeLock.current) return
    closeLock.current = true
    setCloseConfirming(true)
    setCloseError(null)
    try {
      const closed = await closePaperPosition(pos.id)
      const text = `${displaySymbol(closed.symbol)} · position clôturée`
      setNotice({ ok: true, text })
      afterPaperOrJournalAction(true, text, ['portfolio', 'journal', 'operations', 'screener'])
      setCloseConfirm(false)
      await refresh()
    } catch (err: unknown) {
      const raw = err instanceof Error ? err.message : 'Échec clôture'
      setCloseError(raw.replace(/^[a-z_]+: /, ''))
      afterPaperOrJournalAction(false, raw)
    } finally {
      setCloseConfirming(false)
      closeLock.current = false
    }
  }

  const open = pos ? String(pos.status).toUpperCase() === 'OPEN' : false
  const base = pos ? displaySymbol(pos.symbol) : '—'
  const dir = directionWords(pos?.direction)
  const unrealized = live?.unrealized_pnl ?? null
  const unrealizedPct = live?.unrealized_pct ?? null
  const mark = live?.current_price ?? null

  return (
    <>
      <dialog
        ref={dialogRef}
        className="fiche-dialog"
        onCancel={(e) => {
          e.preventDefault()
          dialogRef.current?.close()
        }}
      >
        <div className="dialog-body">
          <div className="dialog-head">
            <h2>
              {dir.title} · {base} / USDT
            </h2>
            <button type="button" onClick={() => dialogRef.current?.close()} aria-label="Fermer">
              ×
            </button>
          </div>

          {badge(open ? 'OUVERTE' : pos ? 'CLÔTURÉE' : '—')}
          {live?.mark_stale ? badge('MARK STALE', 'amber') : null}
          <p>
            Fiche position · paper · {pos?.timeframe?.toUpperCase() ?? '—'}
            {loading ? ' · chargement…' : ''}
          </p>

          {error && (
            <div className="notice" style={{ marginTop: 12, ...actionNoticeStyle(false) }}>
              {error}
            </div>
          )}
          {notice && (
            <div
              className="notice"
              style={{ marginTop: 12, ...actionNoticeStyle(notice.ok) }}
              role="status"
            >
              {notice.text}
            </div>
          )}

          {!pos && !loading && !error && (
            <p style={{ fontSize: 12, color: 'var(--muted)' }}>
              — · position absente (id inconnu)
            </p>
          )}

          {pos && (
            <>
              <div className="statline">
                <span>Sens</span>
                <b>
                  {dir.title}
                  <span className="fiche-term-hint">{dir.detail}</span>
                </b>
              </div>
              <div className="statline">
                <span>Entrée</span>
                <b className="mono">
                  {price(pos.entry_price)}
                  <span className="fiche-term-hint">
                    {new Date(pos.entry_time).toLocaleString('fr-FR')}
                  </span>
                </b>
              </div>
              <div className="statline">
                <span>Stop</span>
                <b className="mono">
                  {pos.stop_price != null
                    ? price(pos.stop_price)
                    : '— · stop_price absent'}
                </b>
              </div>
              <div className="statline">
                <span>Objectif</span>
                <b className="mono">
                  {pos.take_profit_price != null
                    ? price(pos.take_profit_price)
                    : '— · take_profit_price absent'}
                </b>
              </div>
              <div className="statline">
                <span>Quantité</span>
                <b className="mono">
                  {pos.qty != null ? pos.qty.toPrecision(4) : '— · qty absente'}
                </b>
              </div>
              <div className="statline">
                <span>Notional</span>
                <b className="mono">{eur(pos.notional)}</b>
              </div>
              <div className="statline">
                <span>Durée</span>
                <b>{holdingLabel(pos.entry_time, pos.exit_time)}</b>
              </div>
              <div className="statline">
                <span>Origine</span>
                <b>
                  {pos.source === 'auto_watchlist'
                    ? 'Auto watchlist'
                    : pos.source === 'user_confirmed'
                      ? 'Confirmé utilisateur'
                      : pos.source || '— · source absente'}
                </b>
              </div>

              {open ? (
                <>
                  <div className="statline">
                    <span>Mark</span>
                    <b className="mono">
                      {mark != null ? price(mark) : '— · mark indisponible'}
                    </b>
                  </div>
                  <div className="statline">
                    <span>P&amp;L latent</span>
                    <b className={`mono ${toneClass(unrealized)}`.trim()}>
                      {signedEur(unrealized)}
                      {unrealizedPct != null ? ` · ${pct(unrealizedPct, 2)}` : ''}
                      {unrealized == null ? (
                        <span className="fiche-term-hint">
                          — · unrealized_pnl absent (overview)
                        </span>
                      ) : null}
                    </b>
                  </div>
                  <div style={{ marginTop: 12 }}>
                    <PositionScenariosDisclosure positionId={pos.id} />
                  </div>
                </>
              ) : (
                <>
                  <div className="statline">
                    <span>Sortie</span>
                    <b className="mono">
                      {pos.exit_price != null
                        ? price(pos.exit_price)
                        : '— · exit_price absent'}
                      <span className="fiche-term-hint">
                        {pos.exit_time
                          ? new Date(pos.exit_time).toLocaleString('fr-FR')
                          : '— · exit_time absent'}
                      </span>
                    </b>
                  </div>
                  <div className="statline">
                    <span>P&amp;L réalisé</span>
                    <b className={`mono ${toneClass(pos.realized_pnl ?? null)}`.trim()}>
                      {signedEur(pos.realized_pnl)}
                      {pos.pnl_pct != null ? ` · ${pct(pos.pnl_pct, 2)}` : ''}
                    </b>
                  </div>
                  <div className="statline">
                    <span>Raison de sortie</span>
                    <b>{exitReasonLabel(pos.exit_reason)}</b>
                  </div>
                </>
              )}

              {(pos.partial_exits?.length ?? 0) > 0 && (
                <div className="table-wrap" style={{ marginTop: 16 }}>
                  <table>
                    <thead>
                      <tr>
                        <th>PRISE PARTIELLE</th>
                        <th>R</th>
                        <th>QTY</th>
                        <th>PNL</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pos.partial_exits!.map((pe) => (
                        <tr key={pe.seq}>
                          <td>#{pe.seq}</td>
                          <td className="mono">{pe.r_multiple.toFixed(2)}R</td>
                          <td className="mono">{pe.qty.toPrecision(4)}</td>
                          <td className="mono">{signedEur(pe.realized_pnl)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <div className="notice blue" style={{ marginTop: 20 }}>
                Paper uniquement — aucun ordre réel. Calques / mini-chart : suite phase B.
              </div>

              {open && (
                <button
                  type="button"
                  className="suggestion"
                  style={{ width: '100%', marginTop: 16 }}
                  disabled={closeConfirming}
                  onClick={() => {
                    setCloseError(null)
                    setCloseConfirm(true)
                  }}
                >
                  Fermer la position →
                </button>
              )}

              <div className="dialog-actions">
                <button
                  type="button"
                  onClick={() => {
                    dialogRef.current?.close()
                    navigate(`/app/market?symbol=${encodeURIComponent(pos.symbol)}`)
                  }}
                >
                  Voir le graphique
                </button>
                <button
                  type="button"
                  className="primary"
                  onClick={() => {
                    openDecisionFiche(pos.symbol, pos.timeframe || '1h')
                  }}
                >
                  Fiche décision
                </button>
              </div>
            </>
          )}

          {!pos && !loading && (
            <div className="dialog-actions">
              <button type="button" className="primary" onClick={() => dialogRef.current?.close()}>
                Fermer
              </button>
            </div>
          )}
        </div>
      </dialog>

      {closeConfirm && pos && (
        <PaperCloseConfirmSheet
          position={pos}
          confirming={closeConfirming}
          error={closeError}
          onConfirm={() => void executeClose()}
          onCancel={() => {
            if (!closeConfirming) setCloseConfirm(false)
          }}
        />
      )}
    </>
  )
}
