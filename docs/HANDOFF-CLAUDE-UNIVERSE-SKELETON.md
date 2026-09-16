# Handoff Claude — Squelette univers + MarketData neutre (binôme Cursor)

> **Pour :** Claude Code (moteur Python `ichivol-app/engine/`)  
> **De :** Cursor + décision produit utilisateur (2026-09-15 ~19h)  
> **Priorité :** lire **après** [`HANDOFF-CLAUDE-REALIGN-NORTHSTAR.md`](./HANDOFF-CLAUDE-REALIGN-NORTHSTAR.md) (north star soir — obligatoire)  
> **Parent :** [`HANDOFF-AGENT-CONCEPT.md`](./HANDOFF-AGENT-CONCEPT.md) · [`TRADING_ARCHITECTURE_V2.md`](./TRADING_ARCHITECTURE_V2.md) · [`MARKET-DATA-STRATEGY.md`](./MARKET-DATA-STRATEGY.md)

---

## 0. Contexte produit (figé avec l’utilisateur)

L’utilisateur **ne veut pas** que le produit soit « une app Binance ».  
Il veut **sa** app / **son** moteur Ichimoku×RVOL, univers entier, **indépendant d’une marque**.

Réalité technique acceptée :
- Les prix viennent toujours d’**adaptateurs** remplaçables.
- Binance = **un** adaptateur crypto **market-data-only** (`data-api.binance.vision`), **pas** le centre du produit ni le broker.
- On construit **d’abord le squelette** (contrat + univers), providers ensuite.
- Décision / 5 questions / roadmap méthodes : voir REALIGN + `METHODS-ROADMAP.md` (cette mission univers **ne** change **pas** le combiner).

Décision de découpage binôme :

| Qui | Zone | Ne pas toucher |
|-----|------|----------------|
| **Claude** | `ichivol-app/engine/` — universe, market_data provider, routes engine, tests Python | Front React (`src/`), sauf si demandé |
| **Cursor** | Front / Settings / docs produit / coordination | Ne pas finir le squelette engine en parallèle (collision) |

---

## 1. Déjà amorcé par Cursor (à reprendre / compléter)

Fichier créé :

```
ichivol-app/engine/app/universe/types.py
```

Contient `AssetClass` + `Instrument` (`id`, `asset_class`, `label`, `provider`, `provider_symbol`, `enabled`, `quote`, `is_wired`).

**Manque encore** (ta mission) :

```
engine/app/universe/__init__.py
engine/app/universe/catalog.py          # UNIVERSE multi-classes
engine/app/market_data/provider.py      # Protocol / ABC
engine/app/market_data/registry.py      # get_provider(id)
# Adapter : wrapper autour de binance.py existant (ne casse pas fetch_klines)
GET /api/engine/universe                # liste classes + instruments + wired?
```

---

## 2. Objectif de cette mission (Done when)

1. **Univers squelette** multi-classes dans le moteur :
   - `crypto` — instruments câblés via provider `binance` (watchlist actuelle BTCUSDT… → ids canoniques du type `BTC-USD` **ou** garder `BTCUSDT` en id pour compat, mais documente le choix)
   - `forex` — EURUSD, GBPUSD, USDJPY, … **provider=None**
   - `metal` — XAUUSD, XAGUSD, … **provider=None**
   - `index` — SPX, NDX, … **provider=None**
   - `equity` — quelques placeholders AAPL/TSLA, **provider=None**
   - `energy` — optionnel placeholder

2. **Contrat `MarketDataProvider`** :
   ```python
   def fetch_ohlcv(self, provider_symbol: str, timeframe: str, limit: int) -> list[Candle]:
       ...
   ```
   Binance implémente ce contrat. `fetch_klines` peut rester comme façade pour ne pas casser les tests existants.

   **Prévoir dans le contrat / métadonnées** (même si Binance ne remplit que `exchange`) — voir [`MARKET-DATA-STRATEGY.md`](./MARKET-DATA-STRATEGY.md) §5b :
   - `volume_type`: `exchange | tick | reported | none`
   - `source`: id provider (`binance_vision`, plus tard `twelve_data`)
   Ne bloque pas le Done de cette mission si tu stockes ça en metadata dict ; l’important = ne pas oublier le champ pour RVOL multi-classes.

3. **Screener** :
   - Watchlist par défaut = instruments `enabled` **et** `is_wired`
   - Résolution symbole : accepter encore `BTCUSDT` (compat API front actuelle) **et** `instrument.id` si tu introduis des ids canoniques
   - Si `provider is None` → erreur claire `provider_not_wired`, pas de crash obscur

4. **Route** `GET /api/engine/universe` :
   ```json
   {
     "classes": ["crypto", "forex", ...],
     "instruments": [
       {
         "id": "...",
         "asset_class": "forex",
         "label": "EUR/USD",
         "provider": null,
         "provider_symbol": null,
         "wired": false,
         "enabled": true
       }
     ]
   }
   ```

5. **Tests** : suite existante verte ; ajouter tests unitaires catalog + provider registry (sans réseau). Ne pas exiger de vrai feed forex.

6. **README engine** : 5–10 lignes « Univers / MarketData neutre » + lien vers ce handoff.

---

## 3. Règles dures

- **Ne pas** brancher un vrai provider forex/actions dans cette mission (pas d’API key Polygon/OANDA ici).
- **Ne pas** fusionner StrategyAgents avec le Copilot LLM ([`HANDOFF-AGENT-CONCEPT.md`](./HANDOFF-AGENT-CONCEPT.md)).
- **Ne pas** refactorer le front `MarketPage` / `src/lib/markets.ts` — Cursor le fera **après** que `/universe` existe.
- **Ne pas** casser : `GET /screener`, `GET /decisions/{symbol}`, `GET /backtest/{symbol}`, persistence, cache screener.
- Compat : le front Décisions envoie encore des symboles type `BTCUSDT` — garde ça vivant.

---

## 4. Ordre de travail suggéré

1. Fix / finalize `universe/types.py` si besoin  
2. `catalog.py` + helpers `get_instrument`, `wired_instruments`, `by_class`  
3. `MarketDataProvider` + `BinanceSpotProvider` + registry  
4. Brancher `screener/service.py` (et idéalement `backtest/experiments.py` + `cli.py`) via registry  
5. Route `/universe`  
6. Tests + `pytest` vert  
7. Court update `engine/README.md`

---

## 5. Après ta mission (Cursor + Phase 1b)

Quand `/api/engine/universe` répond :

1. Cursor aligne le front Marché sur l’univers **moteur** (afficher « non câblé »).
2. **Provider #1 multi-actifs = Twelve Data** (décision figée dans [`MARKET-DATA-STRATEGY.md`](./MARKET-DATA-STRATEGY.md) §5) — Claude ou Cursor branche `twelve_data.py` **après** squelette + clé API user.
3. EODHD = benchmark historique parallèle, pas le premier câblage.
4. Ne pas toucher Ichimoku/RVOL pour ajouter un provider.

**Hors scope de TA mission actuelle** : implémenter Twelve Data (pas de clé dans le squelette).

---

## 6. Prompt de démarrage (à coller dans Claude Code)

```
Lis docs/HANDOFF-CLAUDE-UNIVERSE-SKELETON.md en entier, puis docs/HANDOFF-AGENT-CONCEPT.md §1–2.

Mission : squelette univers multi-classes + MarketDataProvider neutre dans ichivol-app/engine/.
Binance = seul adaptateur câblé. Forex/métaux/indices/actions = placeholders provider=None.
Ne touche pas au front React. Garde screener/decisions/backtest compatibles BTCUSDT.
Done when : GET /api/engine/universe OK, pytest vert, README engine mis à jour.
```

---

*Handoff binôme — source de vérité pour cette mission engine. Si conflit avec une ancienne note « tout est Binance », ce document gagne.*
