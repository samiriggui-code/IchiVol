import type { PaperPosition } from '../../lib/paper'
import { signedEur } from '../../lib/tradeStory'

export const NOTE_MAX = 500

export const pctFmt = new Intl.NumberFormat('fr-FR', {
  style: 'percent',
  signDisplay: 'exceptZero',
  maximumFractionDigits: 2,
  minimumFractionDigits: 1,
})

export function fmtWhen(iso: string): string {
  return new Date(iso).toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function tone(v: number | null | undefined): string {
  if (v == null || v === 0) return ''
  return v > 0 ? 'up' : 'down'
}

export function fmtPerf(pnlPct: number | null | undefined): string {
  if (pnlPct == null) return '—'
  return pctFmt.format(pnlPct / 100)
}

export function fmtResultat(p: PaperPosition): string {
  if (p.realized_pnl != null && Number.isFinite(p.realized_pnl)) {
    return signedEur(p.realized_pnl)
  }
  return '—'
}

export function downloadCsv(filename: string, headers: string[], rows: string[][]) {
  const esc = (c: string) => `"${c.replace(/"/g, '""')}"`
  const lines = [headers.map(esc).join(','), ...rows.map((r) => r.map(esc).join(','))]
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
