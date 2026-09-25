import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ContextPage } from './pages/ContextPage'
import { DashboardShell } from './layouts/DashboardShell'
import { initTheme } from './lib/theme'
import { ActivityPage } from './pages/ActivityPage'
import { AgentsPage } from './pages/AgentsPage'
import { AgentPage } from './pages/AgentPage'
import { BacktestsPage } from './pages/BacktestsPage'
import { DecisionsPage } from './pages/DecisionsPage'
import { JournalPage } from './pages/JournalPage'
import { LandingPage } from './pages/LandingPage'
import { LoginPage } from './pages/LoginPage'
import { MarketPage } from './pages/MarketPage'
import { OverviewPage } from './pages/OverviewPage'
import { PortfolioPage } from './pages/PortfolioPage'
import { RequireAuth } from './pages/RequireAuth'
import { SettingsPage } from './pages/SettingsPage'
import './theme/camap-tokens.css'
import './theme/keenicons.css'
import './theme/camap-landing.css'
import './index.css'
// Workspace refinements follow the base cockpit rules; no !important overrides.
import './theme/iv-workspace.css'
import './theme/maquette-theme.css'

initTheme()

export function Root() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireAuth />}>
          <Route path="/app" element={<DashboardShell />}>
            <Route index element={<Navigate to="desk" replace />} />
            {/* T14a canonical routes */}
            <Route path="desk" element={<OverviewPage />} />
            <Route path="market" element={<MarketPage />} />
            <Route path="opportunites" element={<DecisionsPage />} />
            <Route path="portefeuille" element={<PortfolioPage />} />
            <Route path="context" element={<ContextPage />} />
            <Route path="journal" element={<JournalPage />} />
            <Route path="operations" element={<ActivityPage />} />
            <Route path="strategy-lab" element={<BacktestsPage />} />
            <Route path="agent" element={<AgentPage />} />
            <Route path="agents" element={<AgentsPage />} />
            <Route path="settings" element={<SettingsPage />} />
            {/* Legacy redirects — no page deletion without redirect (T14a) */}
            <Route path="overview" element={<Navigate to="/app/desk" replace />} />
            <Route path="decisions" element={<Navigate to="/app/opportunites" replace />} />
            <Route path="activite" element={<Navigate to="/app/operations" replace />} />
            <Route path="synthese" element={<Navigate to="/app/portefeuille" replace />} />
            <Route
              path="paper"
              element={<Navigate to="/app/portefeuille?tab=positions" replace />}
            />
            <Route
              path="paper/tech"
              element={<Navigate to="/app/portefeuille?tab=positions" replace />}
            />
            <Route
              path="watchlist"
              element={<Navigate to="/app/market?filter=pinned" replace />}
            />
            <Route path="backtests" element={<Navigate to="/app/strategy-lab" replace />} />
            <Route path="*" element={<Navigate to="desk" replace />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
