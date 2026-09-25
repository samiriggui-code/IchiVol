# ACTIONS MÉTIER — écritures `lib/*.ts` (main vs branche ui-port)

Audit des fonctions client qui font **POST / PATCH / PUT / DELETE**.  
Comparaison `origin/main` ↔ `cursor/ui-port-pages-a2fe` après rebranchement paper + journal + settings + lab.

Légende : **OK** = accessible dans l’UI portée · **REWIRED** = reconnecté sur cette branche · **N/A main** = jamais appelé côté UI sur main · **SUPERSEDED** = remplacé par un autre flux maquette.

| Action (`lib`) | Sur main | Sur branche (où) | Statut |
|----------------|----------|------------------|--------|
| `paper.openPaperPosition` | Opportunités (`useOpportunitesController`) | Opportunités · dialog → `PaperConfirmSheet` | **REWIRED** |
| `paper.previewPaperBuy` | `PaperConfirmSheet` | `PaperConfirmSheet` (depuis Opportunités) | **OK** |
| `paper.proposePaperTrade` | Opportunités / AgentPanel | Opportunités (avant confirm) | **REWIRED** |
| `paper.closePaperPosition` | PaperPage / SynthesePage | Portefeuille · bouton Fermer → `PaperCloseConfirmSheet` | **REWIRED** |
| `userDecisions.confirmUserDecision` | Opportunités + Journal | Opportunités (après open paper) | **OK** |
| `userDecisions.patchUserDecisionStatus` | Journal | Journal · Archiver / Restaurer | **REWIRED** |
| `userDecisions.patchUserDecisionNote` | Journal | Journal · Note personnelle (décision sélectionnée) | **REWIRED** |
| `userDecisions.deleteUserDecision` | Journal | Journal · Supprimer | **REWIRED** |
| `settings.patchSettings` | Paramètres (controller) | Paramètres · RVOL / LLM / prefs alertes | **REWIRED** |
| `pushAlerts.enablePushAlerts` | Paramètres · Alertes | Paramètres · Alertes | **REWIRED** |
| `pushAlerts.disablePushAlerts` | Paramètres · Alertes | Paramètres · Alertes | **REWIRED** |
| `settings.testLlm` | via `llmStatus` | `lib/llmStatus.tsx` (header / statut) | **OK** |
| `labResearch.buildAuditReport` | `LabResearchPanel` | Strategy Lab · Examiner / Configurer | **REWIRED** |
| `labResearch.proposeExperimentPlan` | `LabResearchPanel` | Strategy Lab · Configurer une expérience | **REWIRED** |
| `labResearch.runMonteCarlo` | `LabResearchPanel` | Strategy Lab · Examiner (onglet Régimes) | **REWIRED** |
| `backtest.getWalkForwardOpt` | Lab controller | Strategy Lab · Examiner (onglet Walk-forward) | **REWIRED** |
| `agent.askAgentStream` | AgentPanel | Copilot (`AgentPage`) | **OK** |
| `agent.confirmAgentAction` | AgentPanel / Market | Marché · Ajouter à la watchlist | **OK** |
| `agent.askAgent` | — | — | **N/A main** |
| `auth.login` / `auth.logout` | Login / shell | Login / shell | **OK** |
| `notifications.markNotificationRead` | NotificationBell | NotificationBell | **OK** |
| `notifications.markAllNotificationsRead` | NotificationBell | NotificationBell | **OK** |
| `riskLock.armKillSwitch` / `disarm` / `unlockDailyLoss` | KillSwitchControls | KillSwitchControls (header) | **OK** |
| `chartObjects.postUserTradeSetup` | Market · MarkTradeSheet | — | **SUPERSEDED** par « Préparer le trade → » → fiche Opportunités paper (`?open=1`). Marquage chart ENTRY/STOP/TP hors surface maquette. |
| `chartObjects.postUserTradePoint` | — | — | **N/A main** |
| `chartObjects.deleteUserChartObject` | — | — | **N/A main** |
| `backtestOverlay.postBacktestOverlay` | Market · bottom panel | — | **SUPERSEDED** (hors maquette Marché). Overlay backtest non exposé sur le port littéral. |
| `watchlist.removeWatchlistSymbol` | — | — | **N/A main** (ajout via `confirmAgentAction` seulement) |

## Entrées UI paper (flux validé)

1. **Marché** → `Préparer le trade →` → `/app/opportunites?symbol=…&open=1` → dialog maquette.
2. **Opportunités** → dialog → `Ouvrir une position paper →` → `proposePaperTrade` → `PaperConfirmSheet` (`previewPaperBuy`) → `openPaperPosition` (+ `confirmUserDecision`).
3. **Portefeuille** → ligne ouverte → `Fermer` → `PaperCloseConfirmSheet` → `closePaperPosition`.

## Composants paper conservés

- `PaperConfirmSheet` (ouvert)
- `PaperCloseConfirmSheet` (fermeture)

`PaperTradeSheet` et les 15 autres orphelins listés par la relecture Claude ont été **supprimés** (voir RETIRES.md des pages concernées).
