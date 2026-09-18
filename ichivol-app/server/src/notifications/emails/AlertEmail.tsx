import {
  Body,
  Container,
  Head,
  Heading,
  Hr,
  Html,
  Preview,
  Text,
} from '@react-email/components'

export interface AlertEmailProps {
  database: boolean
  engine: boolean
  checkedAt: string
  appUrl: string
}

function StatusLine({ label, ok }: { label: string; ok: boolean }) {
  return (
    <Text style={{ margin: '4px 0', fontFamily: 'monospace', fontSize: 14 }}>
      {ok ? '✅' : '🔴'} {label} — {ok ? 'OK' : 'DOWN'}
    </Text>
  )
}

export function AlertEmail({ database, engine, checkedAt, appUrl }: AlertEmailProps) {
  return (
    <Html>
      <Head />
      <Preview>IchiVol — un composant système ne répond plus</Preview>
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
          <Heading style={{ fontSize: 18, margin: '0 0 12px' }}>⚠️ IchiVol — alerte système</Heading>
          <Text style={{ color: '#525252', fontSize: 14 }}>
            `/api/health` a répondu en échec au dernier contrôle. Positions papier et collecte
            backtest peuvent être interrompues tant que ce n'est pas réglé.
          </Text>
          <Hr style={{ margin: '16px 0' }} />
          <StatusLine label="Base de données" ok={database} />
          <StatusLine label="Moteur Python" ok={engine} />
          <Text style={{ color: '#a3a3a3', fontSize: 12, marginTop: 16 }}>Vérifié à {checkedAt}</Text>
          <Hr style={{ margin: '16px 0' }} />
          <Text style={{ fontSize: 13 }}>
            Vérifie les conteneurs (`docker compose ps` / `docker compose logs`) sur le VPS, ou{' '}
            <a href={appUrl}>ouvre l'app</a> pour confirmer.
          </Text>
        </Container>
      </Body>
    </Html>
  )
}

export default AlertEmail
