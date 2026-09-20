/**
 * PDF attaché au briefing quotidien — même contenu que l’email, format bureau.
 */
import {
  Document,
  Page,
  Path,
  StyleSheet,
  Svg,
  Text,
  View,
  pdf,
} from '@react-pdf/renderer'
import type { DailyBriefing } from '../briefingTypes.js'

const colors = {
  ink: '#11151c',
  muted: '#676b73',
  border: '#ddd9d3',
  primary: '#1a7df5',
  bull: '#0ea89a',
  bear: '#dc4c3f',
  subtle: '#f6f3ee',
  card: '#ffffff',
}

const styles = StyleSheet.create({
  page: {
    paddingTop: 36,
    paddingBottom: 40,
    paddingHorizontal: 40,
    fontFamily: 'Helvetica',
    fontSize: 10,
    color: colors.ink,
    backgroundColor: colors.card,
  },
  brand: {
    fontSize: 9,
    letterSpacing: 1.5,
    textTransform: 'uppercase',
    color: colors.primary,
    marginBottom: 4,
    fontFamily: 'Helvetica-Bold',
  },
  title: { fontSize: 18, fontFamily: 'Helvetica-Bold', marginBottom: 4 },
  meta: { fontSize: 9, color: colors.muted, marginBottom: 14 },
  headline: {
    backgroundColor: colors.subtle,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 4,
    padding: 10,
    marginBottom: 14,
    fontSize: 10,
    fontFamily: 'Helvetica-Bold',
    lineHeight: 1.4,
  },
  h2: {
    fontSize: 9,
    letterSpacing: 1,
    textTransform: 'uppercase',
    color: colors.muted,
    marginTop: 12,
    marginBottom: 6,
    fontFamily: 'Helvetica-Bold',
  },
  body: { fontSize: 9.5, lineHeight: 1.45, marginBottom: 5, color: colors.ink },
  muted: { fontSize: 8.5, color: colors.muted, lineHeight: 1.4 },
  kpiRow: { flexDirection: 'row', marginBottom: 6 },
  kpi: {
    flex: 1,
    backgroundColor: colors.subtle,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 4,
    padding: 7,
    marginRight: 6,
  },
  kpiLabel: { fontSize: 7, color: colors.muted, textTransform: 'uppercase', marginBottom: 2 },
  kpiValue: { fontSize: 11, fontFamily: 'Helvetica-Bold' },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    paddingVertical: 5,
  },
  footer: {
    position: 'absolute',
    bottom: 24,
    left: 40,
    right: 40,
    fontSize: 7.5,
    color: colors.muted,
  },
})

function eur(n: number | null | undefined, digits = 2): string {
  if (n == null || !Number.isFinite(n)) return '—'
  return `${n.toFixed(digits).replace('.', ',')} €`
}

function pct(n: number | null | undefined, digits = 1): string {
  if (n == null || !Number.isFinite(n)) return '—'
  const sign = n > 0 ? '+' : ''
  return `${sign}${(n * 100).toFixed(digits)} %`
}

function tone(v: number | null | undefined): string {
  if (v == null || v === 0) return colors.ink
  return v > 0 ? colors.bull : colors.bear
}

function EquityPath({ values }: { values: number[] }) {
  if (values.length < 2) return null
  const w = 480
  const h = 72
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = Math.max(1e-9, max - min)
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w
    const y = h - ((v - min) / span) * (h - 8) - 4
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })
  const d = `M ${pts.join(' L ')}`
  const up = values[values.length - 1] >= values[0]
  return (
    <Svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      <Path d={d} stroke={up ? colors.bull : colors.bear} strokeWidth={2} fill="none" />
    </Svg>
  )
}

function DigestPdfDoc({ briefing }: { briefing: DailyBriefing }) {
  const { kpis, openBook, tape, shadow, evidence, circuit, paperStats } = briefing

  return (
    <Document
      title={`IchiVol Briefing ${briefing.generatedAtIso.slice(0, 10)}`}
      author="IchiVol"
      subject="Briefing quotidien paper trading"
    >
      <Page size="A4" style={styles.page}>
        <Text style={styles.brand}>IchiVol</Text>
        <Text style={styles.title}>Briefing quotidien</Text>
        <Text style={styles.meta}>
          {briefing.portfolioLabel} ({briefing.portfolioCode}) · {briefing.generatedAt}
        </Text>

        <Text style={styles.headline}>{briefing.headline}</Text>

        <View style={styles.kpiRow}>
          <View style={styles.kpi}>
            <Text style={styles.kpiLabel}>Equity</Text>
            <Text style={[styles.kpiValue, { color: tone(kpis.totalPnl) }]}>{eur(kpis.equity)}</Text>
          </View>
          <View style={styles.kpi}>
            <Text style={styles.kpiLabel}>P&L total</Text>
            <Text style={[styles.kpiValue, { color: tone(kpis.totalPnl) }]}>
              {eur(kpis.totalPnl)} ({pct(kpis.totalPnlPct)})
            </Text>
          </View>
          <View style={styles.kpi}>
            <Text style={styles.kpiLabel}>24 h</Text>
            <Text style={[styles.kpiValue, { color: tone(kpis.dayChange) }]}>
              {kpis.dayChange == null ? '—' : eur(kpis.dayChange)}
            </Text>
          </View>
          <View style={styles.kpi}>
            <Text style={styles.kpiLabel}>Positions</Text>
            <Text style={styles.kpiValue}>{kpis.openPositions}</Text>
          </View>
        </View>

        <View style={styles.kpiRow}>
          <View style={styles.kpi}>
            <Text style={styles.kpiLabel}>Cash</Text>
            <Text style={styles.kpiValue}>{eur(kpis.cash)}</Text>
          </View>
          <View style={styles.kpi}>
            <Text style={styles.kpiLabel}>Investi</Text>
            <Text style={styles.kpiValue}>{eur(kpis.invested)}</Text>
          </View>
          <View style={styles.kpi}>
            <Text style={styles.kpiLabel}>Latent</Text>
            <Text style={[styles.kpiValue, { color: tone(kpis.unrealizedPnl) }]}>
              {eur(kpis.unrealizedPnl)}
            </Text>
          </View>
          <View style={styles.kpi}>
            <Text style={styles.kpiLabel}>Win rate</Text>
            <Text style={styles.kpiValue}>
              {paperStats?.winRate == null ? '—' : pct(paperStats.winRate)}
            </Text>
          </View>
        </View>

        <Text style={styles.h2}>Courbe de capital</Text>
        <EquityPath values={briefing.equitySpark} />
        <Text style={styles.muted}>
          {briefing.equitySpark.length} points · départ {eur(kpis.initialCash, 0)}
        </Text>

        <Text style={styles.h2}>Lecture desk</Text>
        {briefing.narrative.map((line, i) => (
          <Text key={i} style={styles.body}>
            {line}
          </Text>
        ))}

        <Text style={styles.h2}>Livre ouvert</Text>
        {openBook.length === 0 ? (
          <Text style={styles.muted}>Aucune position.</Text>
        ) : (
          openBook.map((p) => (
            <View key={p.symbol + p.timeframe} style={styles.row} wrap={false}>
              <Text>
                {p.label} · {p.direction} · {p.timeframe}
              </Text>
              <Text style={{ color: tone(p.unrealizedPnl) }}>
                {eur(p.notional)} | {eur(p.unrealizedPnl)}
              </Text>
            </View>
          ))
        )}

        <Text style={styles.h2}>Tape 24 h</Text>
        {tape.length === 0 ? (
          <Text style={styles.muted}>Aucun événement.</Text>
        ) : (
          tape.map((ev, i) => (
            <View key={i} style={styles.row} wrap={false}>
              <View style={{ flex: 1, paddingRight: 8 }}>
                <Text style={{ fontFamily: 'Helvetica-Bold' }}>{ev.title}</Text>
                <Text style={styles.muted}>{ev.detail}</Text>
              </View>
              <Text style={styles.muted}>
                {new Date(ev.time).toLocaleString('fr-FR', {
                  timeZone: 'Europe/Paris',
                  day: '2-digit',
                  month: 'short',
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </Text>
            </View>
          ))
        )}

        {circuit && (
          <Text style={[styles.muted, { marginTop: 6 }]}>
            Circuit 24 h — décisions {circuit.decisions24h} · entrées {circuit.opened24h} · sorties{' '}
            {circuit.closed24h} · refus {circuit.blocked24h}
          </Text>
        )}

        <Text style={styles.h2}>Filtres & preuve edge</Text>
        {shadow && <Text style={styles.body}>{shadow.plain}</Text>}
        {evidence && (
          <>
            <Text style={styles.body}>{evidence.edgePlain}</Text>
            <Text style={styles.muted}>
              {evidence.runsTotal} lancements ({evidence.totalRows} résultats) · {evidence.distinctDays} j · edge{' '}
              {evidence.pipelineBeats}/{evidence.pipelineCompared}
            </Text>
          </>
        )}

        <Text style={styles.footer}>
          IchiVol — briefing paper trading. Informational only, aucune exécution réelle.{' '}
          {briefing.appUrl}
        </Text>
      </Page>
    </Document>
  )
}

export async function renderDigestPdf(briefing: DailyBriefing): Promise<Buffer> {
  const instance = pdf(<DigestPdfDoc briefing={briefing} />)
  const result = await instance.toBuffer()
  if (Buffer.isBuffer(result)) return result
  const chunks: Buffer[] = []
  for await (const chunk of result as AsyncIterable<Uint8Array>) {
    chunks.push(Buffer.from(chunk))
  }
  return Buffer.concat(chunks)
}
