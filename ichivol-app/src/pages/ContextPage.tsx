import { ContextPanel } from '../components/ContextPanel'

/**
 * Page Contexte = détail approfondi du teaser Overview.
 * Rôle produit : régime / sentiment macro — pas un 2ᵉ screener IchiVol.
 */
export function ContextPage() {
  return (
    <div className="context-page">
      <header className="page-head">
        <h1>Contexte</h1>
        <p className="muted">
          Zoom macro : climat, news, calendrier, corrélations watchlist.
          Complète l’Overview — n’écrase pas Ichimoku × RVOL.
        </p>
      </header>
      <ContextPanel variant="full" />
    </div>
  )
}
