# IchiVol — Agent Server

Petit backend Express (TypeScript) qui héberge l'agent IA d'IchiVol. Il garde les clés API des LLM côté serveur (jamais exposées au navigateur) et sert le référentiel anti-hallucination.

## Lancer

```bash
npm install
cp .env.example .env   # renseigner au moins une clé
npm run dev             # http://localhost:8787
```

`GET /api/health` renvoie `{ ok, provider, model, checks: { database, engine } }` -- `ok` (et le code HTTP, 200 ou 503) reflète un vrai test de connexion DB + `GET /api/engine/health`, pas juste "le process Express répond" (voir `src/health/check.ts`).

## Providers LLM

Un seul appel HTTP `fetch` par provider (pas de SDK), sélectionné via `LLM_PROVIDER` (`anthropic` | `openai` | `openrouter`), avec override possible par requête (`provider` dans le body de `/api/agent/chat`) pour tester sans redémarrer.

## Sources (anti-hallucination)

Déclarées dans `src/sources/registry.ts` :

- **`binance-academy`** (kb) — référentiel de théorie : 8 articles Binance Academy scrapés une fois (Ichimoku, volume/VWAP, breakout, support/résistance, stratégies, chandeliers), versionnés en markdown dans `src/knowledge/docs/`. Recherche par recouvrement de termes/TF-IDF maison (`src/knowledge/retriever.ts`), sans base vectorielle — corpus volontairement petit.
- **`binance-market-data`** (live-api) — les mêmes endpoints publics que l'app (`/api/v3/klines`, `/api/v3/ticker/24hr` sur `data-api.binance.vision`). Le backend ne les appelle pas lui-même : le frontend envoie les valeurs déjà calculées par `App.tsx` (biais Ichimoku, RVOL, dernier signal), et le prompt système interdit explicitement au modèle d'inventer un chiffre en dehors de ce qui est fourni.

Chaque réponse de `/api/agent/chat` renvoie un tableau `citations` reconstruit côté serveur à partir des chunks réellement récupérés (jamais des URLs que le modèle pourrait citer de mémoire).

## Notifications système (watchdog + digest, 2026-09-17)

Deux jobs d'arrière-plan démarrés dans `src/index.ts` (même pattern `setInterval` que `startJournalWatchJob`), aucun ne vote/décide quoi que ce soit -- purement informationnel :

- **`src/notifications/systemWatchdog.ts`** -- ping `checkSystemHealth()` (le même check que `/api/health`) toutes les `WATCHDOG_INTERVAL_MS` (5 min par défaut). N'alerte que sur un **changement d'état** (sain→en panne, ou en panne→rétabli), jamais à chaque poll pendant que ça reste cassé -- sinon ça spam. Rien n'est envoyé au tout premier check du process (évite un faux "rétabli" au démarrage).
- **`src/notifications/digest.ts`** -- une fois par `DIGEST_INTERVAL_MS` (24h par défaut), résume `GET /paper/performance` (condition 2 : historique paper trading) et `GET /backtest/evidence` (condition 1 : edge de rendement) — les deux conditions du gate broker live, `docs/CAHIER-DES-CHARGES.md` §5 V3.

Les deux créent une notification in-app (`kind: system_alert | system_digest`, visibles dans la cloche header comme n'importe quelle autre) **et**, si `SMTP_HOST`/`SMTP_USER`/`SMTP_PASSWORD` sont configurés, un email via `src/notifications/mailer.ts` (nodemailer) avec un template React Email (`src/notifications/emails/{AlertEmail,DigestEmail}.tsx`, rendu en HTML via `@react-email/render`). Sans config SMTP, `sendMail()` log un avertissement une fois et retourne `false` sans jamais lever d'exception -- les notifications in-app continuent de fonctionner dans tous les cas, l'email est un bonus optionnel.

Smoke test (pas de suite de tests dans ce package, voir `scripts/smoke-e*.ts`) : `npx tsx scripts/smoke-e7-notifications.ts` -- vérifie la forme du health check, le rendu réel des deux templates (HTML non trivial), et la dégradation propre de `sendMail` sans config SMTP.

## Rafraîchir le référentiel

Le scraping n'est pas automatisé dans l'app (pas d'appel réseau vers Binance Academy à l'exécution). Pour ajouter/mettre à jour un article, ajouter un fichier `.md` dans `src/knowledge/docs/` avec le frontmatter :

```md
---
title: "Titre de l'article"
url: "https://www.binance.com/en/academy/..."
tags: ["tag1", "tag2"]
source: "Binance Academy"
---
# Titre
...contenu...
```
