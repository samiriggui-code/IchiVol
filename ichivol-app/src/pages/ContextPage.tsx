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
          Zoom macro : capitalisation, dominance, Fear &amp; Greed, top marchés, corrélations.
          Complète l’Overview — n’écrase pas la méthode Ichimoku × volume.
        </p>
      </header>
      <ContextPanel variant="full" />
    </div>
  )
}
