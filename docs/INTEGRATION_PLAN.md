# Plan d'intégration — GrokDesk (donneur) → Ichimoku × RVOL (socle)

Statut au moment de la rédaction : **aucune modification n'a été apportée à `ichivol-app/`.** Ce document précède toute implémentation, conformément à la règle de la mission ("AUCUNE refonte globale avant d'avoir produit la matrice d'intégration").

Documents associés :
- `GROKDESK_ANALYSIS.md` — audit technique complet de GrokDesk
- `GROKDESK_REUSABLE_COMPONENTS.md` — matrice composant par composant (KEEP/ADAPT/REWRITE/REJECT)
- `TRADING_ARCHITECTURE_V2.md` — architecture cible mappée sur la stack réelle

## Règle directrice

Le projet existant (`ichivol-app/`) reste le socle. GrokDesk est un laboratoire dont on retient surtout des **patterns architecturaux** (bus pub/sub, hiérarchie de véto Risk, calibration bornée avec journal de révisions) — pas du code métier, le domaine (memecoins pump.fun, pas d'orderbook de probabilité) étant trop éloigné du nôtre (Ichimoku/RVOL sur crypto spot, extension Polymarket en lecture seule).

## Matrice de synthèse (résumé — détail complet dans GROKDESK_REUSABLE_COMPONENTS.md)

| Composant | Source | Décision |
|---|---|---|
| Ichimoku engine | notre projet | KEEP |
| RVOL | notre projet | KEEP |
| Screener multi-source | notre projet | KEEP |
| Copilot LLM + RAG | notre projet | KEEP (hors périmètre StrategyAgent) |
| DB (Prisma) | notre projet | KEEP/EXTEND |
| Bus pub/sub | GrokDesk | ADAPT |
| Agent score/budget glissant | GrokDesk | ADAPT |
| ScoringMatrix bornée + journal | GrokDesk | ADAPT (avec gate humain ajouté) |
| Ledger wallet/vault | GrokDesk | ADAPT |
| PaperBroker | GrokDesk | ADAPT (résultat doit dériver du marché, pas d'un tirage caché) |
| StrategyAgent interface | — | REWRITE (aucun équivalent GrokDesk) |
| Consensus Engine | GrokDesk (inspiration faible) | REWRITE |
| Risk Engine avancé (Kelly plafonné, exposition, drawdown) | GrokDesk (véto seul conservé) | REWRITE (hybride) |
| Edge Engine (P_model vs P_market) | — | REWRITE (aucun équivalent) |
| Backtest / walk-forward | — | REWRITE (aucun équivalent) |
| Adapter Polymarket | — | REWRITE (aucun équivalent) |
| GrokDesk UI (terminal.html) | GrokDesk | REJECT (inspiration visuelle seulement) |
| GrokDesk market data (pump.fun/bonding curve) | GrokDesk | REJECT |
| Demo PnL GrokDesk | GrokDesk | REJECT (données synthétiques scriptées) |
| Firing/"rewrite" d'agent | GrokDesk | REJECT (cosmétique) |

## Phasage (repris de la mission, §9, concrétisé)

### Phase 0 — Fondations (préalable à tout le reste)
- Étendre le schéma Prisma (voir `TRADING_ARCHITECTURE_V2.md` §4) : `MarketSnapshot`, `StrategySignal`, `AgentPrediction`, `ConsensusDecision`, `EdgeCalculation`, `RiskCalculation`, `Trade`, `StrategyPerformance`, `StrategyCalibration`, `Backtest`.
- Définir l'interface `StrategyAgent` (contrat partagé Python/TS via schéma JSON).
- Porter le `Bus` (pattern GrokDesk) en version typée, côté `engine/` (Python) ou `server/` selon où vit l'orchestration finale — à trancher à l'implémentation.

### Phase 1 — Historical backtest
- Construire `engine/app/backtest/` : rejoue les `StrategyAgent` sur des données historiques réelles (pas de génération synthétique façon `PumpFun`).
- Premiers agents à backtester : `ICHIMOKU_AGENT`, `RVOL_AGENT` (les deux seuls déjà partiellement implémentés côté indicateurs).
- Sortie persistée dans `Backtest` (pas seulement imprimée comme le fait GrokDesk).

### Phase 2 — Walk-forward testing
- Réentraînement/recalibration glissante de `ScoringMatrix`-like par stratégie, avec statut `"recommended"` uniquement (jamais auto-déployé).

### Phase 3 — Paper trading temps réel
- `PaperBroker` (adapté du pattern GrokDesk, corrigé pour dériver le résultat du prix réel).
- Toute décision passe par `Consensus → Edge → Risk → Execution` et est journalisée intégralement (voir schéma DB).

### Phase 4 — Shadow mode
- Le pipeline complet tourne en continu sur données live, génère des décisions, **mais n'exécute rien**, ni paper ni réel — sert à valider la stabilité et la cohérence avant d'activer l'exécution paper.

### Phase 5 — Live (exposition extrêmement limitée)
- Hors périmètre de ce document. `LiveAdapter` reste un stub désactivé tant que les phases 1 à 4 n'ont pas produit un historique de décisions validées.

## Volet Polymarket (mission §10)

- `PolymarketAdapter` en lecture seule uniquement : markets, prices, probabilities, orderbook, spread, liquidity, resolution rules.
- Alimente le pipeline exactement comme une source de marché supplémentaire (`MarketData → Screener → Strategies → Consensus → Edge → Risk → PAPER EXECUTION`), sans écriture d'ordres réels.
- Aucun équivalent dans GrokDesk (aucune notion de marché de probabilité) — conception entièrement nouvelle.

## Garde-fous explicites à respecter à l'implémentation

1. Aucun agent de stratégie ne décide seul d'une taille de position — seul le Risk Engine sizes.
2. Aucune modification automatique des règles de trading en production par un LLM — seulement `OBSERVATION → RECOMMENDATION`, la `VALIDATION` et le `DEPLOYMENT` restent des actes humains (contrairement à `ScoringMatrix.tighten()` dans GrokDesk qui s'applique sans validation).
3. Paper trading obligatoire avant tout live ; live reste désactivé par défaut.
4. Ne jamais présenter le scoreboard de démonstration GrokDesk (ni aucun chiffre de backtest interne) comme une performance financière réelle.

## Prochaine étape proposée

Ce plan couvre l'audit et la conception ; aucune ligne de `ichivol-app/` n'a été touchée. La suite logique — dès validation de ce plan par vous — serait de commencer par la Phase 0 (schéma Prisma + interface `StrategyAgent`), en commençant par les deux agents déjà outillés (`ICHIMOKU_AGENT`, `RVOL_AGENT`) avant d'attaquer Momentum/Volatility/Structure/Bayesian. À confirmer avant toute implémentation.
