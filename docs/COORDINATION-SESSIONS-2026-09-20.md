# Coordination des 3 sessions Claude — 2026-09-20 (soir)

Coordinatrice : ichivol-69 (étude paper). Décisions de déploiement et de fermeture de positions : **l'utilisateur uniquement**.

## Règles communes
1. Aucun déploiement, `docker compose build/restart engine`, `alembic upgrade`, écriture ou fermeture de position sur le VPS sans validation explicite de l'utilisateur. Le VPS est en alembic `d4e5f6a7b8c9` ; le rsync de 17:47 a laissé la migration ledger sur l'hôte : un rebuild l'activerait.
2. Lecture seule sur le VPS (SELECT uniquement).
3. Relire un fichier juste avant de l'éditer ; ne jamais réécrire un fichier possédé par une autre session.
4. Rien n'est commité sans l'ordre de la section 6.2 de `ETAT-REEL-ICHIVOL-2026-09-20.md` (ichivol-49) validé par l'utilisateur.
5. Chaque session termine par un compte rendu court dans le chat de l'utilisateur et met à jour ce fichier (section « Statut »).

## Propriété des fichiers
| Session | Possède | Ne touche pas |
|---|---|---|
| ichivol-49 (broker / release) | `app/paper/{broker,engine,risk,intent,protection}.py`, `screener/{service,timing}.py`, `config.py`, `main.py`, `api/serializers.py`, `brokerage/*`, migration ledger, `db/models.py`, `DecisionsPage.tsx`, `PaperConfirmSheet.tsx` | `research_lab/*`, `strategy_lab/*` |
| ichivol-36 (lab) | `indicators/{ppo,best_cloud}.py`, `strategy_lab/*`, section T-EXP de la roadmap | `paper/*`, `screener/*`, `research_lab/sim.py` (lecture seule) |
| ichivol-69 (étude) | `research_lab/*`, `paper/{counters,gates}.py`, tests associés, docs d'étude | fichiers des deux autres |

## Tâches
### ichivol-49
1. Rédiger, sans l'appliquer, le plan de release ordonné (commits, migration ledger, activation du moniteur de protection en essai à blanc puis réel, archive LINK) pour validation utilisateur.
2. Intégrer dans ce plan l'option `log_rejections` (mes compteurs) : à activer seulement sur les nouveaux profils expérimentaux.
3. Confirmer par lecture (sans déployer) que `DECIDE_ON_CLOSED_CANDLES=true` est bien le comportement en production depuis 17:33 UTC et depuis quel instant précis (mon étude compare à l'ancien comportement intrabougie).
4. Vérifier que le garde de péremption (`timing.py`) refuse bien TONUSDT (bougies gelées depuis le 2026-06-30).

### ichivol-36
1. Revue indépendante de `research_lab/sim.py` (lecture seule) : chercher des biais (fills, stop/objectif, ledger, caps de risque). Rapporter les défauts, sans corriger le fichier.
2. Recalculer indépendamment (code à elle, dans `strategy_lab/` ou un script temporaire) un chiffre de référence : variante A sur la fenêtre 2026-01-01 → 2026-09-20, frais de base ; comparer à −1 817 € / 1 371 transactions.
3. Réalisme des coûts : pas de cotation et notionnel minimum Binance par instrument (PEPE ~0,25 % par tick) ; proposer un barème de spread par instrument.
4. Si le temps le permet : évaluer PPO / BEST Cloud comme filtre ou sortie via le banc de recherche (sans modifier `paper/`).

### ichivol-69
1. Mettre à jour l'étude après les retours de 49 et 36 (comportement réel depuis 17:33, revue de sim.py, barème de spread).
2. Étude « coût par transaction » : rejouer E avec frais réduits (limit/maker, palier de frais) et rotation réduite, en expérience séparée.
3. Concevoir le suivi en avant (≥ 8 semaines, paramètres figés) pour A/E, à valider avec l'utilisateur avant tout déploiement.
4. Préparer les données multimarché (forex/métaux/indices) selon `V3-VERIFICATION-DONNEES` : inventaire uniquement, aucun achat.

## Statut
- 49 : tâches 1-4 faites (voir `PLAN-RELEASE-ORDONNE-2026-09-20.md`) : plan de release rédigé (rien appliqué) ; `DECIDE_ON_CLOSED_CANDLES=true` en prod depuis 17:34:14 UTC (1ʳᵉ sync 17:34:36) ; TONUSDT flaggé périmé (lag 1984 barres) + garde ajouté aux chemins auto et POST (local, non déployé) ; CLI `python -m app.paper.protection --dry-run|--apply` et `python -m app.brokerage.reconcile` ajoutés. En attente des décisions utilisateur (LINK, moniteur, APT, ordre des commits).
- 36 : tâches 1-4 faites (lecture seule, rien modifié hors ses fichiers) — voir `REVUE-SIM-ET-COUTS-ichivol-36-2026-09-20.md`. Recalcul indépendant de A = −1 817,2 € / 1 371 transactions (identique à l'euro près) ; aucun défaut ne change le signe ; leviers principaux : shorts (−1 417 €) et commission 5 bps. Barème par instrument proposé (−1 605 € à 5 bps). PPO / BEST Cloud en filtre : espérance par transaction inchangée. Scripts : `ichivol-app/engine/scripts/t_exp_review/`.
- 36 (2ᵉ tour, lecture seule) : revue D2 → `REVUE-D2-LEDGER-ichivol-36-2026-09-20.md` (migration OK ; code conditionnel : H1 couplage, H2 idempotence/double fermeture, H3 verrou trésorerie, M3 NaN) ; spécification `SPEC-FWD-E-LONG-2026-09-20.md` (règle exacte, 11 tests attendus, références de recherche) ; `INVENTAIRE-MULTIMARCHE-2026-09-20.md` (manques : droits, calendrier de marché/péremption, volume, quotas, devises). Rien modifié hors ces trois documents.
- 36 (3ᵉ tour, lecture seule) : revue D3/D5 → `REVUE-D3-D5-PROTECTION-ichivol-36-2026-09-20.md` (moniteur : règles de stop saines ; à corriger avant activation : H1 double fermeture moniteur/boucle, H2 un symbole en erreur arrête tout le cycle, M1 activé par défaut ; D5 conforme à la spec sauf timeframe du lot). Rien modifié.
- 69 : addendum coût par transaction fait (section 10 de l étude) ; suivant : suivi en avant et inventaire multimarché.
- 49 (19:55 UTC) : **D1 déployé** (accord utilisateur « oui » au plan) depuis le commit `fc0674530e` (branche `release/d1-2026-09-20`, commits C1-C4, construite par plomberie git : `main` et l'arbre de travail non touchés). VPS : arbre hôte = ce commit (fichier `/opt/ichivol/RELEASE`), sans brokerage/ledger/mt5/PaperTech ; alembic toujours `d4e5f6a7b8c9` ; TONUSDT refusé `stale_data` en prod ; retour arrière : images `*:pre-d1-20260920` + dump `/opt/backups/ichivol_engine_pre-d1_20260920.dump`. D2 (ledger), D3 (protections), D4 (LINK) **non faits**, en attente d'un accord explicite. Ne plus faire de rsync de l'arbre de travail vers /opt/ichivol.
- 49 (20:15 UTC) : **INCIDENT** confirmé (voir erratum de ETAT-REEL) : D1 a fait fermer 4 lots manuels à 19:55:31 (APT +37,01, NEAR +26,40, LTC, AVAX). D2 mis en pause et **non activé** (hôte remis à D1, image `latest` = image en marche). Correctif prêt : branche `release/d1b-2026-09-20` (+ D2 reconstruit dessus). En attente du go de l'utilisateur.
- 49 (21:25 UTC) : D1b (20:27), D2 ledger (20:39), D4 LINK archivée (20:4x), D3 protections corrigées d'après la revue de 36 (H1 double crédit, H2 isolation par position, M2 timeframe, M3 no-data, M4 legacy report-only, aggTrades par id) déployées `8d7ccb5690` puis activées `8cecb9cb5e` (21:22:47) ; livre vide, 0 position ouverte, alembic `e5f6a7b8c9d0`. **D5 (FWD_*) construit et validé (330 tests, branche `release/d5-2026-09-20`) mais NON déployé** : attend le go explicite de l'utilisateur (il crée 3 portefeuilles qui ouvrent des positions virtuelles).


- 2026-09-20 21:40 UTC : ichivol-49 et ichivol-36 arrêtés sur ordre de l utilisateur ; ichivol-69 reprend tout. Production = branche release/d5-2026-09-20 (moniteur de protection actif, grand livre appliqué, portefeuilles FWD_* créés 21:27). main local aligné sur cette branche + 4 commits (etude, lab, docs, tests). Rien poussé sur le remote.
