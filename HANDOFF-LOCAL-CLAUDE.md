# HANDOFF — Reprise du chantier IchiVol V3 en local

**LIS CE FICHIER EN PREMIER, avant tout autre fichier du repo.**

## Contexte

Tu (Claude, en local sur le PC de l'utilisateur) reprends le rôle de **superviseur** d'un chantier mené avec **Cursor** sur ce repo. Le principe depuis le début : **Cursor code, tu vérifies par toi-même (code + tests avec une vraie base Postgres), tu valides ou tu corriges, puis tu donnes le prochain job.** Jamais l'inverse — ne fais pas confiance à ce que Cursor écrit dans son propre compte-rendu sans le vérifier dans le code et les tests.

## Le canal de communication : `docs/HANDOFF-CURSOR-V3.md`

Chaque PR de Cursor y ajoute une entrée **en haut**, jamais effacée. Toi tu le lis, tu vérifies le diff réel de la PR associée, et tu répliques ta revue soit dans ce fichier, soit dans un message que l'utilisateur colle à Cursor. Lis-le en entier avant de commencer.

## La feuille de route

Un document Claude Docs existe avec toute la feuille de route (audit initial, tranches T1 à T8 détaillées, journal complet de chaque revue) : **https://claude.ai/code/artifact/36b8918e-047e-4dd9-a33c-7fa6c9fa49c2**. Si tu as accès aux outils Docs, ouvre-le et continue à l'alimenter au même endroit — ne recrée pas un nouveau doc. Sinon, base-toi sur ce fichier et sur `docs/HANDOFF-CURSOR-V3.md`.

## Méthode de travail (stricte)

1. Cursor code sur une branche, PR en **draft**, écrit une entrée dans le handoff, s'arrête.
2. Tu fetches la branche, tu lis le **vrai diff**, tu vérifies la logique toi-même (pas seulement le résumé de Cursor).
3. Tu relances **toute la suite de tests avec une vraie base Postgres** (voir ci-dessous) — c'est comme ça qu'on a trouvé plusieurs bugs invisibles en CI sans base.
4. Tu donnes un verdict : **validé** (Cursor merge) ou **à corriger** (liste précise).
5. Cursor **attend toujours ta revue explicite avant de merger et avant de démarrer le job suivant**, même si ses propres tests sont verts.

**Incident à connaître** : à un moment, Cursor a mergé 18 PR tout seul sans attendre de revue (dont une couche "Event Intelligence" en 7 phases, demandée séparément par l'utilisateur). Audité a posteriori : le contenu était sain (rien ne touchait le moteur de décision, tout restait en observation/proposition), mais **le processus a été violé**. Un rappel ferme a été envoyé. Reste vigilant sur ce point.

## Setup de la base Postgres pour les tests (à refaire à chaque session si l'environnement est réinitialisé)

```bash
apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq postgresql
service postgresql start
su postgres -c "psql -qc \"ALTER USER postgres PASSWORD 'root';\" && createdb ichivol_engine_dev"
cd ichivol-app/engine && alembic upgrade head
python -m pytest tests -q -p no:cacheprovider --tb=short
```

L'URL par défaut (`app/config.py`) est `postgresql+psycopg://postgres:root@127.0.0.1:5432/ichivol_engine_dev`. **Référence actuelle avec cette base : 0 échec, 1 skip (réseau Binance).** Tout échec au-delà de ça est une régression à traiter avant tout merge.

Pour le serveur Node (`ichivol-app/server`), pense à `npm ci`, `npx prisma generate`, et `npx prisma migrate deploy` avant de lancer ses tests (`npm test`).

## État d'avancement (au moment du transfert)

**Terminé et validé** : T1 (registre d'indicateurs, un seul chemin de calcul, plus de repaint de trendlines, `routes.py` découpé), T2 (ChartObject, outils de dessin pour Claude avec garde-fou anti-hallucination, marquage de trade par l'utilisateur), T3 (DSL de stratégie étendu, registre de conditions), T4a (backtest visuel), T0-BROKER (fidélité du broker virtuel, formule short corrigée), T0-CI (tests paper réécrits), T0-METRICS et T0-METRICS-2 (statistiques nettes de frais partout), T0-CALC (calculateur de scénarios objectif/stop/crash).

**Fait par Cursor seul, audité a posteriori et validé** : Event Intelligence (phases 1-7, observation-only), T4b/T4c/T4d (filtres, WHY entered/exited, régime), T5a/T5b (poids de confluence, observation-only), T6 (audit de trade), T7 (Monte Carlo), T3d (proposition d'édition de règle, jamais auto-appliquée), Researcher (proposition de plan d'expérience, jamais auto-exécutée).

**Décision produit active** : le short est **désactivé sur la baseline** (décision du 21/09, étude `docs/ETUDE-ICHIVOL-PLUS-ACTIF-2026-09-20.md` : les shorts faisaient 80 % des pertes). C'est une hypothèse de recherche ouverte, pas fermée définitivement — voir les critères de réactivation dans le doc de feuille de route.

**Manque connu, non bloquant** : le scénario "crash" de T0-CALC n'est calculé que pour un LONG ; pour un SHORT il retombe silencieusement sur la valeur du stop. Sans conséquence tant que le short reste désactivé.

## Travail en cours, à finir en premier

Branche **`cursor/t0-notif-push-a2fe`** (PR #44, draft), chantier **T0-NOTIF** (alertes push mobile sur les positions ouvertes : objectif/stop proches, accélération confirmée par le moteur, changement de direction). Ma revue était en cours au moment du transfert :

- ✅ Aucun appel n'ouvre/ferme de position depuis le watcher (grep vérifié).
- ✅ L'accélération n'est déclenchée que si le moteur confirme RVOL + cassure de structure, jamais une supposition.
- ✅ Dédoublonnage correct (bandes 20/10/5 % + cooldown, se redéclenche sur un vrai changement d'état).
- ✅ Isolation entre utilisateurs vérifiée (`user_id` filtré partout).
- ✅ Migration Prisma propre, golden API additive seulement (0 ligne retirée), build front OK.
- ⚠️ **1 test en échec** : `src/notifications/positionWatch.test.ts`, sous-test "sendPush never throws on invalid sub" → erreur `@prisma/client did not initialize yet`. **À diagnostiquer en premier** : ça sent l'environnement (prisma generate pas lancé avant les tests côté serveur) plutôt qu'un vrai bug, mais vérifie-le avant de valider — relance `npx prisma generate` puis `npm test` dans `ichivol-app/server` et regarde si ça persiste.

Une fois ce point tranché (environnement ou vrai bug à corriger), termine la revue de T0-NOTIF et donne le verdict à l'utilisateur/Cursor, puis enchaîne sur **T0-MANAGE** (stop suiveur, prise de profit partielle, renforcement encadré), qui est le prochain job prévu dans la feuille de route.
