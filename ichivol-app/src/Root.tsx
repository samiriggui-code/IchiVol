import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ContextPage } from './pages/ContextPage'
import { DashboardShell } from './layouts/DashboardShell'
import { initTheme } from './lib/theme'
import { AgentPage } from './pages/AgentPage'
import { BacktestsPage } from './pages/BacktestsPage'
import { DecisionsPage } from './pages/DecisionsPage'
import { JournalPage } from './pages/JournalPage'
import { LandingPage } from './pages/LandingPage'
import { LoginPage } from './pages/LoginPage'
import { MarketPage } from './pages/MarketPage'
import { OverviewPage } from './pages/OverviewPage'
import { PaperPage } from './pages/PaperPage'
import { RequireAuth } from './pages/RequireAuth'
import { SettingsPage } from './pages/SettingsPage'
import { SynthesePage } from './pages/SynthesePage'
import { WatchlistPage } from './pages/WatchlistPage'
import './theme/camap-tokens.css'
import './theme/keenicons.css'
import './theme/camap-landing.css'
import './index.css'

initTheme()

export function Root() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireAuth />}>
          <Route path="/app" element={<DashboardShell />}>
            <Route index element={<Navigate to="overview" replace />} />
            <Route path="overview" element={<OverviewPage />} />
            <Route path="market" element={<MarketPage />} />
            <Route path="context" element={<ContextPage />} />
            <Route path="decisions" element={<DecisionsPage />} />
            <Route path="journal" element={<JournalPage />} />
            <Route path="watchlist" element={<WatchlistPage />} />
            <Route path="synthese" element={<SynthesePage />} />
            <Route path="paper" element={<PaperPage />} />
            <Route path="paper/tech" element={<Navigate to="/app/paper" replace />} />
            <Route path="backtests" element={<BacktestsPage />} />
            <Route path="agent" element={<AgentPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
