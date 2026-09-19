# Handoff Claude — Mise à niveau IchiVol × MetaTrader 5 (VPS)

> **Pour :** Claude (conclure + planifier la mise à niveau ; engine / bridge en priorité)  
> **De :** Cursor (session 2026-09-19)  
> **Date :** 2026-09-19  
> **Owner produit :** Samir  
> **Live :** https://ichivol.global-it-ss.com · smoke `http://187.77.166.124:3060` · repo `/opt/ichivol` sur VPS Hostinger id `1722028`

---

## 0. Mission (ce que tu dois faire)

1. **Lire** ce handoff + les refs §9 (ne pas tout relire le monorepo).  
2. **Conclure** une mise à niveau IchiVol face à MT5 déjà prévu / installable sur le VPS.  
3. **Rendre** un verdict écrit : option choisie (A/B/C ci-dessous), critères d’admission, plan en STEPS, STOP avant exécution live.  
4. **Ne pas** brancher d’ordres réels. **Ne pas** mettre `MT5_MODE=LIVE`. **Ne pas** exposer VNC/MT5 en port public.

Si une info VPS manque (credentials, Wine bootstrap), **vérifier sur le VPS** avant de coder, puis documenter le constat.

---

## 1. Décisions produit déjà figées (ne pas rouvrir)

| Règle | Source |
|-------|--------|
| Ichimoku × RVOL = cœur décisionnel Python | Architecture V2 |
| PaperBroker 5 000 € / profil, baseline `ICHIVOL_BASELINE_V1` **jamais écrasé** | Phases 1–5 |
| Lab (event study / WF / opt) **avant** promotion live | Strategy Lab |
| ShadowBroker = counterfactuel **hors cash** | Phase 5 livrée |
| MCP / TradingView = **viz**, pas un vote Decision Engine | V2 §13 |
| **MCP MT5 / exécution** = **post-validation** uniquement | V2 §11 rule 11 |
| Market data ≠ execution | V2 |
| Volume MT5 CFD = **tick** par défaut (jamais mélanger silencieux avec Binance real volume dans RVOL) | `volume_semantics.py` |
| Bridge MT5 = service **séparé** (Wine), profile Docker `mt5`, caps CPU/RAM durs | `docker-compose.yml` + `mt5-bridge/README.md` |

---

## 2. État IchiVol aujourd’hui (fait)

### 2.1 Grand V2 — briques livrées

| Phase | Contenu | Statut |
|-------|---------|--------|
| 1 | PaperBroker · risk 1% · TP 2R · freeze baseline | Déployé VPS |
| 2 | Market Structure (MVPP / trendln / consensus) · profils `STRUCTURE_*` | Déployé |
| 3 | Context RSI / CMF / OBV / régime | Déployé |
| 4 | FibonacciContext · `ICHIVOL_MS_FIB` | Déployé |
| 5 | ShadowBroker · table `shadow_positions` · `/shadow/stats` | Déployé 2026-09-19 |
| ∥ | Strategy Lab Phases 1–8 (event study → walk-forward-opt) | Déployé |
| ∥ | Evidence Engine + Signal Evidence Card + paper propose→confirm | Mergé `main` (Cloud) |
| ∥ | GPTHEIST AnalysisStage (lab contract) | Mergé `main` (Cloud) |
| ∥ | Landing Grand V2 | Déployé |

### 2.2 Stack runtime VPS (constat Cursor 2026-09-19)

```
ichivol-postgres · ichivol-engine · ichivol-server · ichivol-web (:3060 / Traefik FQDN)
```

- Projet Docker compose : `/opt/ichivol/docker-compose.yml`  
- **Container `ichivol-mt5-bridge` : NON listé dans `docker ps`** au moment du handoff (profile `mt5` pas démarré, ou credentials manquants).  
- Code bridge présent dans le repo : `ichivol-app/mt5-bridge/`  
- Engine déjà sur réseau `mt5_bridge` + env `MT5_ENABLED` / `MT5_BRIDGE_URL` (défaut `false`).  
- **Owner affirme MT5 installé sur le VPS** — à **vérifier** (Wine volume `ichivol_mt5_wine`, process terminal, ou install hors Docker). Ne pas assumer « bridge healthy » sans `/health` → `connected: true`.

### 2.3 Ce qui existe déjà dans le code (ne pas réinventer)

| Pièce | Path | Rôle |
|-------|------|------|
| Client engine READ | `engine/app/market_data/mt5.py` | HTTP → bridge |
| Registry opt-in | `engine/app/market_data/registry.py` | `MT5_ENABLED=true` |
| Config | `engine/app/config.py` | `mt5_mode`: `READ_ONLY` \| `PAPER` \| `DEMO` — **pas LIVE** |
| Bridge FastAPI | `mt5-bridge/bridge_server.py` | OHLCV + health, **pas d’ordres** |
| Symbol map | `mt5-bridge/symbol_map.py` | alias broker |
| Compose profile | `docker-compose.yml` service `mt5-bridge` | `profiles: ['mt5']`, mem 3g, cpus 1.5 |
| Secrets template | `deploy/vps/.env.example` | `MT5_LOGIN/PASSWORD/SERVER` |
| Tests unit client | `engine/tests/market_data/test_mt5.py` | mock, pas live |

Doc opérationnelle bridge : [`ichivol-app/mt5-bridge/README.md`](../ichivol-app/mt5-bridge/README.md).

---

## 3. Contexte externe — page MetaTrader Algo (lecture Cursor)

Source : https://www.metatrader.com/fr/algotrading (hub articles FR MetaQuotes, 2026).

### 3.1 Ce que MetaQuotes pousse maintenant

- **Python + MT5** comme flux recherche → test → exécution  
- **Algo Forge** (Git) pour collab MQL5  
- Perf : OpenCL / DirectX / symboles custom (Renko, Range…)  
- Journal SQLite, Calendrier économique MQL5 API  
- Narrative plateforme : **ONNX, OpenBLAS, IA agentique, Model Context Protocol (MCP)** branchés sur terminal / MetaEditor / marché / trading

### 3.2 Implications pour IchiVol (à trancher)

| Signal MetaQuotes | Implications IchiVol |
|-------------------|----------------------|
| MCP dans MT5 | Ne pas dupliquer un « LLM qui trade dans MT5 ». IchiVol garde **Decision Engine Python** ; MT5 = rail data (puis exécution démo plus tard). |
| Python research / MT5 exec | Aligné avec notre split Lab/Paper vs live. Renforcer **provider MT5 READ** pour FX/métaux (vs biquote plafond ~100 barres). |
| Algo Forge / MQL5 EAs | **Hors cœur IchiVol**. Companion MQL optionnel plus tard — pas un remplacement du Lab. |
| Volume tick CFD | Déjà anticipé (`VolumeType.TICK_VOLUME`) — **bloquer** toute fusion RVOL cross-provider sans tag. |

---

## 4. Options de mise à niveau (tu choisis + justifies)

### Option A — **MT5 Data Lab (recommandé comme next)**

**But :** allumer le bridge READ_ONLY, valider OHLCV FX/métaux/indices via MT5 démo, brancher catalogue instruments `provider=mt5` **sans** toucher baseline crypto Binance.

- Steps typiques : credentials démo → `--profile mt5 up` → checklist README → `MT5_ENABLED=true` → CLI smoke → 2–3 instruments wired → tests volume_type  
- **Hors scope :** ordres, MCP server MT5, MQL5 EAs  
- **Critère done :** `get_provider("mt5")` OK ; `/health connected:true` ; XAUUSD + EURUSD 1h limit≥200 ; volume_type explicite dans payload

### Option B — **MT5 + Evidence / Paper shadow parity**

Comme A, **plus** : journaliser `provider=mt5` dans Evidence / décisions ; permettre propose→confirm paper sur symboles MT5 (cash paper only).

- **Critère done :** A + une décision Evidence avec source MT5 + paper intent sur symbole MT5 sans ordre broker

### Option C — **MCP MT5 / exécution démo** (trop tôt sauf preuve écrite)

Écrire `app/execution/mt5_demo.py` + routes place/close **DEMO only**.

- **Bloqué** tant que : Paper + Shadow + Lab OOS n’ont pas de critère d’admission chiffré vs baseline  
- Si tu proposes C, tu dois d’abord lister les **gates de preuve** (n trades, expectancy, DD) — sinon refuse C

### Option D — **Companion MQL5 / Algo Forge** (parallèle, bas priorité)

Indicateur Pine/MQL miroir Ichimoku×RVOL pour chart humain — **n’alimente pas** le Decision Engine.

---

## 5. Contraintes VPS (non négociables)

1. VPS **multi-clients** (gsms, pizzeria, grace, qatrial, n8n, traefik…) — Wine/MT5 **ne doit pas** les affamer (`mem_limit: 3g`, `cpus: 1.5` déjà dans compose).  
2. Réseau `ichivol_mt5_bridge` **isolé** — jamais mélangé aux autres projets.  
3. **Aucun** port public VNC / MT5. Tunnel SSH seulement.  
4. Secrets uniquement dans `/opt/ichivol/deploy/vps/.env` (jamais git).  
5. Deploy pattern connu : tar/scp préservant `.env` **ou** git pull + `docker compose --env-file deploy/vps/.env …` — ne pas écraser `.env`.  
6. Profile : `docker compose --env-file deploy/vps/.env --profile mt5 up -d --build mt5-bridge`

---

## 6. Livrable attendu de Claude (format de réponse)

Réponds dans cet ordre :

### A. Verdict

Une phrase : **Option X** (+ sous-option si besoin).

### B. Pourquoi pas les autres

2–4 lignes.

### C. Plan STEPS (implémentation)

Numéroté, chaque step = fichiers touchés + test + critère done.  
Inclure **STEP 0 = audit VPS** (bridge running? wine volume? env MT5_* présents sans logger les secrets?).

### D. Risques

Wine bootstrap fragile, broker alias symboles, tick vs real volume, charge VPS.

### E. STOP

Liste explicite de ce que tu **ne** feras pas dans ce chantier (LIVE orders, MCP serveur MT5 full, remplacer Binance, etc.).

---

## 7. Questions ouvertes pour l’owner (si bloquant)

1. Compte MT5 : **démo quel broker / serveur** ? (nom serveur exact pour `MT5_SERVER`)  
2. MT5 « installé » = container Wine IchiVol, ou install Windows/Wine **hors** `/opt/ichivol` ?  
3. Priorité données : XAUUSD / FX majeurs / indices — lesquels d’abord ?  
4. Faut-il que Claude **implémente** Option A tout de suite après le verdict, ou **STOP au plan** seulement ?

*(Si non répondu : assume Option A, STOP au plan + STEP 0 audit VPS, puis attendre « ok vas-y » pour coder.)*

---

## 8. Anti-patterns (refus)

- Brancher MT5 comme **seul** provider marché  
- Utiliser volume tick MT5 dans les mêmes buckets RVOL que Binance sans `volume_type`  
- Ordres live « pour tester »  
- MCP qui laisse un LLM appeler `order_send`  
- Cloner des EAs MQL5 du Market Store dans le Decision Engine  
- Lancer `mt5-bridge` sans caps mémoire / sur le réseau `ichivol` public Traefik

---

## 9. Refs à lire (ordre)

1. Ce fichier  
2. [`ichivol-app/mt5-bridge/README.md`](../ichivol-app/mt5-bridge/README.md)  
3. [`docs/ARCHITECTURE-CONSOLIDEE-V2.md`](./ARCHITECTURE-CONSOLIDEE-V2.md) §9 Shadow · §13 MCP · §14 phases  
4. [`docs/TRADING_ARCHITECTURE_V2.md`](./TRADING_ARCHITECTURE_V2.md) rule 11  
5. [`docs/MARKET-DATA-STRATEGY.md`](./MARKET-DATA-STRATEGY.md) (biquote vs profondeur)  
6. [`docs/EVIDENCE-ARCHITECTURE.md`](./EVIDENCE-ARCHITECTURE.md) (si Option B)  
7. Code : `engine/app/market_data/mt5.py` · `registry.py` · `volume_semantics.py` · `mt5-bridge/bridge_server.py`  
8. Contexte éditorial (optionnel) : https://www.metatrader.com/fr/algotrading  

---

## 10. Snapshot git / déploiement (contexte)

- `main` GitHub aligné post-merge Cloud (Evidence + GPTHEIST + ShadowBroker) au moment du handoff.  
- Bug récent corrigé : `walk-forward-opt` unpackait mal `resolve_and_fetch` (tuple n=3) — ne pas réintroduire.  
- Deploy IchiVol historique : rebuild `engine`/`web` après extract tar préservant `.env`.

---

**Fin du handoff.**  
Claude : conclus la mise à niveau (§6), puis STOP ou attends confirmation owner pour exécuter STEP 0+.
