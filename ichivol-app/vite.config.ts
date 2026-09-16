import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// data-api.binance.vision is reachable from more regions than api.binance.com
const BINANCE = 'https://data-api.binance.vision'
const BYBIT = 'https://api.bybit.com'
const OKX = 'https://www.okx.com'
const COINGECKO = 'https://api.coingecko.com'
const FEAR_GREED = 'https://api.alternative.me'
const AGENT_SERVER = 'http://localhost:8787'

const marketProxy = (target: string, prefix: string) => ({
  target,
  changeOrigin: true,
  rewrite: (path: string) => path.replace(new RegExp(`^${prefix}`), ''),
  configure: (proxy: { on: (event: string, fn: (...args: unknown[]) => void) => void }) => {
    proxy.on('proxyReq', (...args: unknown[]) => {
      const proxyReq = args[0] as { setHeader: (k: string, v: string) => void }
      proxyReq.setHeader('Accept', 'application/json')
      proxyReq.setHeader('User-Agent', 'IchiVol/1.0 (local-dev)')
    })
    proxy.on('error', (...args: unknown[]) => {
      const err = args[0] as Error
      const res = args[2] as { writeHead?: (code: number, h: Record<string, string>) => void; end?: (b: string) => void } | undefined
      console.warn(`[proxy ${prefix}]`, err.message)
      if (res && !('headersSent' in res && (res as { headersSent?: boolean }).headersSent) && res.writeHead && res.end) {
        res.writeHead(502, { 'Content-Type': 'application/json' })
        res.end(JSON.stringify({ error: 'upstream_unavailable', detail: err.message }))
      }
    })
  },
})

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    allowedHosts: true,
    proxy: {
      '/binance': marketProxy(BINANCE, '/binance'),
      '/bybit': marketProxy(BYBIT, '/bybit'),
      '/okx': marketProxy(OKX, '/okx'),
      '/coingecko': marketProxy(COINGECKO, '/coingecko'),
      '/feargreed': marketProxy(FEAR_GREED, '/feargreed'),
      '/api': {
        target: AGENT_SERVER,
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 4173,
    host: true,
    allowedHosts: true,
    proxy: {
      '/binance': marketProxy(BINANCE, '/binance'),
      '/bybit': marketProxy(BYBIT, '/bybit'),
      '/okx': marketProxy(OKX, '/okx'),
      '/coingecko': marketProxy(COINGECKO, '/coingecko'),
      '/feargreed': marketProxy(FEAR_GREED, '/feargreed'),
      '/api': {
        target: AGENT_SERVER,
        changeOrigin: true,
      },
    },
  },
})
