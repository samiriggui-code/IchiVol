# Handoff Cursor — Agent Claude, overlay Structure, multi-clés LLM, retrait MT5

> **Pour :** Cursor (agent qui édite Paper / Synthèse / front en parallèle)  
> **De :** Claude Code (session « agent / chat / structure »)  
> **Date :** 2026-09-20  
> **Refs :** [`HANDOFF-CLAUDE-AGENT-CHANNEL.md`](./HANDOFF-CLAUDE-AGENT-CHANNEL.md) · [`TRADING_ARCHITECTURE_V2.md`](./TRADING_ARCHITECTURE_V2.md) · [`ARCHITECTURE-CONSOLIDEE-V2.md`](./ARCHITECTURE-CONSOLIDEE-V2.md) §13  
> **Objet :** dire ce qui a été fait, où c'est, ce qui est en prod, et comment ne pas se marcher dessus.

---

## 0. Règles de coordination (à lire d'abord)

1. **Index git partagé.** Deux agents dans le même dossier se marchent sur l'index. Le commit `269a02b` (« feat(paper): V1 synthèse… ») a embarqué **46 fichiers**, dont tout mon travail (MT5, agent Claude, Structure). Il est poussé, je n'ai pas réécrit l'historique. Le contenu est bon, seul le message est trompeur.
   - Commiter **par chemins explicites**, jamais `git add -A` ni `git commit -a`.
   - Idéalement via un index temporaire (`GIT_INDEX_FILE=… git read-tree HEAD && git add <chemins> && git commit`, puis `git reset -q`).
2. **Ne pas reconstruire `web` depuis un working tree « sale ».** Le build embarque tout `ichivol-app/src`, y compris du travail à moitié fini. Je n'ai donc **pas** redéployé `web` depuis mes derniers changements front (voir §3).
3. **Déploiement partiel** : un service à la fois (`docker compose … build <svc>` puis `up -d --no-deps <svc>`). Le compose du VPS est **identique à celui du dépôt** (plus de MT5, plus de variables factices à exporter).
4. **Partage proposé** : toi = Paper, Synthèse, Décisions, endpoints engine `paper`. Moi = agent/chat, structure (overlay), réglages LLM. Prévenir avant de toucher `routes.py`, `index.css`, `DashboardShell.tsx`, `Root.tsx` ou le VPS.
5. **Pas de push sans accord de l'utilisateur** (accord donné pour `a21abf5`, c'est fait).

---

## 1. Ce qui a été fait

### 1.1 MT5 : retiré partout
Le bridge Wine/MT5 n'a jamais abouti sur le VPS partagé (l'installeur MT5 se figeait sous Wine ; une image communautaire a aussi échoué). À la demande de l'utilisateur : **supprimé du dépôt et du VPS**.
- Dépôt : `ichivol-app/mt5-bridge/`, `market_data/mt5.py`, `tests/market_data/test_mt5.py`, doc `HANDOFF-CLAUDE-MT5-UPGRADE-2026-09-19.md` supprimés ; `docker-compose.yml`, `.env.example` (×2), `config.py`, `registry.py`, `volume_semantics.py`, `test_registry.py` restaurés à leur état d'avant MT5 (`162af71`).
- VPS : plus aucun conteneur, volume, réseau ou variable MT5.
- Restent des **mentions d'architecture** (« MCP MT5 = beaucoup plus tard ») dans `TRADING_ARCHITECTURE_V2.md` et `ARCHITECTURE-CONSOLIDEE-V2.md` : c'est une intention future, rien n'est construit.

### 1.2 Overlay Structure sur le graphique (page Marché)
- **Moteur** : `GET /structure/{symbol}` renvoie maintenant, pour chaque trendline, `start_time`, `end_time`, `start_price`, `end_price` (avant : seulement des indices de barre). `routes.py` : `_line_dict(line, series)` + `window` dans `get_structure`. Test : `engine/tests/api/test_structure_line_dict.py`.
- **Front** : `src/lib/structure.ts` (client + `toStructureOverlay`, garde les 3 meilleures zones et 2 meilleures trendlines par côté), couche « Structure » dans `PriceChart.tsx`, chargement dans `MarketPage.tsx` (**pas** pour `twelve_data` : crédits limités).
- Pas encore : Fibonacci, VWAP, POC (l'API de décision n'expose pas ces niveaux au front).

### 1.3 Agent Claude (chat) : tool use + streaming
- **Serveur** (`ichivol-app/server/src/agent/`) :
  - `claudeTools.ts` : boucle d'outils Anthropic, lecteur du flux SSE, conversion du manifeste moteur en outils Claude. **Allowlist lecture seule** : 19 outils (les 20 commandes du canal agent moins `list_tools`) + `search_knowledge`. Résultats tronqués à 12 000 caractères, 6 tours d'outils max puis réponse forcée (`tool_choice: none`).
  - `claudeAgent.ts` : exécute les outils (`engineAgentCommand`), cache du manifeste 5 min, citations KB.
  - `route.ts` : si le fournisseur résolu est **`anthropic`** → agent à outils (JSON, ou SSE si `stream: true`). Sinon → **ancien chemin inchangé** (OpenRouter/OpenAI). Les intentions qui écrivent (`save_decision`, `pin_symbol`, `open_paper_position`) restent court-circuitées par le planificateur avec **confirmation utilisateur**.
  - `systemPrompt.ts` : `buildAgentSystemPrompt` (le moteur décide, Claude explique ; tags `[MOTEUR]/[RAG]/[GK]`).
- **Front** : `lib/agent.ts` (`askAgentStream`, lit le SSE, repli JSON automatique), `components/AgentPanel.tsx` (bulle en direct, ligne « Moteur interrogé : … »), `pages/AgentPage.tsx` simplifiée.
- **Supprimé (inutile)** : `AgentChat.tsx` (bulle flottante), `AgentEnginePanel.tsx` (589 lignes, boutons manuels), `lib/agentChannel.ts`, `server/src/agent/tools/engineChannelTools.ts` (jamais appelé), les 4 pastilles de mode.
- **Contrat SSE** (`POST /api/agent/chat`, corps `stream: true`) : lignes `data: {json}\n\n` de type `text {delta}`, `tool_start {name,input}`, `tool_end {name,ok,ms}`, `done {response}`, `error {error}`. En-tête `X-Accel-Buffering: no`. Fermeture de l'onglet ⇒ annulation de l'appel Claude.

### 1.4 Réglages LLM : une clé par fournisseur
Avant : une seule clé perso (`llmApiKeyEnc`) rattachée au fournisseur actif, donc en ajouter une **remplaçait** l'autre.
- Colonne `settings.llmKeysEnc` (JSONB) + migration `20260920100000_llm_keys_per_provider` (appliquée en prod). L'ancienne clé est traitée comme celle du fournisseur qui était actif, puis migrée au prochain enregistrement.
- Logique pure : `server/src/settings/llmKeys.ts` (+ tests). `resolveLlmForUser(userId, providerOverride?)` : clé perso du fournisseur demandé, sinon clé du `.env`, et modèle par défaut du fournisseur si ce n'est pas l'actif. Cela corrige aussi un défaut latent : un `provider` demandé dans le chat réutilisait la clé du fournisseur actif.
- `PATCH /api/settings` : `llmApiKey` est écrit pour `llmProvider` (celui du même PATCH, sinon l'actif) et **ne touche pas** les autres fournisseurs. `llmConnections` est calculé par fournisseur.
- Front : sélecteur de fournisseur dans le chat (`AgentPanel.tsx`, choix mémorisé dans `localStorage`).

---

## 2. État en production (VPS)

| Service | État |
|---|---|
| `ichivol-server` | **Déployé** : agent Claude + streaming + multi-clés + migration appliquée (colonne `llmKeysEnc` vérifiée). |
| `ichivol-engine` / `ichivol-web` | Reconstruits par une autre session depuis le working tree (overlay Structure inclus). **À vérifier** : le `web` en ligne contient-il le sélecteur de fournisseur ? (`AgentPanel.tsx` / `lib/agent.ts` sont commités dans `a21abf5`.) |
| `.env` | `LLM_PROVIDER=openrouter` **conservé** ; `ANTHROPIC_API_KEY` ajoutée à côté (les deux coexistent). |

Vérifié en prod (lecture seule) : OpenRouter reste actif, Anthropic est résolu avec sa propre clé et son modèle `claude-sonnet-4-5`.

**Sauvegardes** (`/opt/ichivol-backup/`) : `pre-deploy-20260920-0109.tgz` (src + engine/app, avant l'autre session), `server-pre-claude-agent-20260919-2318.tgz`, `server-pre-multikey-20260920-0933.tgz`, `ichivol-db-20260920-0933.sql.gz` ; et `deploy/vps/.env.bak-20260920-0923`.

---

## 3. Points ouverts

1. **L'agent Claude n'a jamais tourné pour de vrai.** La clé Anthropic est valide mais le compte renvoie *« credit balance is too low »*. Tant que l'utilisateur n'ajoute pas de crédits, tout reste sur OpenRouter. Tests réalisés : 16 tests serveur (`npm test` dans `server/`, faux `fetch`), lecteur SSE du navigateur testé à part, `tsc` OK des deux côtés. **Pas de test de bout en bout** avec une vraie clé ni dans un navigateur.
2. **Rendu de l'overlay Structure** jamais vu à l'écran (pas de moteur local lancé).
3. **`web` à reconstruire** quand tes pages Paper/Synthèse compilent et sont stables. Le working tree contenait au moment de l'écriture des changements que je n'ai pas faits : `Root.tsx`, `BrokerAccount.tsx`, `NavIcons.tsx`, `OverviewPage.tsx`, `PaperPage.tsx`, `WatchlistPage.tsx`, `SynthesePage.tsx` (non suivi), `PaperTechPage.tsx` (supprimé), `server/src/notifications/digest.ts`. Je n'y touche pas.
4. **`routes.py`** : l'autre session avait déplacé `get_paper_portfolio` plus bas dans son working tree (hunk qui n'est pas de moi). À toi de le garder ou non.
5. **Message du commit `269a02b`** : à documenter ou laisser tel quel, décision de l'utilisateur.
6. **Docs périmées** : le README engine annonce 9 commandes agent, il y en a 20.

---

## 4. Contrats à ne pas casser

- `GET /api/engine/structure/{symbol}` : champs `start_time/end_time/start_price/end_price` sur les trendlines de `detectors.*` (utilisés par `lib/structure.ts`).
- `POST /api/agent/chat` : champs `provider` et `stream` optionnels ; réponse JSON inchangée pour les autres fournisseurs et pour les actions à confirmer.
- `GET/PATCH /api/settings` : `llmConnections[]` par fournisseur ; `llmApiKey` = clé du fournisseur du PATCH (jamais un remplacement global).
- Engine agent channel : lecture seule uniquement (`write_tier_enabled: false`). Ne pas exposer de commande d'écriture à Claude sans nouvelle décision produit.
- Aucune clé dans git : `.env` du VPS uniquement ; les clés perso sont chiffrées en base (`SETTINGS_SECRET`).

---

## 5. Vérifier rapidement

```bash
# serveur
cd ichivol-app/server && npx tsc -p tsconfig.json --noEmit && npm test     # 16 tests
# front
cd ichivol-app && npx tsc -p tsconfig.app.json --noEmit
# engine
cd ichivol-app/engine && ./.venv/Scripts/python.exe -m pytest tests/api/test_structure_line_dict.py -q
```
