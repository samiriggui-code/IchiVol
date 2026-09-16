# Handoff — Cursor (Frontend)

Destiné à : Cursor, qui reprend le développement frontend (pages restantes : Backtests). Rédigé le 2026-09-15 par une des sessions Claude Code qui travaille sur ce repo en parallèle (moteur Python `ichivol-app/engine/`). Ce document décrit l'état **réellement vérifié** du code à cette date — pas un plan aspirationnel.

**Mise à jour 2026-09-15 (fin de journée) : la décision de routage est prise et implémentée — Express proxy `/api/engine/*` vers le moteur Python (port 8000), voir §"API serveur Express". `DecisionsPage.tsx` est branché et fonctionne avec de vraies données (testé en conditions réelles, capture d'écran à l'appui). Seule `BacktestsPage.tsx` reste un vrai placeholder, car le moteur de backtest n'existe pas encore.**

## Contexte : plusieurs agents travaillent sur ce repo en parallèle

Pour éviter les collisions de fichiers, sache que d'autres sessions IA travaillent activement sur ce projet :
- Une session Claude Code s'occupe de l'auth serveur (JWT/cookie), du schéma Prisma (`server/prisma/schema.prisma`), et vient de construire le shell de dashboard (`layouts/DashboardShell`, `Root.tsx`, les pages placeholders `OverviewPage`/`MarketPage`/`DecisionsPage`/`BacktestsPage`/`SettingsPage`).
- Une session Claude Code construit le moteur Python (`ichivol-app/engine/`) : Ichimoku, RVOL, agents, decision combiner, collecteur OHLCV — détaillé plus bas.
- Une recherche GrokDesk/architecture a été **tranchée** : north star verrouillée dans `docs/TRADING_ARCHITECTURE_V2.md` + `METHODS-ROADMAP.md` + `MARKET-DATA-STRATEGY.md`. Si Claude reprend le moteur : lui coller `docs/HANDOFF-CLAUDE-REALIGN-NORTHSTAR.md` en premier.

Avant de modifier un fichier qui semble déjà « en cours » ailleurs (notamment `LoginPage.tsx`, `RequireAuth.tsx`, `App.tsx`/`MarketPage.tsx`, `PriceChart.tsx`, `Screener.tsx`, `LandingPage.tsx`, `camap-tokens.css`), il vaut mieux vérifier avec l'utilisateur plutôt que de réécrire par-dessus un travail en cours.

## Architecture actuelle (3 process séparés)

| Process | Stack | Port | État |
|---|---|---|---|
| `ichivol-app/` (SPA) | Vite + React 19 + react-router | 5173 (dev) | Fonctionnel |
| `ichivol-app/server/` | Express + Prisma + Postgres (`ichivol_dev`) | 8787 | Auth fonctionnelle, reste à minima |
| `ichivol-app/engine/` | Python FastAPI + SQLAlchemy + Postgres (`ichivol_engine_dev`) | 8000, à démarrer manuellement (`uvicorn app.main:app --port 8000 --reload`, voir `engine/README.md`) | Logique métier + routes `/api/engine/{health,screener,decisions/{symbol}}` prêtes et testées (40 tests) |

Le proxy Vite (`vite.config.ts`) route `/api/*` → `localhost:8787` (le serveur Express), plus `/binance`, `/bybit`, `/okx`, `/coingecko`, `/feargreed` vers les APIs externes correspondantes. Express relaie ensuite `/api/engine/*` vers le moteur Python (port 8000) — voir §"API serveur Express" plus bas. **Il faut donc que les trois process tournent** (Vite 5173, Express 8787, engine 8000) pour que `/app/decisions` fonctionne.

## Routing frontend actuel (`src/Root.tsx`)

```
/                    LandingPage        (fait)
/login               LoginPage          (en cours ailleurs)
/app (RequireAuth)   DashboardShell
  /app/overview      OverviewPage       (placeholder "Bientôt")
  /app/market        MarketPage         (ex-App.tsx, fonctionnel : chart + screener)
  /app/context        ContextPanel      (fonctionnel : contexte macro)
  /app/decisions     DecisionsPage      (fait — screener + détail décision, données réelles)
  /app/backtests     BacktestsPage      (placeholder "Bientôt" — le moteur de backtest n'existe pas encore)
  /app/settings      SettingsPage       (fait par Cursor — formulaire LLM + sources + thème)
```

## API serveur Express actuelle (port 8787)

```
GET   /api/health
POST  /api/auth/login
POST  /api/auth/logout
GET   /api/auth/me
GET   /api/settings      (requireAuth)
PATCH /api/settings      (requireAuth)
POST  /api/agent/chat    (requireAuth)
GET   /api/engine/*      (requireAuth) — proxy passthrough vers le moteur Python
```

**Décision de routage prise : Express proxy, pas un second proxy Vite.** `server/src/engine/proxy.ts` relaie tel quel (même path, `requireAuth`, timeout 45s) vers `config.engineUrl` (env `ENGINE_URL`, défaut `http://127.0.0.1:8000`). Choisi pour rester cohérent avec le pattern existant (un seul point d'entrée `/api/*` pour le front, déjà en place pour auth/settings/agent) plutôt que de faire connaître au front un deuxième backend. `BacktestsPage.tsx` pourra réutiliser exactement le même mécanisme le jour où le moteur de backtest existera (pas de nouveau proxy à écrire).

**Perf mesurée en réel** : le screener sur 20 paires est parallélisé côté moteur (`ThreadPoolExecutor`, 6 requêtes Binance en simultané) — la première version séquentielle dépassait le timeout du proxy (15s) et a été corrigée. Compte 2-5s pour un scan complet.

## Schéma Prisma actuel (`server/prisma/schema.prisma`, DB `ichivol_dev`)

```prisma
model User {
  id, email, passwordHash, role, createdAt, updatedAt
  setting Setting?
  decisions Decision[]
}

model Setting {
  userId (unique, 1:1 avec User)
  activeSources   Json  @default(["binance"])
  ichimokuParams  Json  @default({"tenkan":9,"kijun":26,"senkouB":52,"displacement":26})
  volumeParams    Json  @default({"rvolLen":20,"rvolConfirm":1.5,"spikeMult":2})
  theme           String @default("dark")
  llmProvider     String @default("openrouter")   // ajouté par Cursor
  llmModel        String @default("openai/gpt-4o-mini")
  llmApiKeyEnc    String?                          // chiffré, jamais renvoyé en clair par GET
}

model Decision {
  userId, symbol, interval, bias, rvol, signalKind?, note?, status, createdAt, updatedAt
}
```

**`/api/settings` (GET/PATCH) est fait**, avec `llmApiKeyEnc` chiffré et jamais renvoyé en clair — voir [`HANDOFF-SETTINGS-API-KEYS.md`](./HANDOFF-SETTINGS-API-KEYS.md) pour la spec complète (déjà implémentée, ce doc sert maintenant de référence plutôt que de todo-list).

Les valeurs par défaut ci-dessus correspondent exactement aux constantes déjà utilisées côté client dans `src/lib/types.ts` (`DEFAULT_ICHI`, `DEFAULT_VOL`) — les réutiliser plutôt que redéfinir des valeurs par défaut différentes.

## Moteur Python (`ichivol-app/engine/`) — ce qu'il fait déjà, et ce qui manque pour que le front puisse le consommer

Base de données séparée (`ichivol_engine_dev`), aucune donnée mockée — testé avec de vraies bougies Binance BTCUSDT.

Ce qui existe et est testé (40 tests passent) :
- `app/indicators/ichimoku.py` — état structuré Ichimoku (`price_vs_kumo`, `tk_cross`, `future_kumo`, `chikou_state`, `kumo_breakout`, `kumo_thickness`, `trend_strength`, `score`), anti-lookahead prouvé.
- `app/indicators/rvol.py` — RVOL/RVOL5/10/20, `anomaly_level` (LOW/NORMAL/SIGNIFICANT/STRONG/ANOMALY).
- `app/agents/{ichimoku_agent,rvol_agent}.py` — sortie `{agent, direction, probability, confidence, expected_value, reasons[], invalidation[], metadata}`.
- `app/decision/combiner.py` — combine les deux agents en une `Decision` : `{decision: STRONG_BUY|BUY|WATCH|WAIT|SELL|STRONG_SELL, direction, probability, confidence, agreement, weights_used, reasons[], risks[], invalidation[]}`.
- `app/market_data/` — collecteur OHLCV Binance → table `candles` (idempotent, vérifié en conditions réelles).
- `app/screener/` — scan multi-actifs (20 symboles, même univers que `WATCHLIST` dans `src/lib/binance.ts`), classé par décision actionnable puis confiance ; chaque scan est persisté (`strategy_signals`/`agent_predictions`/`decisions`) pour être traçable.
- **`app/api/routes.py` — routes FastAPI réelles, montées sous `/api/engine` :**
  - `GET /api/engine/screener?timeframe=1h` → `{timeframe, rows: [{symbol, timeframe, price, decision, direction, confidence, probability, ichimoku_score, rvol}]}`
  - `GET /api/engine/decisions/{symbol}?timeframe=1h` → le détail complet d'une décision : tous les champs ci-dessus + `reasons[]`, `risks[]`, `invalidation[]`, `agreement`, `weights_used`, `strategy_version`, `timestamp`, plus le détail par agent (`ichimoku`, `rvol_detail`).

**`DecisionsPage.tsx` est fait** (`src/pages/DecisionsPage.tsx` + `src/lib/decisions.ts`) : table screener (tri décision actionnable puis confiance), clic sur une ligne → panneau détail (raisons/risques/invalidation/accord). Testé en conditions réelles (capture d'écran, vraies données Binance).

Ce qui reste :
1. Le service FastAPI n'a pas de process manager permanent (pas de PM2/service Windows) — il faut le démarrer manuellement (`engine/README.md`). À automatiser un jour (script `dev` racine qui lance les 3 process ?).
2. Pas de cache : chaque appel à `/api/engine/screener` refait un scan live parallélisé (~2-5s pour 20 paires) — correct pour un usage manuel, pas pour du polling fréquent/temps réel.
3. `BacktestsPage.tsx` reste à faire, mais bloqué sur l'existence du moteur de backtest (pas encore construit côté Python).

## Recommandations concrètes pour Cursor

- **Rôles (ne pas confondre)** :
  - **Cursor** = frontend SPA (`src/pages/*`, shell, CSS densifié) — dont `/app/settings`
  - **Claude auth/DB** = Express auth, Prisma, routes API serveur
  - **Claude engine** = `ichivol-app/engine/` Python — ne pas toucher depuis Cursor
- **Exception 2026-09-15** : Cursor a livré bout-en-bout Settings (UI + `GET/PATCH /api/settings` + champs LLM Prisma) car Claude auth était ailleurs. Ne pas re-implémenter. Voir `HANDOFF-SETTINGS-API-KEYS.md` checklist.
- Réutilise les types déjà définis dans `src/lib/types.ts` (`Candle`, `IchimokuParams`, `VolumeParams`, `ScreenerRow`, `Signal`) plutôt que d'en recréer des équivalents.
- Le style partagé vit dans `src/theme/camap-tokens.css` (tokens couleur/police/radius, light+dark) et `src/theme/camap-landing.css` (composants landing/login) — les pages du dashboard utilisent `src/index.css`.
- Pour Decisions/Backtests : si la route API n'existe pas encore, le dire à l'utilisateur plutôt que de mocker silencieusement des vrais signaux.
