/**
 * Schéma Ichimoku de l'accueil et de la connexion : bougies, Tenkan, Kijun, nuage et volume.
 * Série synthétique déterministe, sans aucun prix affiché : c'est une illustration, pas une donnée.
 */

type Bar = { o: number; h: number; l: number; c: number; v: number }

const N = 64
const W = 600
const H = 220
const PRICE_H = 160
const VOL_TOP = 172

function rng(seed: number) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function buildSeries(): Bar[] {
  const r = rng(3)
  const bars: Bar[] = []
  let p = 100
  for (let i = 0; i < N + 52; i++) {
    // Range puis cassure haussière dans le dernier tiers.
    const drift = i < 88 ? 0.0012 * Math.sin(i / 7) : 0.0032
    const o = p
    const c = o * (1 + drift + (r() - 0.5) * 0.011)
    const h = Math.max(o, c) * (1 + r() * 0.004)
    const l = Math.min(o, c) * (1 - r() * 0.004)
    const v = (0.35 + r() * 0.65) * (i > 92 ? 1.7 : 1)
    bars.push({ o, h, l, c, v })
    p = c
  }
  return bars
}

function mid(bars: Bar[], end: number, len: number) {
  const s = bars.slice(Math.max(0, end - len + 1), end + 1)
  return (Math.max(...s.map((b) => b.h)) + Math.min(...s.map((b) => b.l))) / 2
}

const OFFSET = 52
const SERIES = buildSeries()
const VIEW = SERIES.slice(OFFSET)
const TENKAN = VIEW.map((_, i) => mid(SERIES, i + OFFSET, 9))
const KIJUN = VIEW.map((_, i) => mid(SERIES, i + OFFSET, 26))
// Nuage projeté 26 bougies en avant : la valeur affichée en i vient de i − 26.
const SPAN_A = VIEW.map((_, i) => (mid(SERIES, i + OFFSET - 26, 9) + mid(SERIES, i + OFFSET - 26, 26)) / 2)
const SPAN_B = VIEW.map((_, i) => mid(SERIES, i + OFFSET - 26, 52))

const ALL = [...VIEW.flatMap((b) => [b.h, b.l]), ...SPAN_A, ...SPAN_B]
const MAX = Math.max(...ALL)
const MIN = Math.min(...ALL)
const VMAX = Math.max(...VIEW.map((b) => b.v))
const STEP = W / N

const y = (v: number) => 8 + ((MAX - v) / (MAX - MIN)) * (PRICE_H - 16)
const x = (i: number) => STEP * i + STEP / 2
const path = (vals: number[]) =>
  vals.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join('')
const CLOUD =
  path(SPAN_A) +
  SPAN_B.map((v, i) => `L${x(i).toFixed(1)},${y(v).toFixed(1)}`)
    .reverse()
    .join('') +
  'Z'

type Props = { className?: string }

export function IchimokuMockChart({ className }: Props) {
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      className={['ichi-sketch', className].filter(Boolean).join(' ')}
      role="img"
      aria-label="Schéma d’un nuage Ichimoku en cassure haussière, confirmée par le volume"
    >
      {[0.25, 0.5, 0.75].map((f) => (
        <line key={f} x1={0} x2={W} y1={PRICE_H * f} y2={PRICE_H * f} className="ichi-sketch-grid" />
      ))}
      <line x1={0} x2={W} y1={VOL_TOP - 4} y2={VOL_TOP - 4} className="ichi-sketch-grid" />
      <path d={CLOUD} className="ichi-sketch-cloud" />
      <path d={path(SPAN_A)} className="ichi-sketch-span" />
      <path d={path(SPAN_B)} className="ichi-sketch-span is-b" />
      <path d={path(KIJUN)} className="ichi-sketch-kijun" />
      <path d={path(TENKAN)} className="ichi-sketch-tenkan" />
      {VIEW.map((b, i) => {
        const up = b.c >= b.o
        const top = y(Math.max(b.o, b.c))
        const vh = (b.v / VMAX) * (H - VOL_TOP - 2)
        return (
          <g key={i} className={up ? 'is-up' : 'is-down'}>
            <line x1={x(i)} x2={x(i)} y1={y(b.h)} y2={y(b.l)} className="ichi-sketch-wick" />
            <rect
              x={x(i) - STEP * 0.32}
              y={top}
              width={STEP * 0.64}
              height={Math.max(1.5, y(Math.min(b.o, b.c)) - top)}
              className="ichi-sketch-body"
            />
            <rect
              x={x(i) - STEP * 0.32}
              y={H - vh}
              width={STEP * 0.64}
              height={vh}
              className="ichi-sketch-vol"
            />
          </g>
        )
      })}
    </svg>
  )
}
