import 'dotenv/config'

export type ProviderName = 'anthropic' | 'openai' | 'openrouter'

export interface Config {
  port: number
  isProd: boolean
  jwtSecret: string
  llmProvider: ProviderName
  llmModel: string
  anthropicApiKey: string | undefined
  openaiApiKey: string | undefined
  openrouterApiKey: string | undefined
  engineUrl: string
  smtp: {
    host: string | undefined
    port: number
    user: string | undefined
    password: string | undefined
    from: string
    secure: boolean
  }
  alertEmailTo: string | undefined
  digestIntervalMs: number
  watchdogIntervalMs: number
}

function readProvider(value: string | undefined): ProviderName {
  if (value === 'openai' || value === 'openrouter') return value
  return 'anthropic'
}

if (!process.env.JWT_SECRET) {
  throw new Error('JWT_SECRET manquant dans server/.env')
}

export const config: Config = {
  port: Number(process.env.PORT) || 8787,
  isProd: process.env.NODE_ENV === 'production',
  jwtSecret: process.env.JWT_SECRET,
  llmProvider: readProvider(process.env.LLM_PROVIDER),
  llmModel: process.env.LLM_MODEL || 'claude-sonnet-4-5',
  anthropicApiKey: process.env.ANTHROPIC_API_KEY,
  openaiApiKey: process.env.OPENAI_API_KEY,
  openrouterApiKey: process.env.OPENROUTER_API_KEY,
  engineUrl: process.env.ENGINE_URL || 'http://127.0.0.1:8000',
  smtp: {
    host: process.env.SMTP_HOST,
    port: Number(process.env.SMTP_PORT) || 587,
    user: process.env.SMTP_USER,
    password: process.env.SMTP_PASSWORD,
    from: process.env.SMTP_FROM || 'IchiVol <no-reply@ichivol.local>',
    secure: process.env.SMTP_SECURE === 'true',
  },
  alertEmailTo: process.env.ALERT_EMAIL_TO,
  // Digest quotidien par défaut ; watchdog santé toutes les 5 min.
  digestIntervalMs: Number(process.env.DIGEST_INTERVAL_MS) || 24 * 60 * 60 * 1000,
  watchdogIntervalMs: Number(process.env.WATCHDOG_INTERVAL_MS) || 5 * 60 * 1000,
}
