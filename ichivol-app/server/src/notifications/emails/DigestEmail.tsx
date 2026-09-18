import {
  Body,
  Container,
  Head,
  Heading,
  Hr,
  Html,
  Preview,
  Section,
  Text,
} from '@react-email/components'

export interface DigestEmailProps {
  appUrl: string
  generatedAt: string
  paper: {
    numOpenPositions: number
    numClosedTrades: number
    totalReturn: number | null
    winRate: number | null
  } | null
  evidence: {
    totalRows: number
    distinctDays: number
    latestPairs: number
    lastRunAt: string | null
    pipelineBeatsIchimokuSharpe: { beats: number; compared: number } | null
  } | null
}

function fmtPct(v: number | null): string {
  if (v == null) return '—'
  return `${(v * 100).toFixed(1)}%`
}

export function DigestEmail({ appUrl, generatedAt, paper, evidence }: DigestEmailProps) {
  const edge = evidence?.pipelineBeatsIchimokuSharpe
  return (
    <Html>
      <Head />
      <Preview>IchiVol — résumé quotidien (paper trading + preuve edge)</Preview>
      <Body style={{ backgroundColor: '#f5f5f4', fontFamily: 'sans-serif', padding: '24px 0' }}>
        <Container
          style={{
            backgroundColor: '#ffffff',
            borderRadius: 8,
            padding: 24,
            maxWidth: 480,
            margin: '0 auto',
            border: '1px solid #e5e5e5',
          }}
        >
          <Heading style={{ fontSize: 18, margin: '0 0 4px' }}>IchiVol — résumé du jour</Heading>
          <Text style={{ color: '#a3a3a3', fontSize: 12, margin: '0 0 16px' }}>{generatedAt}</Text>

          <Section>
            <Heading as="h2" style={{ fontSize: 14, margin: '0 0 8px' }}>
              Paper trading (auto_watchlist) — condition 2
            </Heading>
            {paper ? (
              <>
                <Text style={{ margin: '2px 0', fontSize: 14 }}>
                  Positions ouvertes : <strong>{paper.numOpenPositions}</strong>
                </Text>
                <Text style={{ margin: '2px 0', fontSize: 14 }}>
                  Trades clôturés : <strong>{paper.numClosedTrades}</strong>
                </Text>
                <Text style={{ margin: '2px 0', fontSize: 14 }}>
                  Rendement composé : <strong>{fmtPct(paper.totalReturn)}</strong> · Win rate :{' '}
                  <strong>{fmtPct(paper.winRate)}</strong>
                </Text>
              </>
            ) : (
              <Text style={{ fontSize: 14, color: '#a3a3a3' }}>Indisponible aujourd'hui.</Text>
            )}
          </Section>

          <Hr style={{ margin: '16px 0' }} />

          <Section>
            <Heading as="h2" style={{ fontSize: 14, margin: '0 0 8px' }}>
              Preuve edge backtest — condition 1
            </Heading>
            {evidence ? (
              <>
                <Text style={{ margin: '2px 0', fontSize: 14 }}>
                  {evidence.totalRows} snapshots · {evidence.distinctDays} j d'historique ·{' '}
                  {evidence.latestPairs} paires au dernier cycle
                </Text>
                <Text style={{ margin: '2px 0', fontSize: 14 }}>
                  PIPELINE bat Ichimoku (Sharpe) :{' '}
                  <strong>{edge ? `${edge.beats}/${edge.compared}` : 'pas encore comparable'}</strong>
                </Text>
                <Text style={{ margin: '2px 0', fontSize: 12, color: '#a3a3a3' }}>
                  Dernier cycle : {evidence.lastRunAt ?? 'jamais'}
                </Text>
              </>
            ) : (
              <Text style={{ fontSize: 14, color: '#a3a3a3' }}>Indisponible aujourd'hui.</Text>
            )}
          </Section>

          <Hr style={{ margin: '16px 0' }} />
          <Text style={{ fontSize: 13 }}>
            Ce résumé est informatif — aucune décision d'exécution n'est prise ici.{' '}
            <a href={appUrl}>Ouvrir IchiVol</a>
          </Text>
        </Container>
      </Body>
    </Html>
  )
}

export default DigestEmail
