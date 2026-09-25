import react from '@vitejs/plugin-react'
import { defineConfig, type ProxyOptions } from 'vite'

// data-api.binance.vision is reachable from more regions than api.binance.com
const BINANCE = 'https://data-api.binance.vision'
const BYBIT = 'https://api.bybit.com'
const OKX = 'https://www.okx.com'
const COINGECKO = 'https://api.coingecko.com'
const FEAR_GREED = 'https://api.alternative.me'
const AGENT_SERVER = process.env.AGENT_SERVER || 'http://localhost:8787'

const marketProxy = (target: string, prefix: string): ProxyOptions => ({
  target,
  changeOrigin: true,
  rewrite: (path) => path.replace(new RegExp(`^${prefix}`), ''),
  configure: (proxy) => {
    proxy.on('proxyReq', (proxyReq) => {
      proxyReq.setHeader('Accept', 'application/json')
      proxyReq.setHeader('User-Agent', 'IchiVol/1.0 (local-dev)')
    })
    proxy.on('error', (err, _req, res) => {
      console.warn(`[proxy ${prefix}]`, err.message)
      const socket = res as { writeHead?: (code: number, h: Record<string, string>) => void; end?: (b: string) => void; headersSent?: boolean }
      if (socket && !socket.headersSent && socket.writeHead && socket.end) {
        socket.writeHead(502, { 'Content-Type': 'application/json' })
        socket.end(JSON.stringify({ error: 'upstream_unavailable', detail: err.message }))
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
