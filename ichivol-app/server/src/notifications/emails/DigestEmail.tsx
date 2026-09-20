import {
  Body,
  Column,
  Container,
  Head,
  Heading,
  Hr,
  Html,
  Link,
  Preview,
  Row,
  Section,
  Text,
} from '@react-email/components'
import type { CSSProperties } from 'react'
import type { DailyBriefing } from '../briefingTypes.js'

/** IchiVol brand (aligned with camap-tokens light). */
const brand = {
  bg: '#faf8f5',
  card: '#fefdfb',
  ink: '#11151c',
  muted: '#676b73',
  border: '#ddd9d3',
  primary: '#1a7df5',
  bull: '#0ea89a',
  bear: '#dc4c3f',
  subtle: '#f6f3ee',
  sans: "Manrope, 'Segoe UI', Helvetica, Arial, sans-serif",
}

function eur(n: number | null | undefined, digits = 2): string {
  if (n == null || !Number.isFinite(n)) return '—'
  return n.toLocaleString('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    maximumFractionDigits: digits,
  })
}

function pct(n: number | null | undefined, digits = 1): string {
  if (n == null || !Number.isFinite(n)) return '—'
  const sign = n > 0 ? '+' : ''
  return `${sign}${(n * 100).toFixed(digits)} %`
}

function toneColor(v: number | null | undefined): string {
  if (v == null || v === 0) return brand.ink
  return v > 0 ? brand.bull : brand.bear
}

/** Email-safe equity sparkline as stacked bar row (no external image host). */
function EquityBars({ values }: { values: number[] }) {
  if (values.length < 2) {
    return (
      <Text style={{ ...muted, margin: 0 }}>Pas encore assez de points pour la courbe.</Text>
    )
  }
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = Math.max(1e-9, max - min)
  const last = values[values.length - 1]
  const first = values[0]
  const up = last >= first

  return (
    <Section style={{ margin: '8px 0 4px' }}>
      <Row>
        {values.map((v, i) => {
          const h = Math.round(8 + ((v - min) / span) * 36)
          return (
            <Column key={i} style={{ padding: '0 1px', verticalAlign: 'bottom', width: `${100 / values.length}%` }}>
              <Section
                style={{
                  height: h,
                  backgroundColor: up ? brand.bull : brand.bear,
                  opacity: 0.35 + (0.65 * (v - min)) / span,
                  borderRadius: 2,
                }}
              />
            </Column>
          )
        })}
      </Row>
      <Text style={{ ...muted, margin: '6px 0 0', fontSize: 11 }}>
        Trajectoire equity · {values.length} pts · {up ? 'tendance haute' : 'tendance basse'} sur la fenêtre
      </Text>
    </Section>
  )
}

function Kpi({
  label,
  value,
  sub,
  valueColor,
}: {
  label: string
  value: string
  sub?: string
  valueColor?: string
}) {
  return (
    <Column style={{ padding: '0 4px', width: '25%' }}>
      <Section style={kpiCard}>
        <Text style={kpiLabel}>{label}</Text>
        <Text style={{ ...kpiValue, color: valueColor ?? brand.ink }}>{value}</Text>
        {sub ? <Text style={kpiSub}>{sub}</Text> : null}
      </Section>
    </Column>
  )
}

export function DigestEmail({ briefing }: { briefing: DailyBriefing }) {
  const { kpis, openBook, tape, shadow, evidence, circuit, paperStats } = briefing
  const preview = `IchiVol Briefing — ${briefing.headline.slice(0, 90)}`

  return (
    <Html>
      <Head />
      <Preview>{preview}</Preview>
      <Body style={{ backgroundColor: brand.bg, fontFamily: brand.sans, padding: '28px 0', margin: 0 }}>
        <Container style={shell}>
          {/* Masthead */}
          <Section style={{ marginBottom: 20 }}>
            <Text style={logo}>IchiVol</Text>
            <Heading style={h1}>Briefing quotidien</Heading>
            <Text style={muted}>
              {briefing.portfolioLabel} · {briefing.generatedAt}
            </Text>
          </Section>

          {/* Desk headline */}
          <Section style={callout}>
            <Text style={{ ...body, margin: 0, fontWeight: 600, color: brand.ink }}>{briefing.headline}</Text>
          </Section>

          {/* KPIs */}
          <Section style={{ margin: '18px 0 8px' }}>
            <Row>
              <Kpi
                label="Equity"
                value={eur(kpis.equity)}
                sub={`Départ ${eur(kpis.initialCash, 0)}`}
                valueColor={toneColor(kpis.totalPnl)}
              />
              <Kpi
                label="P&L total"
                value={eur(kpis.totalPnl)}
                sub={pct(kpis.totalPnlPct)}
                valueColor={toneColor(kpis.totalPnl)}
              />
              <Kpi
                label="24 h"
                value={kpis.dayChange == null ? '—' : eur(kpis.dayChange)}
                sub={pct(kpis.dayChangePct)}
                valueColor={toneColor(kpis.dayChange)}
              />
              <Kpi
                label="Livre"
                value={`${kpis.openPositions}`}
                sub={`${eur(kpis.invested)} engagé`}
              />
            </Row>
          </Section>

          <Section style={{ margin: '8px 0 16px' }}>
            <Row>
              <Kpi label="Cash" value={eur(kpis.cash)} />
              <Kpi
                label="Latent"
                value={eur(kpis.unrealizedPnl)}
                valueColor={toneColor(kpis.unrealizedPnl)}
              />
              <Kpi
                label="Réalisé"
                value={eur(kpis.realizedPnl)}
                valueColor={toneColor(kpis.realizedPnl)}
              />
              <Kpi
                label="Win rate"
                value={paperStats?.winRate == null ? '—' : pct(paperStats.winRate)}
                sub={paperStats ? `${paperStats.closedTrades} clôturés` : undefined}
              />
            </Row>
          </Section>

          {/* Equity bars */}
          <Section style={block}>
            <Heading as="h2" style={h2}>
              Situation financière
            </Heading>
            <EquityBars values={briefing.equitySpark} />
            <Text style={{ ...muted, margin: '4px 0 0', fontSize: 12 }}>
              Cash {eur(kpis.cash)} · Investi {eur(kpis.invested)} · Exposition{' '}
              {kpis.equity > 0 ? `${((kpis.invested / kpis.equity) * 100).toFixed(0)} %` : '—'}
            </Text>
          </Section>

          {/* Narrative */}
          <Section style={block}>
            <Heading as="h2" style={h2}>
              Lecture desk
            </Heading>
            {briefing.narrative.map((line, i) => (
              <Text key={i} style={body}>
                {line}
              </Text>
            ))}
          </Section>

          {/* Open book */}
          <Section style={block}>
            <Heading as="h2" style={h2}>
              Livre ouvert
            </Heading>
            {openBook.length === 0 ? (
              <Text style={muted}>Aucune position — 100 % cash.</Text>
            ) : (
              openBook.slice(0, 8).map((p) => (
                <Section key={p.symbol + p.timeframe} style={rowLine}>
                  <Text style={{ ...body, margin: '0 0 2px' }}>
                    <strong>{p.label}</strong>
                    <span style={{ color: brand.muted }}>
                      {' '}
                      · {p.direction} · {p.timeframe}
                    </span>
                  </Text>
                  <Text style={{ ...muted, margin: 0, fontSize: 12 }}>
                    Investi {eur(p.notional)} · P&amp;L{' '}
                    <span style={{ color: toneColor(p.unrealizedPnl), fontWeight: 600 }}>
                      {eur(p.unrealizedPnl)}
                      {p.unrealizedPct != null ? ` (${pct(p.unrealizedPct)})` : ''}
                    </span>
                  </Text>
                </Section>
              ))
            )}
          </Section>

          {/* Today's tape */}
          <Section style={block}>
            <Heading as="h2" style={h2}>
              Tape 24 h
            </Heading>
            {tape.length === 0 ? (
              <Text style={muted}>Aucun événement paper sur les dernières 24 h.</Text>
            ) : (
              tape.map((ev, i) => (
                <Section key={i} style={rowLine}>
                  <Text style={{ ...body, margin: '0 0 2px', fontWeight: 600 }}>{ev.title}</Text>
                  <Text style={{ ...muted, margin: 0, fontSize: 12 }}>
                    {new Date(ev.time).toLocaleString('fr-FR', {
                      timeZone: 'Europe/Paris',
                      day: '2-digit',
                      month: 'short',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                    {ev.detail ? ` — ${ev.detail}` : ''}
                  </Text>
                </Section>
              ))
            )}
            {circuit && (
              <Text style={{ ...muted, marginTop: 10, fontSize: 12 }}>
                Circuit : {circuit.decisions24h} décisions · {circuit.opened24h} entrées ·{' '}
                {circuit.closed24h} sorties · {circuit.blocked24h} refus filtres
              </Text>
            )}
          </Section>

          {/* Filters + edge */}
          <Section style={block}>
            <Heading as="h2" style={h2}>
              Filtres &amp; preuve edge
            </Heading>
            {shadow ? (
              <Text style={body}>{shadow.plain}</Text>
            ) : (
              <Text style={muted}>ShadowBroker indisponible.</Text>
            )}
            {evidence ? (
              <>
                <Text style={body}>{evidence.edgePlain}</Text>
                <Text style={{ ...muted, fontSize: 12 }}>
                  {evidence.runsTotal} lancements ({evidence.totalRows} résultats) · {evidence.distinctDays} j ·{' '}
                  {evidence.latestPairs} paires dernier cycle
                  {evidence.lastRunAt
                    ? ` · maj ${new Date(evidence.lastRunAt).toLocaleString('fr-FR', { timeZone: 'Europe/Paris' })}`
                    : ''}
                </Text>
              </>
            ) : (
              <Text style={muted}>Preuve backtest indisponible.</Text>
            )}
          </Section>

          <Hr style={{ borderColor: brand.border, margin: '20px 0' }} />

          <Text style={{ ...body, marginBottom: 8 }}>
            Le PDF joint détaille ce briefing (courbe, livre, tape).{' '}
            <Link href={briefing.appUrl} style={{ color: brand.primary }}>
              Ouvrir IchiVol
            </Link>
          </Text>
          <Text style={{ ...muted, fontSize: 11, margin: 0 }}>
            Informational only — paper trading, aucune exécution réelle. IchiVol ne constitue pas un
            conseil en investissement.
          </Text>
        </Container>
      </Body>
    </Html>
  )
}

export default DigestEmail

const shell: CSSProperties = {
  backgroundColor: brand.card,
  borderRadius: 12,
  padding: '28px 28px 24px',
  maxWidth: 560,
  margin: '0 auto',
  border: `1px solid ${brand.border}`,
}

const logo: CSSProperties = {
  margin: 0,
  fontSize: 13,
  fontWeight: 700,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
  color: brand.primary,
}

const h1: CSSProperties = {
  margin: '6px 0 4px',
  fontSize: 22,
  fontWeight: 700,
  color: brand.ink,
  letterSpacing: '-0.02em',
}

const h2: CSSProperties = {
  margin: '0 0 10px',
  fontSize: 13,
  fontWeight: 700,
  letterSpacing: '0.04em',
  textTransform: 'uppercase',
  color: brand.muted,
}

const body: CSSProperties = {
  margin: '0 0 8px',
  fontSize: 14,
  lineHeight: '1.5',
  color: brand.ink,
}

const muted: CSSProperties = {
  color: brand.muted,
  fontSize: 13,
  lineHeight: '1.45',
}

const callout: CSSProperties = {
  backgroundColor: brand.subtle,
  border: `1px solid ${brand.border}`,
  borderRadius: 8,
  padding: '12px 14px',
}

const block: CSSProperties = {
  margin: '18px 0 0',
}

const rowLine: CSSProperties = {
  borderBottom: `1px solid ${brand.border}`,
  padding: '8px 0',
}

const kpiCard: CSSProperties = {
  backgroundColor: brand.subtle,
  border: `1px solid ${brand.border}`,
  borderRadius: 8,
  padding: '10px 8px',
  marginBottom: 8,
}

const kpiLabel: CSSProperties = {
  margin: 0,
  fontSize: 10,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  color: brand.muted,
}

const kpiValue: CSSProperties = {
  margin: '4px 0 0',
  fontSize: 15,
  fontWeight: 700,
  fontVariantNumeric: 'tabular-nums',
}

const kpiSub: CSSProperties = {
  margin: '2px 0 0',
  fontSize: 10,
  color: brand.muted,
}
