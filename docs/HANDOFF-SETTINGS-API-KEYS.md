# Handoff Claude — Settings + clés API client

> **Pour :** Claude auth/DB (référence) · **Livré par Cursor** le 2026-09-15  
> **De :** Cursor (UI + API settings, exception roles — Claude était sur engine)  
> **Date :** 2026-09-15  
> **Doc parent :** [`AUDIT-AJOUTS-AUTH-DB-AGENT.md`](./AUDIT-AJOUTS-AUTH-DB-AGENT.md)  
> **Roles :** voir aussi [`HANDOFF-CURSOR-FRONTEND.md`](./HANDOFF-CURSOR-FRONTEND.md)

---

## Statut : LIVRÉ (ne pas refaire)

| Élément | Statut |
|---------|--------|
| Page `/app/settings` form LLM + sources + indicateurs | ✅ |
| Menu user → Paramètres + statut LLM | ✅ |
| `GET/PATCH /api/settings` | ✅ |
| Prisma `llmProvider` / `llmModel` / `llmApiKeyEnc` + migration | ✅ |
| Agent chat : settings → fallback `.env` | ✅ |
| Clé jamais renvoyée en clair (`llmApiKeySet` seulement) | ✅ |

**Next Claude auth/DB :** P3 threads agent / P4 decisions mémoire — pas Settings.  
**Next Claude engine :** routes FastAPI `/api/engine/*` — pas le SPA.  
**Next Cursor :** Decisions/Backtests UI quand les APIs existent.

---

## 1. Pourquoi ce handoff

Le client doit pouvoir **configurer depuis l’UI** (pas seulement via `server/.env`) :

1. **LLM** — provider + clé + modèle (Anthropic / OpenAI / OpenRouter)  
2. **Marchés** — éventuellement clés exchange (voir §4 — optionnel MVP)  
3. Accès depuis le **menu user** (header) + page **Settings** (sidebar)

Aujourd’hui ces surfaces sont des **coquilles vides**.

---

## 2. État réel du chantier (ne pas refaire)

### Fait par Claude (backend) — OK

| Élément | Statut | Où |
|---------|--------|-----|
| Postgres dédié + Prisma | ✅ | `server/prisma/schema.prisma` — `users`, `settings`, `decisions` |
| Migration init | ✅ | `server/prisma/migrations/20260915105941_init/` |
| Seed admin | ✅ | `server/prisma/seed-admin.ts` |
| Auth cookie JWT httpOnly | ✅ | `server/src/auth/*` — `POST /login`, `POST /logout`, `GET /me` |
| Front auth branché API | ✅ | `src/lib/auth.ts` — plus de sessionStorage fake |
| Agent chat protégé | ✅ | `requireAuth` sur `POST /api/agent/chat` |
| Providers LLM (env) | ✅ | Anthropic / OpenAI / OpenRouter via `server/.env` |

### Fait par Cursor (UI) — OK, ne pas casser

| Élément | Statut |
|---------|--------|
| Shell dashboard dense (sidebar 168px, header 36px, base 12px) | ✅ |
| Tokens GSMS (Manrope / Newsreader / blue) | ✅ |
| Overview / Market / AgentChat floating | ✅ |
| Pages Decisions / Backtests / Settings = **placeholders** | ⚠️ intentionnel |

### Pas fait — **ton chantier immédiat**

| Élément | Statut |
|---------|--------|
| Page Settings réelle | ❌ placeholder `SettingsPage.tsx` |
| Menu user (header) au-delà de email + logout | ❌ |
| API `GET/PATCH /api/settings` | ❌ |
| Stockage clés LLM (chiffrées) en DB | ❌ — schéma `settings` **sans** champs secrets |
| Runtime LLM depuis settings user (pas seulement env) | ❌ — `config.ts` lit uniquement `process.env` |
| Clés API marchés côté client | ❌ (et souvent inutiles — §4) |
| Décisions UI + agent mémoire | ❌ (phases suivantes, hors ce handoff) |

---

## 3. Gaps UI concrets

### 3.1 Menu user — `DashboardShell.tsx`

Aujourd’hui :
- avatar + email
- bouton Déconnexion

**Attendu MVP :**
- lien **Paramètres** → `/app/settings`
- statut LLM court (ex. `OpenRouter · gpt-4o-mini` ou `LLM non configuré`)
- Déconnexion (garder)

Pas besoin de sous-menu “profil” complexe (1 admin).

### 3.2 Page Settings — `SettingsPage.tsx`

Placeholder « Bientôt ». Remplacer par un formulaire dense (style cockpit déjà en CSS).

---

## 4. Produit — 2 ou 3 paramètres pour que ça marche

### Bloc A — LLM (obligatoire pour l’agent)

Exactement **3 champs** :

| Champ | Type | Valeurs / notes |
|-------|------|-----------------|
| `llmProvider` | enum | `anthropic` \| `openai` \| `openrouter` |
| `llmApiKey` | secret string | Une seule clé active (celle du provider choisi) |
| `llmModel` | string | Ex. `claude-sonnet-4-5`, `gpt-4o-mini`, `openai/gpt-4o-mini` |

Comportement :
- À la sauvegarde → persister (chiffré) + invalider le provider en cache si besoin  
- Au chat agent → résoudre clé/modèle dans cet ordre : **settings user → fallback `server/.env`**  
- GET settings **ne renvoie jamais** la clé en clair : seulement `llmApiKeySet: boolean` + last4 optionnel  
- PATCH avec `llmApiKey: ""` = effacer la clé stockée  

Réutiliser le code providers existant (`server/src/providers/*`) — ne pas réécrire les clients HTTP.

### Bloc B — Marchés (optionnel MVP)

**Fait important :** Binance / Bybit / OKX tourne aujourd’hui en **REST public** (klines / tickers) via proxies Vite. **Aucune clé exchange n’est requise** pour screener + chart.

Ne pas bloquer le MVP Settings sur des clés Binance. Si tu ajoutes un bloc « Marchés » :

| Champ | Rôle |
|-------|------|
| `activeSources` | déjà dans schéma (`["binance"]`…) — brancher l’UI dessus |
| `exchangeApiKey` / `exchangeApiSecret` | **reporté** (rate-limit privé / futures) — hors scope immédiat |

Message UI suggéré : *« Les données marché publiques fonctionnent sans clé. Les clés exchange arriveront pour les endpoints privés. »*

### Bloc C — Indicateurs (nice-to-have même PR)

Déjà en schéma Prisma `Setting` :
- `ichimokuParams` — tenkan / kijun / senkouB / displacement  
- `volumeParams` — rvolLen / rvolConfirm / spikeMult  
- `theme`

Brancher l’UI = lecture/écriture ; brancher le chart/screener dessus = **2e passe** (aujourd’hui hardcodé côté front).

---

## 5. Spec technique proposée

### Schéma — étendre `Setting`

```prisma
model Setting {
  // ... champs existants ...
  llmProvider   String  @default("openrouter")  // anthropic|openai|openrouter
  llmModel      String  @default("openai/gpt-4o-mini")
  llmApiKeyEnc  String? // ciphertext — jamais plain
  // optionnel plus tard:
  // exchangeKeysEnc Json?
}
```

Chiffrement : AES-256-GCM avec `SETTINGS_SECRET` (ou dérivé de `JWT_SECRET` documenté) dans `.env`.  
Ne jamais logger la clé.

### Routes

```
GET  /api/settings          requireAuth → prefs + llmProvider + llmModel + llmApiKeySet
PATCH /api/settings         requireAuth → upsert Setting pour req.user.id
```

Body PATCH (exemple) :
```json
{
  "llmProvider": "openrouter",
  "llmModel": "openai/gpt-4o-mini",
  "llmApiKey": "sk-or-…",
  "activeSources": ["binance", "bybit"],
  "theme": "dark"
}
```

### Runtime agent

Dans `handleAgentChat` / factory providers :
1. Charger `Setting` user  
2. Si `llmApiKeyEnc` présent → déchiffrer → passer au provider choisi  
3. Sinon → `config.*ApiKey` env (comportement actuel)  
4. Erreur claire si aucune clé : *« Configurez votre clé LLM dans Paramètres »*

Override `provider` dans le body chat : garder pour debug, mais la **source de vérité produit** = Settings.

### Front

| Fichier | Travail |
|---------|---------|
| `src/pages/SettingsPage.tsx` | Formulaire dense : LLM (3 champs) + sources + thème |
| `src/lib/settings.ts` | `getSettings` / `patchSettings` |
| `src/layouts/DashboardShell.tsx` | Lien Settings + badge « LLM OK / manquant » |
| CSS | Réutiliser classes `.panel`, `.controls`, `.field` — densités déjà OK |

Ne pas refaire le design system. Pas de gros cards / hero.

---

## 6. Critères « terminé » (ce handoff)

- [ ] `/app/settings` : form LLM (provider + model + key) sauvegardable  
- [ ] Menu user → lien Paramètres + indicateur clé configurée  
- [ ] Clé absente du GET JSON (seulement `llmApiKeySet`)  
- [ ] Agent chat utilise la clé Settings si présente, sinon `.env`  
- [ ] Message d’erreur UI/agent si aucune clé  
- [ ] Migration Prisma + seed inchangé (admin)  
- [ ] Aucune clé en clair dans git / logs / responses  
- [ ] UI dense cohérente avec le shell actuel  

Hors ce handoff : décisions UI, agent memory, orchestration actions, clés exchange privées.

---

## 7. Règles non négociables (rappel)

- IchiVol ≠ GSMS — DB `ichivol_*` séparée  
- 1 admin / 1 workspace  
- Pas d’ordres broker  
- Ne pas casser densités CSS Cursor (`index.css` shell + pages)  

---

## 8. Fichiers à lire en premier

```
ichivol-app/server/prisma/schema.prisma
ichivol-app/server/src/config.ts
ichivol-app/server/src/providers/*
ichivol-app/server/src/agent/route.ts
ichivol-app/server/src/auth/middleware.ts
ichivol-app/src/pages/SettingsPage.tsx
ichivol-app/src/layouts/DashboardShell.tsx
ichivol-app/src/lib/auth.ts
docs/AUDIT-AJOUTS-AUTH-DB-AGENT.md
```

---

## 9. Phases audit — mise à jour

| Phase | Statut |
|-------|--------|
| P0 SPEC | ✅ |
| P1 Postgres + schema users/settings/decisions | ✅ |
| P2 Auth cookie Express | ✅ |
| **P6 Settings persistés + clés LLM UI** | ⬅️ **next** (ce handoff) |
| P3 threads/messages agent | après P6 |
| P4 decisions/actions mémoire | après |
| P5 orchestrateur allowlist | après |

---

*Handoff prêt à coller dans un prompt Claude. Source de vérité pour Settings / API keys client.*
