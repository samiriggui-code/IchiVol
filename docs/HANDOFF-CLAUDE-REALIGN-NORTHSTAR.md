# HANDOFF CLAUDE — STOP / RÉALIGNER (north star 2026-09-15 soir)

> **Pour :** Claude Code (toute session `engine/` ou agents)  
> **De :** Cursor + utilisateur  
> **Priorité : LIRE EN PREMIER** — tu as commencé avant ces décisions ; une partie de ton plan / code peut être **obsolète**  
> **Ne continue pas** Consensus / Edge / multi-indicateurs / combiner `a * b` comme vérité produit

---

## 0. Ce qui a changé pendant que tu bossais

L’utilisateur a **verrouillé** l’identité IchiVol avec Cursor. Les docs suivantes **remplacent** l’ancienne lecture de `TRADING_ARCHITECTURE_V2.md` (consensus trop tôt, salade d’agents) :

| Doc | Contenu | Action |
|-----|---------|--------|
| [`TRADING_ARCHITECTURE_V2.md`](./TRADING_ARCHITECTURE_V2.md) | **Réécrit** — 5 questions, pipeline à portes | Relire en entier |
| [`METHODS-ROADMAP.md`](./METHODS-ROADMAP.md) | **Nouveau** — méthodes CORE / V1.5 / V2 / V3 | Relire |
| [`MARKET-DATA-STRATEGY.md`](./MARKET-DATA-STRATEGY.md) | Data ≠ execution ; Vision crypto ; **Phase 1b = Twelve Data** multi-actifs | Relire §5–5b |
| [`APP-ARBORESCENCE-V2.md`](./APP-ARBORESCENCE-V2.md) | **Nouveau** — pages V2 + rôle LLM | Relire si tu touches UI/API décisions |
| [`HANDOFF-AGENT-CONCEPT.md`](./HANDOFF-AGENT-CONCEPT.md) | Mis à jour (pipeline, pas combiner ×) | Relire §1–2 |
| [`HANDOFF-CLAUDE-UNIVERSE-SKELETON.md`](./HANDOFF-CLAUDE-UNIVERSE-SKELETON.md) | Univers + MarketData neutre | **Toujours valide** — continue si c’était ta mission |

---

## 1. Phrases fondatrices (à coller en tête de session)

> Ichimoku trouve la direction, RVOL exige la participation, la location dit si l’emplacement est bon, ATR mesure le régime/risque — le reste confirme ou invalide, **jamais** ne dilue en salade de votes.

> **Binance Vision = feed market-data-only** ([FAQ officielle](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md)). IchiVol **n’est pas** une plateforme de trading Binance. Execution = adapter séparé (paper d’abord, venue au choix plus tard).

---

## 2. Ce que tu DOIS arrêter / ne pas démarrer

| Stop | Pourquoi |
|------|----------|
| Traiter `confidence = ichimoku * rvol` comme la règle produit | MVP only → pipeline à **portes** |
| Consensus Engine / Edge / Kelly / live broker Binance | Trop tôt ; après backtest V1 |
| RSI / MACD / Stoch / CCI en StrategyAgents avec vote | Hors cœur IchiVol |
| API payante « indicateurs ready » | Python calcule sur OHLCV brut |
| Brancher ordres / User Data Stream Binance | Market data ≠ execution |
| Multi-personas LLM dans `engine/` | Copilot = TS `server/` seulement |
| Momentum agent avant Structure + ATR | Roadmap : PA/MTF/ATR d’abord |

---

## 3. Ce que tu PEUX / DOIS faire (ordre)

### Si ta mission en cours = univers / MarketDataProvider
→ **Continue** [`HANDOFF-CLAUDE-UNIVERSE-SKELETON.md`](./HANDOFF-CLAUDE-UNIVERSE-SKELETON.md).  
C’est aligné (adapter neutre, Binance = un provider, pas la marque produit).

### Ensuite (V1 moteur décision) — ne pas mélanger avec l’univers si collision
1. Remplacer / faire évoluer `decision/combiner.py` → **pipeline à étages**  
   `Direction → Participation → Structure/MTF → Régime/Risque → BUY|SELL|WATCH|NO_TRADE`  
2. `structure_agent` (HH/HL, S/R, BOS basique) + MTF  
3. `volatility_agent` (ATR régime + hints stop/size — **pas** de vote LONG/SHORT)  
4. Garder Ichimoku = seule source de **direction** ; RVOL = porte participation  

### Plus tard (pas maintenant)
- V1.5 : Volume Profile + VWAP/AVWAP  
- V2 : CVD + OI/Funding  
- V3 : Wyckoff / Donchian / ADX (test backtest)

Détail : [`METHODS-ROADMAP.md`](./METHODS-ROADMAP.md).

---

## 4. Carte mentale produit (pour caler ton code)

```
MarketDataAdapter (Vision / Bybit…)  ≠  ExecutionAdapter (Paper → ???)
                 │
                 ▼
          DATA ENGINE (Python calcule Ichi, RVOL, PA, ATR…)
                 │
                 ▼
     DECISION : Direction → Participation → Location → Régime → Risque
                 │
                 ▼
          BUY | WATCH | NO_TRADE
```

LLM Copilot = **hors** ce pipeline (explique seulement).

---

## 5. Checklist avant ton prochain commit engine

- [ ] J’ai relu `TRADING_ARCHITECTURE_V2.md` + `METHODS-ROADMAP.md` + `MARKET-DATA-STRATEGY.md`  
- [ ] Je ne code pas un ConsensusEngine  
- [ ] Je ne traite pas Binance comme broker  
- [ ] Si je touche `combiner.py` : je documente « MVP → pipeline » ou j’implémente les portes  
- [ ] Nouveaux agents : Structure / ATR seulement en V1 (pas RSI)  
- [ ] Tests existants encore verts  

---

## 6. Message court à coller dans Claude

```
STOP — realign. L’utilisateur a verrouillé la north star avec Cursor ce soir.

Lis dans l’ordre :
1. docs/HANDOFF-CLAUDE-REALIGN-NORTHSTAR.md  (ce fichier)
2. docs/TRADING_ARCHITECTURE_V2.md
3. docs/METHODS-ROADMAP.md
4. docs/MARKET-DATA-STRATEGY.md

Règles : pipeline à portes (pas ichi*rvol comme vérité) ;
5 questions Direction→Participation→Location→Régime→Risque ;
V1 = Ichi+RVOL+PA+MTF+ATR ; pas de consensus/RSI/broker Binance ;
data = data-api.binance.vision only ; execution séparée (paper).

Si tu étais sur universe/MarketDataProvider : continue HANDOFF-CLAUDE-UNIVERSE-SKELETON.md.
Sinon : ne démarre pas Edge/Consensus ; aligne le combiner ensuite.
Quand tu exposeras le pipeline natif : docs/HANDOFF-CLAUDE-PIPELINE-UI.md (le front est déjà prêt).
```

---

## 7. Binôme Cursor

| Cursor (cette session) | Claude |
|------------------------|--------|
| Docs north star, arborescence, data strategy, méthodes | Engine Python (univers / pipeline / agents) |
| Front si demandé | Ne pas réécrire le front sauf demandé |

Collision : si tu modifies `combiner.py` / nouveaux agents, dis-le à l’user ; Cursor ne double pas le même fichier en parallèle.
