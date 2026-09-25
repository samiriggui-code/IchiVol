# IchiVol — Roadmap méthodes (verrouillée)

**Statut : VERROUILLÉ** — 2026-09-15.  
Complète : [`TRADING_ARCHITECTURE_V2.md`](./TRADING_ARCHITECTURE_V2.md) · [`MARKET-DATA-STRATEGY.md`](./MARKET-DATA-STRATEGY.md)

---

## 0. Verdict

**Validé.** On n’empile pas des indicateurs redondants. On répond à **5 questions** :

```
Direction → Participation → Où (Location) → Régime → Risque
```

Puis seulement → **décision**.

RSI / MACD / Stochastic / CCI : **hors cœur**. Test expérimentaux possibles, **aucun vote automatique**.

**Données :** tout le cœur ci-dessous = **gratuit** (OHLCV Binance Vision + calcul Python ; trades pour affiner ; Bybit pour OI/funding). Pas d’API « indicateur tout fait ». Détail : [`MARKET-DATA-STRATEGY.md`](./MARKET-DATA-STRATEGY.md).

---

## 1. Cinq questions = cinq rôles

```
                         ICHIVOL
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
    STRUCTURE          PARTICIPATION          RÉGIME
        │                   │                   │
    Ichimoku               RVOL               ATR
    Price Action           CVD*               ADX*
    MTF                     OI*                Wyckoff*
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                            ▼
                      MARKET LOCATION
                            │
                     VWAP / AVWAP
                     Volume Profile
                     S/R
                            │
                            ▼
                     SETUP QUALITY → DECISION
                            │
                ┌───────────┼───────────┐
                ▼           ▼           ▼
              BUY         WATCH       NO TRADE
```

\* V2+

| Rôle | Question | Méthodes | Droit |
|------|----------|----------|-------|
| 🧠 **Direction / Structure** | Où va la structure ? | Ichimoku, Price Action, MTF | Direction LONG/SHORT/NEUTRAL ; MTF/PA invalident ou qualifient |
| 💰 **Participation** | Le mouvement est-il participé ? | RVOL ; CVD/OI/Funding (V2) | Activer / WATCH ; jamais changer la direction seule |
| 📍 **Location** | Où est le prix vs zones réelles ? | Volume Profile, VWAP/AVWAP, S/R | Bon / mauvais emplacement |
| 🌡️ **Régime** | Quel comportement de marché ? | ATR ; Wyckoff/ADX/Donchian (V2–V3) | Tradable / mort / extrême / accumulation… |
| 🎯 **Risque** | Quelle taille / stop / cible ? | ATR (+ caps paper) | Sizing ; jamais direction |

---

## 2. Catalogue méthodes

| Méthode | Question | Rôle | Priorité | Data | Gratuit |
|---------|----------|------|----------|------|---------|
| **Ichimoku** | Où va la structure ? | Socle direction | **CORE** | OHLCV | ✅ |
| **RVOL** | Mouvement participé ? | Confirmation | **CORE** | OHLCV | ✅ |
| **Price Action / Market Structure** | Que fait le prix ? (HH/HL, BOS, CHoCH, retest…) | Structure | **CORE** | OHLCV | ✅ |
| **MTF** | Cohérent avec TF supérieurs ? | Contexte | **CORE** | OHLCV multi-TF | ✅ |
| **ATR / Vol regime** | Tradable maintenant ? Stop/size ? | Régime + risque | **CORE** | OHLCV | ✅ |
| **Volume Profile** (POC/VAH/VAL/HVN/LVN) | Où le marché a traité ? | Location | **CORE+** | OHLCV approx → trades fin | ✅/⚠️ |
| **VWAP / Anchored VWAP** | Prix vs moyenne pondérée volume ? | Location | **CORE+** | OHLCV | ✅ |
| **CVD / Volume Delta** | Qui pousse (achat/vente) ? | Participation avancée | **V2** | Trades | ✅ |
| **OI + Funding** | Que font les dérivés ? | Contexte crypto | **V2** | Futures public | ✅ |
| **Wyckoff** | Accum / distrib / spring… ? | Régime comportemental | **V3** | OHLCV (+VP) | ✅ (logique maison) |
| **Donchian / Breakout** | Vraie cassure de range ? | Détection | **V3** | OHLCV | ✅ |
| **ADX** | Force de tendance ? | Filtre régime | **V3/test** | OHLCV | ✅ — garder seulement si backtest prouve un edge |
| **Cycle / Spectral** (FFT · Hilbert · ACF) | Où sommes-nous dans le cycle ? Phase / horizon / stabilité ? | Contexte TEMPS | **V3/test** | OHLCV | ✅ — observe-only ; **jamais** vote LONG/SHORT ([`CYCLE_ENGINE_AUDIT.md`](./CYCLE_ENGINE_AUDIT.md)) |

**Hors cœur (pas de vote) :** RSI, MACD, Stochastic, CCI, EMA soup. Cycle/FFT tant que non promu.

---

## 3. Exemples (pourquoi ce n’est pas une salade)

| Setup | Lecture IchiVol |
|-------|-----------------|
| Ichi LONG + RVOL 2.1× + prix sous résistance H4 | LONG confirmé participation, **mauvais emplacement** → WATCH / réduire |
| Ichi LONG + RVOL 2.3× + breakout PA + prix > VAH | **Excellente** config location |
| Ichi LONG + RVOL 2.1× + prix dans gros HVN | Congestion → prudence |
| Ichi LONG + structure bull + prix < AVWAP | Attendre reclaim AVWAP |
| Alignement D1/H4/H1 bull + M15 RVOL 2.4 | Setup plein TF |
| D1/H4 bear + H1 bull + RVOL 2.8 | Contre-tendance / rebond — **pas** un BUY naïf |
| RVOL 2.5 + CVD ↓ | Participation ambiguë (V2) |
| Prix↑ RVOL↑ OI↑ vs Prix↑ RVOL↑ OI↓ | Pas le même trade (V2) |

---

## 4. Roadmap d’implémentation

### V1 — maintenant (OHLCV only, gratuit)

```
ICHIMOKU + RVOL + PRICE ACTION + MTF + ATR
→ Decision Engine (étages)
```

Ordre de code :

1. Pipeline à étages (remplace `confidence = a * b`)
2. `structure_agent` (HH/HL, S/R, BOS basique)
3. MTF bias
4. `volatility_agent` (ATR régime + hints stop/size)

### V1.5 — Location

```
+ VOLUME PROFILE (OHLCV d’abord, trades ensuite)
+ VWAP / ANCHORED VWAP
```

### V2 — Participation crypto avancée

```
+ CVD / Delta (trades)
+ OPEN INTEREST + FUNDING
```

### V3 — Expérimental (backtest obligatoire avant vote)

```
+ WYCKOFF (régime narratif borné)
+ DONCHIAN
+ ADX (garder ou jeter selon métriques)
+ CYCLE / SPECTRAL (FFT·Hilbert·ACF — observe only until backtest)
```

---

## 5. Trois premiers ajouts (après Ichi×RVOL)

1. **Price Action / Market Structure**  
2. **Volume Profile** (V1.5)  
3. **VWAP / Anchored VWAP** (V1.5)  

Puis **CVD + OI/Funding** pour la couche crypto.

---

## 6. Règles

1. Une méthode = **une question** ; pas de double vote directionnel.  
2. Location peut **downgrader** un signal (mauvais emplacement) sans inverser LONG→SHORT toute seule sauf invalidation structure claire.  
3. ATR / ADX / Wyckoff / **Cycle** ne votent **jamais** LONG/SHORT.  
4. Tout calcul indicateur = **Python local** sur données brutes.  
5. Pas d’abonnement data pour V1–V2 crypto spot+futures publics.  
6. Market data ≠ execution ([`MARKET-DATA-STRATEGY.md`](./MARKET-DATA-STRATEGY.md)).
