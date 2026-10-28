# Ève × TradingAgents — audit (2026-10-28)

> Dépôt étudié : [`TauricResearch/TradingAgents`](https://github.com/TauricResearch/TradingAgents), commit `c454491`
> (2026-10-27), Apache 2.0. Lecture seule, aucun code exécuté.
> Doctrine inchangée : **ne pas importer TradingAgents ni le débat bull/bear**
> ([`HANDOFF-CURSOR-SESSION-2026-09-16-SOIR.md`](./HANDOFF-CURSOR-SESSION-2026-09-16-SOIR.md) §5,
> [`PLAN-INTEGRATE-EXPLAIN-COMPETENCIES.md`](./PLAN-INTEGRATE-EXPLAIN-COMPETENCIES.md) §6).
> Cet audit ne liste que des idées à reprendre dans le code d'Ève.

---

## Ce qu'est TradingAgents

| Aspect | Constat | Réf. (dans `tradingagents/`) |
|---|---|---|
| Graphe | 4 analystes en parallèle (Market, Sentiment, News, Fundamentals) → Bull ↔ Bear → Research Manager → Trader → débat risque (Aggressive / Conservative / Neutral) → Portfolio Manager | `graph/setup.py:109-187` |
| Arrêt des débats | compteur : `2 × max_debate_rounds`, `3 × max_risk_discuss_rounds` (1 par défaut) | `graph/conditional_logic.py:11-33` |
| Décision | Pydantic : note 5 niveaux (Buy / Overweight / Hold / Underweight / Sell), Trader Buy/Hold/Sell + entrée, stop, taille | `agents/schemas.py:66-258` |
| Repli | sortie structurée, sinon regex « Rating: X » ; illisible ou contradictoire → **`REVIEW`**, jamais Hold par défaut | `agents/structured.py:52-95`, `agents/rating.py:30,115` |
| Données | yfinance par défaut + Alpha Vantage, SEC, FRED, Polymarket, Reddit, StockTwits ; indicateurs `stockstats` (SMA, EMA, MACD, RSI, Bollinger, ATR, VWMA, MFI) | `dataflows/router.py:97-150`, `dataflows/vendors/yahoo/market.py` |
| Crypto | `BTCUSDT` → `BTC-USD` Yahoo, journalier seulement ; pas d'Ichimoku, pas de RVOL, pas de funding / OI | `dataflows/symbols.py:82-132` |
| Anti look-ahead | toute date demandée par le LLM ramenée à la date de décision (`as_of`) ; « pas de donnée » ≠ « fenêtre non observée » ; OHLCV filtré `<= as_of` | `dataflows/date_window.py` |
| Mémoire | journal append-only : décision « pending » → réglée à N jours (rendement + alpha vs benchmark) → leçon de 2-4 phrases → réinjectée au PM (5 dernières du même actif + 3 d'autres), filtrée point-in-time | `memory/log.py`, `memory/settlement.py`, `memory/reflection.py` |
| Coût | ~15-25 appels LLM séquentiels par décision (quick pour analystes / débats, deep pour Research Manager et PM) | `default_config.py`, `graph/setup.py:125-140` |
| Backtest | grille ticker × date, score par note (taux de bonne direction, alpha moyen) ; pas d'ordres, pas de portefeuille ; reconnu non reproductible | `backtest.py:9-14,122-126` |

## Correspondance avec Ève

| TradingAgents | Ève |
|---|---|
| Analystes | `run_analyst` + snapshot moteur (`eve/context.py`) |
| Bear Researcher | `run_challenger` |
| Débat risque | `run_guardian` + Risk Kernel |
| Portfolio Manager | `synthesize_action` (ordre des règles validé le 2026-10-27) |
| Journal mémoire | `eve/dossier.py` + `eve/followup.py` + `eve/calibration.py` |

Ève couvre déjà le circuit, avec des règles en code et beaucoup moins d'appels LLM.

## À récupérer

| Idée | Cible IchiVol | Prio |
|---|---|---|
| Sentinelle **`REVIEW`** : réponse JEV illisible ou contradictoire ≠ abstention volontaire. Aujourd'hui les deux finissent en `ABSTAIN` (`no_answer`) | `eve/modes.py` `synthesize_action` + `eve/actions.py` + badge panel | P1 |
| Vérifier que `as_of` couvre **toutes** les sources lues par Ève en rejeu (event radar, contexte, evidence) ; distinguer « fenêtre non observée » de « vide » | `eve/context.py`, `eve/event_radar.py`, `evidence/catalog.py` | P1 |
| **Leçons courtes** tirées des dossiers clos (2-4 phrases), réinjectées dans le contexte d'Ève, filtrées point-in-time ; observe-only au début | `eve/followup.py` → nouveau `eve/lessons.py` | P2 |
| Symbole imposé par l'état (le LLM ne choisit pas l'actif) + plafond de tours d'outils | canal agent (`app/agent_channel`) | P2 |
| Score par action (bonne direction %, alpha vs BTC) sur les dossiers réglés | `eve/calibration.py` | P3 |

## Pas

- Débats multi-tours bull/bear ou risque (texte concaténé, contexte qui explose, ~20 appels par décision).
- LLM appelé sur chaque paire du screener : le réserver aux candidats déjà passés par les portes.
- Indicateurs `stockstats`, benchmark SPY, règlement en jours de bourse (crypto = 24/7, benchmark BTC).
- Filtrage sentiment par service tiers (`agents/post_screen.py`).
- Dépendance Python au paquet : inspiration seulement, notice Apache 2.0 si un extrait est repris.
