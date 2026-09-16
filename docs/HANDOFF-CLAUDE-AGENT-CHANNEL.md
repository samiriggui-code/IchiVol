# Handoff Claude — Canal agent IchiVol (pattern ShadowBroker)

> **Pour :** Claude (engine Python uniquement)  
> **De :** Cursor  
> **Date :** 2026-09-16  
> **Refs :** [`HANDOFF-AGENT-CONCEPT.md`](./HANDOFF-AGENT-CONCEPT.md) · [`MARKET-DATA-STRATEGY.md`](./MARKET-DATA-STRATEGY.md) · `_research/Shadowbroker/` (inspiration only)  
> **Front :** Cursor — ne touche pas `src/` ni `server/src/` pour ce chantier

---

## 0. Décision produit (figée)

| Couche | Qui | Rôle |
|--------|-----|------|
| **Engine tools** | **Toi (Claude)** | Calculs déterministes exposés comme commandes agent |
| **Copilot LLM** | Cursor (Express + UI) | Interroge tes tools, explique, jamais recalcule Ichimoku/RVOL |

> L’IA ne calcule pas les indicateurs. Elle appelle ton moteur.

ShadowBroker = **référence d’architecture** sous `_research/Shadowbroker/`.  
**Ne pas cloner** map/OSINT/mesh/financial/prediction markets.  
**Récupérer le pattern :** allowlist → command → batch concurrent → discovery.

---

## 1. Ce que tu dois livrer (engine)

### 1.1 Endpoints (préfixe existant `/api/engine`)

| Méthode | Path | Rôle |
|---------|------|------|
| `GET` | `/agent/tools` | Manifeste : `{ available_commands: string[], commands: [{ name, tier, description, args_schema }] }` |
| `GET` | `/agent/capabilities` | Hints routing / latence / playbooks (optionnel v1, stub OK) |
| `POST` | `/agent/command` | Body `{ "cmd": string, "args": object }` → résultat tool |
| `POST` | `/agent/batch` | Body `{ "commands": [{ "cmd", "args" }, ...] }` max **20**, exécution **concurrente**, résultats **dans l’ordre** de la requête |

Auth : même confiance que le reste de l’engine local (pas d’HMAC ShadowBroker en v1). Documente dans `engine/README.md`.

### 1.2 Allowlist READ (v1 — obligatoire)

Chaque `cmd` **wrappe** du code déjà là. Pas de nouveaux indicateurs.

| `cmd` | Implémentation (réutiliser) | Notes |
|-------|----------------------------|-------|
| `scan_market` | logique `GET /screener` | args : `timeframe?`, filtres optionnels |
| `get_symbol_context` | logique `GET /decisions/{symbol}` | args : `symbol`, `timeframe` |
| `detect_signal` | même scan décision, champ pipeline / gate | alias sémantique OK si payload identique |
| `compare_timeframes` | N× décisions (ex. 15m/1h/4h) ou batch interne | args : `symbol`, `timeframes: string[]` |
| `run_backtest` | logique `GET /backtest/{symbol}` | args alignés route existante |
| `get_correlations` | logique `GET /correlations` | lecture seule |
| `calculate_ichimoku` | sortir les niveaux depuis le scan / indicators déjà calculés | **pas** de LLM ; chiffres engine only |
| `calculate_rvol` | idem RVOL | idem |
| `list_tools` | = sous-ensemble de `GET /agent/tools` | utile pour agents externes |

### 1.3 Allowlist WRITE (v1 — optionnel, tier `full` si tu veux)

| `cmd` | Implémentation | Notes |
|-------|----------------|-------|
| `open_paper` | `POST /paper/positions` | seulement si args valides ; pas d’orders live |
| `close_paper` | `POST /paper/positions/{id}/close` | idem |

Sinon : laisse WRITE hors v1 et documente `tier: read_only`.

### 1.4 Hors scope Claude (ne pas faire)

- Canal HMAC / OpenClaw / mesh
- News / calendrier / sentiment / prediction markets (plus tard, adapters séparés)
- Skills Copilot TS, prompts LLM, UI chat
- Fusion StrategyAgent ↔ Copilot
- Cloner du code ShadowBroker (OSINT, map, financial.py)

### 1.5 Qualité / contrats

1. Cmd inconnue → `400` + `{ "ok": false, "error": "unknown_command", "cmd": "..." }`  
2. Batch : un item en erreur n’échoue **pas** tout le batch (`ok`/`error` par index) — même pattern que `POST /decisions/batch`  
3. Timeout soft raisonnable (ex. 30s/commande) ; pool type `ThreadPoolExecutor` déjà utilisé ailleurs  
4. Tests pytest : tools manifest, command happy-path, unknown cmd, batch order + partial failure  
5. Mettre à jour `ichivol-app/engine/README.md` § Agent channel  

### 1.6 Playbooks (nice-to-have v1.1)

Dict interne (comme ShadowBroker `run_playbook`) :

| Playbook | Batch |
|----------|--------|
| `watchlist_pulse` | `scan_market` |
| `symbol_brief` | `get_symbol_context` + `compare_timeframes` + `get_correlations` (si symboles fournis) |

Exposé via `cmd: run_playbook` **ou** seulement documenté pour que Cursor les encode côté Copilot — au choix, dis-le dans le README.

---

## 2. Réponse JSON cible (contrat front)

### Command

```json
{
  "ok": true,
  "cmd": "get_symbol_context",
  "result": { }
}
```

`result` = **même forme** que la route HTTP équivalente quand c’est possible (ex. décision = payload `/decisions/{symbol}`), pour que Cursor ne réécrive pas les parsers.

### Batch

```json
{
  "ok": true,
  "results": [
    { "ok": true, "cmd": "scan_market", "result": { } },
    { "ok": false, "cmd": "run_backtest", "error": "..." }
  ]
}
```

### Tools

```json
{
  "available_commands": ["scan_market", "get_symbol_context", "..."],
  "commands": [
    {
      "name": "get_symbol_context",
      "tier": "read",
      "description": "Decision pipeline + stages for one symbol",
      "args": { "symbol": "string", "timeframe": "string" }
    }
  ]
}
```

---

## 3. Fichiers suggérés (engine)

```
engine/app/agent_channel/
  __init__.py
  allowlist.py      # READ_COMMANDS / WRITE_COMMANDS
  dispatch.py       # cmd → handler
  batch.py          # concurrent fan-out
engine/app/api/routes.py   # ou router dédié agent.py monté dans main
engine/tests/agent_channel/
```

Réutilise `app/screener/`, `app/decision/`, `app/backtest/`, `app/correlation/` — **ne duplique pas** la maths.

Inspiration locale (lecture seule) :

- `_research/Shadowbroker/backend/services/openclaw_channel.py` → allowlist + `submit_batch`
- `_research/Shadowbroker/backend/services/openclaw_routing.py` → playbooks / anti-dumps
- **Ne copie pas** auth HMAC ni OSINT

---

## 4. Critères « done » pour Claude

- [ ] `GET /agent/tools` liste au moins les READ v1  
- [ ] `POST /agent/command` exécute `get_symbol_context` et `scan_market`  
- [ ] `POST /agent/batch` max 20, ordre préservé, partial failure OK  
- [ ] Tests verts  
- [ ] README engine à jour  
- [ ] Aucun appel LLM dans ce module  

Quand c’est mergeable : note dans un mini-handoff « Cursor peut brancher le client ».

---

## 5. Ce que Cursor fait en parallèle (front / Express) — info seulement

**Branché (Cursor, 2026-09-16 soir) — canal live confirmé :**
- Clients alignés sur `{ tools }` / `{ ok, cmd, data|error }` (pas `result`)
- Copilot `explain_decision` → `POST /agent/batch` (`get_symbol_context` + `compare_timeframes`)
- `getDecisionDetailTool` → `get_symbol_context` (fallback HTTP `/decisions` si besoin)
- Soft-fail `agent_channel_unavailable` retiré (erreurs HTTP réelles seulement)

---

## 6. Bloc collable (résumé ultra-court)

```
ICHIVOL — Claude = engine agent channel (ShadowBroker pattern, pas le code OSINT)

Livrer sous /api/engine :
  GET  /agent/tools
  GET  /agent/capabilities   (stub OK)
  POST /agent/command        { cmd, args }
  POST /agent/batch          { commands[] } max 20, concurrent, order-stable

Allowlist READ v1 (wrap routes existantes, zéro LLM) :
  scan_market, get_symbol_context, detect_signal, compare_timeframes,
  run_backtest, get_correlations, calculate_ichimoku, calculate_rvol, list_tools

WRITE paper optionnel (tier full) ou skip v1.

Contrats : même payloads que /screener /decisions /backtest /correlations.
Tests + engine/README. Pas de front, pas de Copilot, pas de clone ShadowBroker.
Cursor branche le client UI en parallèle sur ce contrat.
```
