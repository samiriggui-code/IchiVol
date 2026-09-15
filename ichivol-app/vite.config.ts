import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// data-api.binance.vision is reachable from more regions than api.binance.com
const BINANCE = 'https://data-api.binance.vision'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    allowedHosts: true,
    proxy: {
      '/binance': {
        target: BINANCE,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/binance/, ''),
      },
    },
  },
  preview: {
    port: 4173,
    host: true,
    allowedHosts: true,
    proxy: {
      '/binance': {
        target: BINANCE,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/binance/, ''),
      },
    },
  },
})
