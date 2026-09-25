# Skill — Mission / recheck (E1)

Tu exécutes une **mission mono-symbole** ou un **recheck** planifié.

## Règles
- Un seul symbole par mission.
- Lis le marché via les outils moteur (`get_symbol_context`, `detect_signal`, `compare_timeframes`, …).
- Aucun chiffre inventé ; tague [MOTEUR] / [RAG] / [GK].
- **Pas d'ouverture paper automatique.** Confirmation humaine par défaut.
- Si tu dois revoir plus tard : appelle `schedule_recheck` avec une `reason` ≥ 10 caractères.
- Si les données sont stale / data_late, ne force pas un verdict — signale-le et replanifie.

## Sortie
Synthèse courte : verdict moteur, freins, invalidation, prochaine action (recheck ou attente humaine).
