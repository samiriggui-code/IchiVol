import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { labelPaperOrderReason } from '../../lib/paperLabels'
import type { EquityPeriod } from '../../pages/desk/deskFormat'
import { fmtEur, fmtPrice } from '../../pages/desk/deskFormat'
import {
  buildPctSeries,
  buildTrades,
  dodgeLabels,
  fmtSignedPct,
  heldAt,
  lerpPctAt,
  pctAxis,
  periodCutoffMs,
  valueAt,
  type PctPoint,
  type TradeMark,
  type TradeOrder,
} from './equityTrajectory'
import { DeciderBadge } from '../decider/DeciderBadge'
import type { Decider } from '../../lib/decider'
import './EquityTrajectory.css'

export type TrajectoryBook = {
  code: string
  label: string
  color: string
  initialCash: number | null
  points: { t: string; equity: number }[]
  /** Symboles tenus maintenant (positions ouvertes du livre). */
  openSymbols: string[]
}

type Prepared = TrajectoryBook & { series: PctPoint[]; base: number }

const MARK_TITLE: Record<TradeMark['kind'], string> = {
  entry_long: 'Achat',
  entry_short: 'Vente à découvert',
  exit: 'Clôture',
}

/** Largeur de la colonne des étiquettes de fin de courbe (nom + valeur), selon la place. */
const LABEL_COL = { wide: 176, mid: 120 } as const
const LABEL_GAP = 16

function markExplain(m: TradeMark): string {
  if (m.kind === 'entry_long') return 'Le portefeuille ouvre une position acheteuse : il gagne si le prix monte.'
  if (m.kind === 'entry_short') return 'Le portefeuille ouvre une position vendeuse : il gagne si le prix baisse.'
  return m.closedSide === 'short'
    ? 'Le portefeuille rachète et ferme sa vente à découvert.'
    : 'Le portefeuille revend et ferme sa position acheteuse.'
}

function fmtWhen(ms: number): string {
  const txt = new Date(ms).toLocaleString('fr-FR', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
  return txt.charAt(0).toUpperCase() + txt.slice(1)
}

function fmtTick(ms: number, spanMs: number): string {
  const d = new Date(ms)
  if (spanMs <= 2 * 86_400_000) return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' }).replace('.', '')
}

function fmtQty(v: number): string {
  return v.toLocaleString('fr-FR', { maximumFractionDigits: v >= 100 ? 0 : 4 })
}

/** Valeur d'étiquette de fin de courbe, toujours avec une décimale : « +27,0 % ». */
function fmtEndPct(v: number): string {
  const n = Math.abs(v * 100).toLocaleString('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
  return `${v > 0 ? '+' : v < 0 ? '−' : ''}${n} %`
}

function truncate(s: string, max: number): string {
  return s.length <= max ? s : `${s.slice(0, max - 1).trimEnd()}…`
}

/** Graduations de dates : jamais sur un bord, espacées régulièrement. */
function timeTicks(t0: number, t1: number, n: number): number[] {
  return Array.from({ length: n }, (_, i) => t0 + ((t1 - t0) * (i + 0.5)) / n)
}

function MarkGlyph({ kind, x, y, color, size = 1 }: { kind: TradeMark['kind']; x: number; y: number; color: string; size?: number }) {
  const s = 5.5 * size
  if (kind === 'exit') {
    return <circle cx={x} cy={y} r={4.5 * size} fill="var(--eqt-surface)" stroke={color} strokeWidth={2} />
  }
  const up = kind === 'entry_long'
  const pts = up
    ? `${x},${y - s} ${x + s},${y + s * 0.75} ${x - s},${y + s * 0.75}`
    : `${x},${y + s} ${x + s},${y - s * 0.75} ${x - s},${y - s * 0.75}`
  return <polygon points={pts} fill={color} stroke="var(--eqt-surface)" strokeWidth={1.5} strokeLinejoin="round" />
}

export function EquityTrajectory({
  books,
  orders,
  period,
  deciders = {},
}: {
  books: TrajectoryBook[]
  orders: TradeOrder[]
  period: EquityPeriod
  /** Qui a décidé chaque lot (id de position → moteur seul / Ève / manuel), affiché dans l'info-bulle. */
  deciders?: Record<string, Decider>
}) {
  const plotRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(360)
  const [hoverMs, setHoverMs] = useState<number | null>(null)
  const [focus, setFocus] = useState<string | null>(null)
  const [activeMark, setActiveMark] = useState<string | null>(null)

  useEffect(() => {
    const el = plotRef.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => {
      const w = Math.round(entry?.contentRect.width ?? 0)
      if (w > 0) setWidth(w)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    setHoverMs(null)
    setActiveMark(null)
  }, [period])

  const cutoff = useMemo(() => periodCutoffMs(period), [period])

  const prepared = useMemo<Prepared[]>(
    () =>
      books
        .map((b) => {
          const series = buildPctSeries(b.points, b.initialCash, cutoff)
          const base = b.initialCash && b.initialCash > 0 ? b.initialCash : (series[0]?.equity ?? 0)
          return { ...b, series, base }
        })
        .filter((b) => b.series.length > 0),
    [books, cutoff],
  )

  const trades = useMemo(
    () =>
      buildTrades(
        orders,
        books.flatMap((b) => b.openSymbols.map((symbol) => ({ bookCode: b.code, symbol }))),
      ),
    [orders, books],
  )

  // Étroit : pas d'étiquettes de fin de courbe, la liste en dessous sert de légende.
  const compact = width < 520
  const labelCol = compact ? 0 : width < 760 ? LABEL_COL.mid : LABEL_COL.wide
  const h = compact ? 240 : 320
  const padL = 46
  const padR = compact ? 12 : labelCol
  const padT = 18
  const padB = 26
  const innerW = Math.max(40, width - padL - padR)
  const innerH = h - padT - padB

  const geo = useMemo(() => {
    if (prepared.length === 0) return null
    const t0 = Math.max(cutoff, Math.min(...prepared.map((b) => b.series[0]!.ms)))
    const t1 = Math.max(...prepared.map((b) => b.series[b.series.length - 1]!.ms))
    if (!(t1 > t0)) return null
    // Chaque courbe va jusqu'au bord droit avec sa dernière valeur connue.
    const series = prepared.map((b) => {
      const last = b.series[b.series.length - 1]!
      return last.ms < t1 ? [...b.series, { ...last, ms: t1 }] : b.series
    })
    const vals = series.flat().map((p) => p.pct)
    const axis = pctAxis(Math.min(...vals), Math.max(...vals))
    const yAt = (pct: number) => padT + ((axis.max - pct) / (axis.max - axis.min)) * innerH
    const xAt = (ms: number) => padL + ((Math.min(Math.max(ms, t0), t1) - t0) / (t1 - t0)) * innerW
    const xEnd = padL + innerW
    const traces = prepared.map((b, i) => {
      const s = series[i]!
      const last = s[s.length - 1]!
      const d = s.map((p, k) => `${k ? 'L' : 'M'}${xAt(p.ms).toFixed(1)},${yAt(p.pct).toFixed(1)}`).join(' ')
      const area = `${d} L${xEnd.toFixed(1)},${yAt(0).toFixed(1)} L${xAt(s[0]!.ms).toFixed(1)},${yAt(0).toFixed(1)} Z`
      return { book: b, series: s, d, area, last, yEnd: yAt(last.pct) }
    })
    const labelYs = dodgeLabels(
      traces.map((t) => t.yEnd),
      LABEL_GAP,
      padT + LABEL_GAP / 2,
      padT + innerH - LABEL_GAP / 2,
    )
    const xTicks = timeTicks(t0, t1, compact ? 3 : 5)
    const marks = trades.marks
      .filter((m) => m.ms >= t0 && m.ms <= t1)
      .map((m) => {
        const tr = traces.find((t) => t.book.code === m.bookCode)
        if (!tr) return null
        const pct = lerpPctAt(tr.series, m.ms)
        if (pct == null) return null
        return { ...m, x: xAt(m.ms), y: yAt(pct), pct, color: tr.book.color }
      })
      .filter((m): m is TradeMark & { x: number; y: number; pct: number; color: string } => m != null)
    return { t0, t1, axis, yAt, xAt, xEnd, traces, labelYs, xTicks, marks }
  }, [prepared, trades, cutoff, innerW, innerH, compact])

  if (!geo) {
    return (
      <div className="eqt" ref={plotRef}>
        <p className="eqt-empty">
          Pas encore assez d’historique de capital sur cette période pour tracer les portefeuilles. Essayez une
          période plus longue.
        </p>
      </div>
    )
  }

  const { t0, t1, axis, yAt, xAt, xEnd, traces, labelYs, xTicks, marks } = geo
  const readMs = hoverMs ?? t1
  const stepDigits = axis.step < 0.001 ? 2 : axis.step < 0.01 ? 1 : 0
  // Les repères de trades n'apparaissent que sur le portefeuille mis en avant : les courbes restent lisibles.
  const visibleMarks = focus ? marks.filter((m) => m.bookCode === focus) : []
  const mark = marks.find((m) => m.id === activeMark) ?? null
  const focusTrace = focus ? traces.find((t) => t.book.code === focus) : null
  // Largeur moyenne : le nom seul (la valeur est dans la liste en dessous).
  const withValue = labelCol >= LABEL_COL.wide
  const nameMax = withValue ? 16 : 14

  const rows = traces
    .map((t) => {
      const v = valueAt(t.series, readMs)
      const held = heldAt(trades.positions, t.book.code, readMs)
      return { t, v, held }
    })
    .sort((a, b) => (b.v?.pct ?? -Infinity) - (a.v?.pct ?? -Infinity))

  const onMove = (e: ReactPointerEvent<SVGRectElement>) => {
    const box = e.currentTarget.getBoundingClientRect()
    const r = Math.min(1, Math.max(0, (e.clientX - box.left) / Math.max(1, box.width)))
    setHoverMs(t0 + r * (t1 - t0))
  }

  const tipLeft = mark ? Math.min(Math.max(4, mark.x - 120), width - 244) : 0
  // Assez de place au-dessus du repère ? Sinon l'info-bulle s'ouvre dessous (jamais sous l'en-tête de l'app).
  const tipBelow = mark ? mark.y < 250 : false
  const hoverX = hoverMs != null ? xAt(hoverMs) : null
  const hoverLabelAnchor = hoverX == null ? 'middle' : hoverX < padL + 60 ? 'start' : hoverX > xEnd - 60 ? 'end' : 'middle'

  return (
    <div className="eqt" ref={plotRef}>
      <p className="eqt-intro">
        Gain ou perte de chaque portefeuille depuis son lancement, en % de son capital de départ.
        {focus ? ' Repères : ' : ' Touchez un portefeuille pour voir ses trades.'}
        {focus ? (
          <span className="eqt-keys" aria-label="Repères">
            <span>
              <svg viewBox="0 0 16 16" aria-hidden="true">
                <MarkGlyph kind="entry_long" x={8} y={8.5} color={focusTrace?.book.color ?? 'currentColor'} size={0.9} />
              </svg>
              achat
            </span>
            <span>
              <svg viewBox="0 0 16 16" aria-hidden="true">
                <MarkGlyph kind="entry_short" x={8} y={7.5} color={focusTrace?.book.color ?? 'currentColor'} size={0.9} />
              </svg>
              vente à découvert
            </span>
            <span>
              <svg viewBox="0 0 16 16" aria-hidden="true">
                <MarkGlyph kind="exit" x={8} y={8} color={focusTrace?.book.color ?? 'currentColor'} size={0.9} />
              </svg>
              clôture
            </span>
          </span>
        ) : null}
      </p>

      <div className="eqt-plot">
        <svg
          width={width}
          height={h}
          viewBox={`0 0 ${width} ${h}`}
          role="img"
          aria-label={`Performance de ${traces.length} portefeuilles en %, période ${period}`}
        >
          {axis.ticks.map((v) => {
            const y = yAt(v)
            const zero = v === 0
            return (
              <g key={v}>
                <line x1={padL} x2={xEnd} y1={y} y2={y} className={zero ? 'eqt-zero' : 'eqt-grid'} />
                <text x={padL - 8} y={y + 3.5} className={zero ? 'eqt-axis is-zero' : 'eqt-axis'} textAnchor="end">
                  {fmtSignedPct(v, stepDigits)}
                </text>
              </g>
            )
          })}
          {xTicks.map((ms) => (
            <g key={ms}>
              <line x1={xAt(ms)} x2={xAt(ms)} y1={padT + innerH} y2={padT + innerH + 4} className="eqt-tick" />
              <text x={xAt(ms)} y={h - 7} className="eqt-axis" textAnchor="middle">
                {fmtTick(ms, t1 - t0)}
              </text>
            </g>
          ))}

          {focusTrace ? <path d={focusTrace.area} fill={focusTrace.book.color} opacity={0.1} /> : null}
          {traces.map(({ book, d }) => (
            <path
              key={book.code}
              d={d}
              fill="none"
              stroke={book.color}
              strokeWidth={focus === book.code ? 2.5 : 2}
              strokeLinejoin="round"
              strokeLinecap="round"
              opacity={focus && focus !== book.code ? 0.18 : 1}
            />
          ))}
          {traces.map(({ book, last, yEnd }) =>
            focus && focus !== book.code ? null : (
              <circle key={`end-${book.code}`} cx={xAt(last.ms)} cy={yEnd} r={4} fill={book.color} stroke="var(--eqt-surface)" strokeWidth={2} />
            ),
          )}

          {!compact
            ? traces.map(({ book, last, yEnd }, i) => {
                const dim = focus != null && focus !== book.code
                const y = labelYs[i]!
                const x0 = xEnd + 6
                const x1 = xEnd + 18
                return (
                  <g
                    key={`lbl-${book.code}`}
                    className={`eqt-endlabel${dim ? ' is-dim' : ''}`}
                    onClick={() => setFocus(focus === book.code ? null : book.code)}
                  >
                    {Math.abs(y - yEnd) > 1 ? (
                      <path d={`M${x0},${yEnd} C${x0 + 6},${yEnd} ${x1 - 6},${y} ${x1},${y}`} fill="none" stroke={book.color} strokeWidth={1} opacity={0.6} />
                    ) : null}
                    <text x={x1 + 4} y={y + 3.5} className="eqt-endname">
                      {truncate(book.label, nameMax)}
                    </text>
                    {withValue ? (
                      <text x={xEnd + labelCol - 6} y={y + 3.5} className="eqt-endval" textAnchor="end">
                        {fmtEndPct(last.pct)}
                      </text>
                    ) : null}
                  </g>
                )
              })
            : null}

          <rect
            className="eqt-hit"
            x={padL}
            y={padT}
            width={innerW}
            height={innerH}
            onPointerDown={(e) => {
              setActiveMark(null)
              onMove(e)
            }}
            onPointerMove={(e) => {
              if (e.pointerType === 'mouse' || e.buttons > 0) onMove(e)
            }}
            onPointerLeave={(e) => {
              if (e.pointerType === 'mouse') setHoverMs(null)
            }}
          />

          {hoverMs != null && hoverX != null ? (
            <g pointerEvents="none">
              <line x1={hoverX} x2={hoverX} y1={padT} y2={padT + innerH} className="eqt-cross" />
              <text x={hoverX} y={padT - 6} className="eqt-axis eqt-hover-date" textAnchor={hoverLabelAnchor}>
                {fmtWhen(hoverMs)}
              </text>
              {traces.map(({ book, series }) => {
                if (focus && focus !== book.code) return null
                const v = valueAt(series, hoverMs)
                if (!v) return null
                return <circle key={`x-${book.code}`} cx={hoverX} cy={yAt(v.pct)} r={4.5} fill={book.color} stroke="var(--eqt-surface)" strokeWidth={2} />
              })}
            </g>
          ) : null}

          {visibleMarks.map((m) => (
            <g
              key={m.id}
              className={`eqt-mark${activeMark === m.id ? ' is-active' : ''}`}
              role="button"
              tabIndex={0}
              aria-label={`${MARK_TITLE[m.kind]} ${m.symbol}, ${m.bookLabel}, ${fmtWhen(m.ms)}`}
              onPointerEnter={(e) => {
                if (e.pointerType === 'mouse') setActiveMark(m.id)
              }}
              onPointerLeave={(e) => {
                if (e.pointerType === 'mouse') setActiveMark(null)
              }}
              onClick={(e) => {
                e.stopPropagation()
                setActiveMark(activeMark === m.id ? null : m.id)
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') setActiveMark(activeMark === m.id ? null : m.id)
              }}
            >
              <circle cx={m.x} cy={m.y} r={12} fill="transparent" />
              <MarkGlyph kind={m.kind} x={m.x} y={m.y} color={m.color} size={activeMark === m.id ? 1.3 : 1} />
            </g>
          ))}
        </svg>

        {mark ? (
          <div
            className={`eqt-tip${tipBelow ? ' is-below' : ''}`}
            role="tooltip"
            style={{ left: tipLeft, top: tipBelow ? mark.y + 16 : mark.y - 16 }}
          >
            <div className="eqt-head">
              <strong>
                {MARK_TITLE[mark.kind]} {mark.symbol}
              </strong>
              <button type="button" className="eqt-tip-close" aria-label="Fermer" onClick={() => setActiveMark(null)}>
                ×
              </button>
            </div>
            <p className="eqt-tip-book">
              <i style={{ background: mark.color }} />
              {mark.bookLabel}
              {mark.positionId && deciders[mark.positionId] ? (
                <DeciderBadge decider={deciders[mark.positionId]!} compact />
              ) : null}
            </p>
            <p>{markExplain(mark)}</p>
            <dl>
              <div>
                <dt>Quand</dt>
                <dd>{fmtWhen(mark.ms)}</dd>
              </div>
              <div>
                <dt>Quantité</dt>
                <dd>
                  {fmtQty(mark.qty)} à {mark.price > 0 ? fmtPrice(mark.price) : '—'}
                </dd>
              </div>
              <div>
                <dt>Montant</dt>
                <dd>{mark.notional > 0 ? fmtEur(mark.notional, 2) : '—'}</dd>
              </div>
              {mark.fee > 0 ? (
                <div>
                  <dt>Frais</dt>
                  <dd>{fmtEur(mark.fee, 2)}</dd>
                </div>
              ) : null}
              {mark.reason && labelPaperOrderReason(mark.reason) && mark.kind === 'exit' ? (
                <div>
                  <dt>Raison</dt>
                  <dd>{labelPaperOrderReason(mark.reason)}</dd>
                </div>
              ) : null}
              {mark.grossPnl != null ? (
                <div>
                  <dt>Résultat du trade</dt>
                  <dd className={mark.grossPnl >= 0 ? 'up' : 'down'}>
                    {mark.grossPnl >= 0 ? 'gain ' : 'perte '}
                    {fmtEur(Math.abs(mark.grossPnl), 2)} (avant frais)
                  </dd>
                </div>
              ) : null}
              <div>
                <dt>Portefeuille à ce moment</dt>
                <dd>{fmtSignedPct(mark.pct)}</dd>
              </div>
            </dl>
          </div>
        ) : null}
      </div>

      <div className="eqt-readout">
        <div className="eqt-head">
          <span>{hoverMs != null ? fmtWhen(hoverMs) : 'Aujourd’hui'}</span>
          {hoverMs != null ? (
            <button type="button" onClick={() => setHoverMs(null)}>
              Revenir à aujourd’hui
            </button>
          ) : focus ? (
            <button type="button" onClick={() => setFocus(null)}>
              Tout afficher
            </button>
          ) : null}
        </div>
        <ol>
          {rows.map(({ t, v, held }) => {
            const on = focus === t.book.code
            const pnl = v ? v.equity - t.book.base : null
            return (
              <li key={t.book.code} className={focus && !on ? 'is-dim' : undefined}>
                <button type="button" aria-pressed={on} onClick={() => setFocus(on ? null : t.book.code)}>
                  <i className="eqt-swatch" style={{ background: t.book.color }} />
                  <span className="eqt-name">{t.book.label}</span>
                  <span className="eqt-held">
                    {!v
                      ? 'pas encore lancé à cette date'
                      : held.length === 0
                        ? 'aucune position'
                        : held.map((p) => `${p.symbol} ${p.side === 'long' ? '↑' : '↓'}`).join(' · ')}
                  </span>
                  <span className={`eqt-val${v ? (v.pct > 0 ? ' up' : v.pct < 0 ? ' down' : '') : ''}`}>
                    {v ? fmtSignedPct(v.pct) : '—'}
                  </span>
                  <span className="eqt-eur">{pnl != null ? `${pnl >= 0 ? '+' : '−'}${fmtEur(Math.abs(pnl), 0)}` : ''}</span>
                </button>
              </li>
            )
          })}
        </ol>
      </div>
    </div>
  )
}
