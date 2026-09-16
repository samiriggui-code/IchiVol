import cookieParser from 'cookie-parser'
import cors from 'cors'
import express from 'express'
import { handleConfirmAgentAction } from './agent/actionsRoute.js'
import { handleAgentChat } from './agent/route.js'
import { handleGetAgentThread, handleListAgentThreads } from './agent/threadsRoute.js'
import { attachSession, requireAuth } from './auth/middleware.js'
import { handleLogin, handleLogout, handleMe } from './auth/route.js'
import { config } from './config.js'
import {
  handleCreateDecision,
  handleDeleteDecision,
  handleListDecisions,
  handlePatchDecision,
  handlePostDecisionStatus,
} from './decisions/route.js'
import { proxyToEngine } from './engine/proxy.js'
import {
  handleListNotifications,
  handleReadAllNotifications,
  handleReadNotification,
} from './notifications/route.js'
import { startJournalWatchJob } from './notifications/watch.js'
import { handleHealth } from './routes/health.js'
import { handleGetSettings, handleLlmTest, handlePatchSettings } from './settings/route.js'
import {
  handleDeleteWatchlistItem,
  handleListWatchlist,
} from './watchlist/route.js'

const app = express()
app.use(cors({ origin: true, credentials: true }))
app.use(express.json({ limit: '256kb' }))
app.use(cookieParser())
app.use(attachSession)

app.get('/api/health', handleHealth)

app.post('/api/auth/login', handleLogin)
app.post('/api/auth/logout', handleLogout)
app.get('/api/auth/me', handleMe)

app.get('/api/settings', requireAuth, handleGetSettings)
app.patch('/api/settings', requireAuth, handlePatchSettings)
app.post('/api/settings/llm-test', requireAuth, handleLlmTest)

app.get('/api/decisions', requireAuth, handleListDecisions)
app.post('/api/decisions', requireAuth, handleCreateDecision)
app.patch('/api/decisions/:id', requireAuth, handlePatchDecision)
app.post('/api/decisions/:id/status', requireAuth, handlePostDecisionStatus)
app.delete('/api/decisions/:id', requireAuth, handleDeleteDecision)

app.get('/api/watchlist', requireAuth, handleListWatchlist)
app.delete('/api/watchlist/:symbol', requireAuth, handleDeleteWatchlistItem)

app.get('/api/notifications', requireAuth, handleListNotifications)
app.post('/api/notifications/read-all', requireAuth, handleReadAllNotifications)
app.post('/api/notifications/:id/read', requireAuth, handleReadNotification)

app.post('/api/agent/chat', requireAuth, handleAgentChat)
app.post('/api/agent/actions/confirm', requireAuth, handleConfirmAgentAction)
app.get('/api/agent/threads', requireAuth, handleListAgentThreads)
app.get('/api/agent/threads/:id', requireAuth, handleGetAgentThread)

app.get('/api/engine/*', requireAuth, proxyToEngine)
app.post('/api/engine/*', requireAuth, proxyToEngine)

app.listen(config.port, () => {
  console.log(`IchiVol agent server on http://localhost:${config.port} (provider: ${config.llmProvider})`)
  startJournalWatchJob()
})
