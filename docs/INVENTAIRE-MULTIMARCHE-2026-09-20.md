# Inventaire multimarché — sources gratuites et manques pour un forward test

**Auteur :** ichivol-36 · **Date :** 2026-09-20 · **Nature :** inventaire uniquement — aucun achat, aucun appel réseau nouveau (je m'appuie sur `V3-VERIFICATION-DONNEES-2026-09-20.md`, qui contient les tests réels, et sur la lecture du code). Légende : **T** testé (dans V3), **C** lu dans le code du repo, **D** documentation/déclaré non testé, **?** non vérifié.

## 1. Ce que le repo câble déjà (C)

Catalogue `app/universe/catalog.py` : 30 instruments, dont **10 hors crypto**.

| Classe | Instruments | Fournisseur | Notes |
|---|---|---|---|
| Forex | EURUSD, GBPUSD, USDJPY | biquote | plafond **101 barres** par appel (T) ; volume = nombre de ticks ; pas de bid/ask (T) ; conditions d'utilisation **?** |
| Métaux | XAUUSD, XAGUSD | biquote | idem |
| Indices | SPX (US500), NDX (USTEC) | biquote | idem ; SPX refusé par Twelve Data gratuit (T : plan Grow) |
| Énergie | WTI (USOIL) | biquote | idem |
| Actions | AAPL, TSLA | Twelve Data | 8 crédits/min, 800/jour (T) ; volume déclaré (place/consolidé **?**) |
| Crypto | 20 paires | Binance | seul fournisseur avec bid/ask (T), volume réel |

Le moteur possède déjà : un accumulateur pour les fournisseurs plafonnés (`market_data/accumulator.py`, biquote seulement), la sémantique de volume par fournisseur (`volume_semantics.py`), l'exécution `candle_only` avec friction configurée, et des jambes multi-devises dans le grand livre (mais **le broker est mono-devise** : USDT traité comme EUR).

## 2. Sources gratuites — état

| Source | Couverture utile | Historique | Volume | Bid/ask | Droits (V3) | Verdict pour un forward test |
|---|---|---|---|---|---|---|
| **Twelve Data gratuit** | forex, or spot, actions US, crypto | T : EUR/USD 1j depuis 2005, 1 min depuis 2021 ; 5 000 barres/requête | forex/or : **aucun** ; actions : oui | **non** (T) | usage personnel non commercial ; stockage prolongé interdit ; « non-display » à clarifier | Utilisable pour forex, XAU, actions US **si** le calcul serveur relève de l'usage interne ; indices refusés ; quota strict (§4) |
| **biquote** | forex, métaux, indices, WTI | **101 barres** seulement ; accumulation locale nécessaire | tick volume | **non** | **?** conditions non relues | Secours / test court ; ne suffit pas pour un backfill |
| **OANDA practice** | forex, métaux, indices CFD | D : depuis 2005 | tick | **D : oui** | D : usage interne + systèmes automatisés autorisés sur démo ; stockage **?** | Seul candidat gratuit avec bid/ask ; **jeton API démo pour la division EU non confirmé** |
| Dukascopy | ticks bid/ask historiques | T (fichiers accessibles) | — | oui | **exclu** : stockage en base et robots interdits | À ne pas utiliser dans un pipeline automatique |
| TradingView MCP | multi | D | ? | non | **exclu** : usage « non-display » interdit | Bloqué sans autorisation écrite |
| Autres (Stooq, Yahoo, Alpha Vantage, ECB/FRED) | — | **non vérifiés par moi** | — | — | **?** | À évaluer (conditions d'usage d'abord), rien affirmé ici |

## 3. Manques pour un forward test multimarché (par ordre de blocage)

1. **Droits d'usage non tranchés** : la réponse TradingView (question déjà rédigée dans V3, à envoyer par l'utilisateur), la clarification « non-display » de Twelve Data et les conditions de biquote/OANDA conditionnent ce qui peut être calculé et stocké. Sans elles, seul Binance est propre.
2. **Aucune donnée d'exécution réaliste hors crypto** : pas de bid/ask gratuit vérifié (seul OANDA le promet, non confirmé). Il faudra un **barème de spread par instrument déclaré comme hypothèse** (comme pour la crypto, `REVUE-SIM-ET-COUTS…`), plus swap/financement pour les CFD, taille de contrat et pas minimal.
3. **Calendrier de marché absent** : le garde de péremption (`screener/timing.py`) calcule le retard en barres depuis l'horloge (`expected = now − now % tf`) sans calendrier. Sur forex/métaux/indices (fermés le week-end, jours fériés, pauses quotidiennes) le retard dépasse **`STALE_LAG_BARS = 2` à chaque fermeture** : tous les signaux seraient déclarés périmés hors séance. Il faut un calendrier par instrument (sessions, jours fériés, heure d'été) avant tout test, et adapter aussi `closed_candles` et les fenêtres d'indicateurs (ATR, RVOL, alignement 4H) aux trous de séance.
4. **Volume inexistant pour forex/métaux** : `volume_type = NONE` ou TICK. Le stade « participation » ne bloque que sur `FAIL` (RVOL « LOW »), jamais sur `WATCH` (`decision/pipeline.py`) ; ce que fait `rvol_agent` sur un volume nul n'est **pas vérifié ici** — à tester. Le cœur Ichimoku × RVOL ne se transpose pas tel quel : décider ce qui remplace le RVOL (tick volume ? rien ?) **avant** de mesurer, et le déclarer.
5. **Historique à constituer** : aucun cache hors crypto dans `research_lab/cache`. Backfill Twelve Data possible (5 000 barres/requête : ≈ 41 semaines de forex 1 h par requête) mais chaque symbole × chaque timeframe coûte des crédits ; l'accumulateur n'existe que pour biquote.
6. **Devises** : le broker suppose USDT = EUR. Forex/indices/actions cotés en USD/JPY exigent une conversion du P&L et de la taille (le grand livre sait poster `CONVERSION`, pas le broker) ; les actions ont en plus splits/dividendes et identifiants de place (piège `CL` = Colgate, V3).
7. **Biais de sélection** : indices/actions → composition point-in-time, survivorship ; crypto déjà partiellement traitée dans `universe.py`.

## 4. Arithmétique de quota (Twelve Data gratuit : 8 crédits/min, 800/jour)

Un cycle complet pour N instruments avec 1 h + 4 h coûte ≈ **2N crédits**. Pour N = 10 : 20 crédits par barre 1 h → **480 crédits/jour** si l'on ne synchronise qu'**aux clôtures de barres** (24 cycles), dans les 800/jour mais avec 7 crédits/min ≈ 3 min d'étalement par cycle. Une synchronisation toutes les 5 minutes (comportement du paper crypto) donnerait 288 cycles × 20 = 5 760 crédits/jour, **7 fois le quota** : les instruments non crypto doivent être synchronisés à la clôture des barres uniquement (et le cache de 90 s ne suffit pas).

## 5. Ce qui est faisable tout de suite, sans achat ni décision de licence
- Test **de mécanique** (pas de résultat économique) : forex EURUSD + XAUUSD via Twelve Data gratuit, 1 h, cycles à la clôture, pour vérifier calendrier/péremption/volume nul/devise avant de parler de P&L.
- Rédiger la table de sessions (heures d'ouverture, jours fériés) et le barème de spread hypothétique par instrument, marqués « hypothèse ».
- Préparer l'envoi de la question TradingView et de deux clarifications (Twelve Data, OANDA) : **à faire par l'utilisateur**.

## 6. Ce qu'il ne faut pas faire
Aucun achat de plan Twelve Data (grille de prix instable, écart 29 $ / 79 $ signalé dans V3), aucun usage de Dukascopy ni de TradingView dans un pipeline automatique, aucune conclusion de performance multimarché avant les points 1 à 4.
