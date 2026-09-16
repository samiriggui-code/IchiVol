# IchiVol — Agent Server

Petit backend Express (TypeScript) qui héberge l'agent IA d'IchiVol. Il garde les clés API des LLM côté serveur (jamais exposées au navigateur) et sert le référentiel anti-hallucination.

## Lancer

```bash
npm install
cp .env.example .env   # renseigner au moins une clé
npm run dev             # http://localhost:8787
```

`GET /api/health` doit répondre `{ ok: true, provider, model }`.

## Providers LLM

Un seul appel HTTP `fetch` par provider (pas de SDK), sélectionné via `LLM_PROVIDER` (`anthropic` | `openai` | `openrouter`), avec override possible par requête (`provider` dans le body de `/api/agent/chat`) pour tester sans redémarrer.

## Sources (anti-hallucination)

Déclarées dans `src/sources/registry.ts` :

- **`binance-academy`** (kb) — référentiel de théorie : 8 articles Binance Academy scrapés une fois (Ichimoku, volume/VWAP, breakout, support/résistance, stratégies, chandeliers), versionnés en markdown dans `src/knowledge/docs/`. Recherche par recouvrement de termes/TF-IDF maison (`src/knowledge/retriever.ts`), sans base vectorielle — corpus volontairement petit.
- **`binance-market-data`** (live-api) — les mêmes endpoints publics que l'app (`/api/v3/klines`, `/api/v3/ticker/24hr` sur `data-api.binance.vision`). Le backend ne les appelle pas lui-même : le frontend envoie les valeurs déjà calculées par `App.tsx` (biais Ichimoku, RVOL, dernier signal), et le prompt système interdit explicitement au modèle d'inventer un chiffre en dehors de ce qui est fourni.

Chaque réponse de `/api/agent/chat` renvoie un tableau `citations` reconstruit côté serveur à partir des chunks réellement récupérés (jamais des URLs que le modèle pourrait citer de mémoire).

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
