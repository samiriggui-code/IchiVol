# IchiVol Engine

Service Python (FastAPI) : Ichimoku, RVOL, agents, Decision Engine, screener multi-actifs, collecteur OHLCV. Base Postgres dédiée `ichivol_engine_dev`, séparée de `ichivol_dev` (server/).

## Setup (une fois)

```bash
cd ichivol-app/engine
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # Windows
# .venv/bin/pip install -r requirements.txt     # macOS/Linux

cp .env.example .env
# Créer la base si elle n'existe pas :
#   psql -h 127.0.0.1 -U postgres -c "CREATE DATABASE ichivol_engine_dev;"

.venv/Scripts/python -m alembic upgrade head
```

## Lancer le service

```bash
cd ichivol-app/engine
.venv/Scripts/python -m uvicorn app.main:app --port 8000 --reload
```

Le serveur Express (`ichivol-app/server`) proxy `/api/engine/*` vers `http://127.0.0.1:8000/api/engine/*` (voir `server/src/engine/proxy.ts`, configurable via `ENGINE_URL` dans `server/.env`). Le moteur doit tourner sur le port 8000 pour que la page `/app/decisions` du front fonctionne.

## Tests

```bash
.venv/Scripts/python -m pytest tests -v
```

~100 tests : indicateurs (anti-lookahead prouvé par troncature), agents, combineur de décision, pipeline à étages, structure/ATR, univers/provider/resolve, collecteur, screener, backtest, routes API. Certains tests réseau/DB se skip automatiquement si Binance ou `ichivol_engine_dev` sont injoignables.

## Univers / MarketData neutre

Voir [`docs/HANDOFF-CLAUDE-UNIVERSE-SKELETON.md`](../../docs/HANDOFF-CLAUDE-UNIVERSE-SKELETON.md) et [`docs/MARKET-DATA-STRATEGY.md`](../../docs/MARKET-DATA-STRATEGY.md). Le produit n'est pas "une app Binance" : `app/universe/catalog.py` liste l'univers complet (crypto/forex/metal/index/equity/energy), Binance n'étant qu'un des adaptateurs (`app/market_data/provider.py` = contrat `MarketDataProvider`, `app/market_data/registry.py` = table id→instance). **Tout le catalogue est câblé aujourd'hui** : crypto → `binance` (Binance Vision), actions (AAPL/TSLA) → `twelve_data` (volume d'échange réel), et FX/métaux/indices/énergie → `biquote` (gratuit, sans clé, voir `app/market_data/biquote.py`). `app/market_data/resolve.py` fait le pont : un symbole catalogué résout vers son provider fixe ; un symbole inconnu du catalogue retombe sur l'ancien comportement (Binance par défaut), pour ne rien casser côté `BTCUSDT`/tests existants. Un instrument sans provider (aucun aujourd'hui, mais le mécanisme reste actif pour un futur ajout) répond `provider_not_wired` si on essaie de le scanner — pas de crash, une erreur claire. `fetch_klines` (dans `binance.py`) reste la façade unique patchée par les tests, que l'appel passe par `scan_symbol`, `experiments.compare` ou `BinanceSpotProvider`.

### Accumulation d'historique (biquote)

Testé en live (2026-09-16) : biquote plafonne **chaque appel à ~100 bougies**, quoi qu'on demande — `/backtest/EURUSD?limit=1000` ne recevait silencieusement que 99 bougies utilisables, sans aucun signal dans la réponse. `app/market_data/accumulator.py` corrige ça : chaque appel via un provider hard-cappé (aujourd'hui, seulement `biquote` — `needs_accumulation()`) persiste ses bougies **clôturées** dans la DB de l'engine (`app/market_data/collector.py`, la même table que le CLI manuel `app/market_data/cli.py` utilise déjà) puis recombine l'historique accumulé avec la lecture live la plus fraîche. `resolve_and_fetch()` (dans `resolve.py`) est le point d'entrée unique — `scan_symbol`, `experiments.compare` et `/ohlcv/{symbol}` passent tous par là au lieu d'appeler `provider.fetch_ohlcv()` directement.

Deux règles importantes, testées (`tests/market_data/test_accumulator.py`) :
- **La dernière bougie renvoyée par un appel live n'est jamais persistée** : c'est presque toujours la bougie en cours de formation, et la contrainte d'unicité `(asset_id, timeframe, timestamp)` fait qu'une ligne insérée n'est jamais mise à jour plus tard (`ON CONFLICT DO NOTHING`) — la persister une fois figerait sa valeur incomplète pour toujours.
- **La profondeur grandit avec le temps, pas d'un coup** : le premier appel sur un instrument encore jamais vu ne récupère toujours que la fenêtre live (~100 bougies) — l'historique DB est vide au départ. C'est en rappelant le même instrument au fil du temps (screener en tâche de fond, requêtes répétées) que l'historique dépasse 100 bougies, biquote livrant à chaque fois une fenêtre plus récente qui vient s'empiler sur ce qui est déjà stocké.

binance/twelve_data ne passent pas par cette accumulation (`needs_accumulation()` renvoie `False`) : ils servent déjà toute la profondeur demandée en un appel, l'ajouter serait un aller-retour DB inutile sur un chemin déjà sollicité (le screener scanne 20+ symboles toutes les 5 minutes).

## Strategy Lab — Event Study (Phase 1)

Couche recherche **au-dessus** du pipeline existant — pas un remplacement.

- Module : `app/strategy_lab/event_study.py`
- HTTP : `GET /api/engine/event-study/{symbol}?variant=PIPELINE&horizons=1,3,5,10&r_multiple=1`
- Agent channel : `run_event_study`
- UI : section sur `/app/backtests` (lancée avec le comparatif)

Pour chaque entrée d’une variante (`ICHIMOKU_ONLY` … `PIPELINE`), mesure les retours ATR-normalisés à +N bougies, MFE/MAE, et le % touchant +R avant −R. **Pas** de capital, fees, ni sizing. Convention d’entrée alignée sur le backtest (open de la barre suivante).

`experiments.prepare_variants()` factorise le fetch OHLCV + séries de positions pour backtest et event study.

### Rules Engine (Phase 2)

- Schema : `app/strategy_lab/ruleset.py` (conditions AND, clés allowlistées)
- Features causales : `features.py` (Ichimoku / RVOL / structure / ATR / CMF / RSI)
- Évaluateur rising-edge : `evaluator.py`
- Catalog built-in : `catalog.py` (`IV_ICHIMOKU_RVOL_LONG_001`, ablation Ichimoku seul, +BOS, kumo breakout)
- Run : `run_ruleset.py` → Event Study **+** ATR SL/TP backtest (`ruleset_backtest.py`)
- HTTP : `GET /rulesets`, `GET /ruleset/{id}/event-study?symbol=…`, `POST /ruleset/event-study`
- Agent : `list_rulesets`, `run_ruleset_event_study`

Backtest ruleset (Phase 3) : entrée next open, stop/target en multiples d’ATR, une position à la fois, stop prioritaire si les deux niveaux sont touchés dans la même barre. Réutilise `compute_metrics`.

### Performance DB (Phase 4)

- Table : `strategy_lab_experiments` (migration `b2c3d4e5f6a7`)
- Module : `app/strategy_lab/perf_db.py`
- Persist : `?persist=true` sur `/ruleset/.../event-study` ou `POST` body `persist`
- List / get / compare : `GET /strategy-lab/experiments`, `.../{id}`, `/strategy-lab/compare?ruleset_ids=A,B`

### Ablation (Phase 5)

- Module : `app/strategy_lab/ablation.py`
- Escalier défaut : A Ichimoku → B +RVOL → C +BOS → D +ATR expansion → E +CMF
- Modes : `cumulative` | `leave_one_out`
- HTTP : `GET/POST /strategy-lab/ablation`
- Deltas entre étapes : expectancy / PF / signaux — un filtre doit prouver son utilité

### Market Regime slices (Phase 6)

- Classifier : `regime.py` (ADX → TRENDING/RANGING, ATR → HI/LO/NORMAL VOL, +DI/−DI → BULL/BEAR/SIDEWAYS)
- Run : `regime_slices.py` — GLOBAL + slices orthogonales sur les mêmes signaux
- HTTP : `GET/POST /strategy-lab/regime-slices`
- Persist : `market_regime` dans Performance DB

### Walk-forward (Phase 7)

- Module : `walk_forward.py` — folds rolling | expanding sur un **ruleset fixe** (pas d'optimizer — Phase 8)
- Features calculées une fois (causales) ; signaux filtrés par plage d'indices IS/OOS
- Résumé OOS : mean expectancy / PF / Sharpe, % folds PF>1, total trades OOS
- HTTP : `GET/POST /strategy-lab/walk-forward`
- Agent : `run_walk_forward`
- Persist optionnel : tags `walk_forward` + `fold` / `split` (IS|OOS) dans Performance DB

### Optimization (Phase 8)

- Module : `optimization.py` — grid-search sur knobs numériques du ruleset (`rvol_min`, `tk_cross_age_max`, `stop_atr`, `target_atr`…)
- Cap : 96 combinaisons max ; knobs absents du ruleset de base ignorés
- Objectifs : `expectancy` | `profit_factor` | `sharpe` (min_trades gate)
- `GET/POST /strategy-lab/optimize` — fenêtre unique (IS only, diagnostic)
- `GET/POST /strategy-lab/walk-forward-opt` — **chemin principal** : best params sur IS → mesure OOS par fold + `param_stability`
- Agent : `run_optimize` · `run_walk_forward_opt`

## Pipeline à étages (north star, docs/HANDOFF-CLAUDE-REALIGN-NORTHSTAR.md)

`confidence = ichimoku × rvol` (`app/decision/combiner.py`) est un **raccourci MVP**, pas la règle produit verrouillée — voir docs/TRADING_ARCHITECTURE_V2.md. La cible : `app/decision/pipeline.py`, un pipeline à 5 portes qui ne fait jamais dire l'inverse à une étape suivante (elle ne peut que rétrograder vers WATCH/NO_TRADE, jamais inverser LONG↔SHORT) :

1. **Direction** — `ICHIMOKU_AGENT` (LONG/SHORT/NEUTRAL).
2. **Participation** — `RVOL_AGENT` (gate : pass/watch/fail, ne vote jamais la direction). Enrichi (V2, jamais de vote, ne change jamais le statut) par CVD (`app/indicators/cvd.py`) et OI/Funding (`app/indicators/oi_funding.py`) — voir section dédiée plus bas.
3. **Structure/MTF** — `app/indicators/structure.py` (swings HH/HL/LH/LL, cassure de structure/BOS, anti-lookahead prouvé) + alignement avec le timeframe supérieur (15m→1h→4h→1d, calculé dans `screener/service.py::_mtf_direction`).
4. **Location** — `app/indicators/location.py` (V1.5, livré) : Volume Profile approximé sur OHLCV (POC/VAH/VAL par histogramme roulant, HVN/LVN relatifs au volume moyen du bin), VWAP roulant, et VWAP ancré qui se réinitialise à chaque cassure de structure confirmée (`structure.bos`). Ne vote jamais LONG/SHORT : qualifie seulement l'emplacement (congestion HVN, mauvais côté de la value area ou de l'AVWAP → `fail`, rétrograde vers WATCH — jamais d'inversion de direction).
5. **Régime/Risque** — `app/indicators/atr.py` (ATR + percentile historique → régime DEAD/NORMAL/EXTREME, jamais de vote directionnel, juste un stop suggéré). Enrichi puis **gate actif** (V3, promu le 2026-09-16 — voir section ADX plus bas) par `app/indicators/adx.py` : régime NORMAL mais tendance non confirmée (ADX absent/en développement) → `fail` → NO_TRADE, jamais un vote de direction.

Label final : `BUY|SELL|WATCH|NO_TRADE`. Exposé de façon **additive** sous la clé `pipeline`, dans `/decisions/{symbol}` ET dans chaque ligne de `/screener` (forme identique à `ichivol-app/src/lib/decisionPipeline.ts::NativePipelinePayload`, satisfait la dépendance "API screener enrichie (status par stage)" de CDC-VIZ-001) — le champ `decision` de premier niveau reste partout celui du combiner legacy pour ne rien casser côté front tant que Cursor n'a pas basculé dessus.

Le pipeline est aussi branché sur le backtest : `app/backtest/experiments.py` a une 4e variante `PIPELINE` (voir plus bas), avec un alignement MTF causal dédié (`_align_mtf_directions`, basé sur les timestamps de clôture des bougies, pas sur un fetch séquentiel — testé par troncature comme le reste) et la Location incluse dans chaque décision simulée. CVD est aussi inclus dans le backtest (calculé sur les mêmes bougies) ; OI/Funding ne le sont **pas encore** (branchés seulement sur le screener/décisions live pour l'instant — nécessitent leur propre fenêtre d'historique alignée, pas fait dans cette passe).

### CVD + OI/Funding (V2 "participation avancée", docs/METHODS-ROADMAP.md)

Enrichissent la porte Participation, jamais un vote, jamais un changement de statut pass/fail/watch — RVOL reste le seul déclencheur du gate (règle produit explicite).

- **CVD** (`app/indicators/cvd.py`) — delta = `2 * taker_buy_volume - volume`, calculé à partir d'un champ déjà présent dans la réponse kline Binance (`app/market_data/binance.py`, index 9 — "taker buy base asset volume") : **zéro appel réseau supplémentaire**, contrairement à une vraie récupération de trades bruts. `None`/`UNKNOWN` partout ailleurs que Binance spot (Twelve Data, biquote n'ont pas ce champ). Codes : `cvd_buy_pressure` / `cvd_sell_pressure` / `cvd_balanced`.
- **OI + Funding** (`app/indicators/oi_funding.py`, `app/market_data/binance_futures.py`) — API futures publique Binance (`fapi.binance.com`, sans clé, données de marché uniquement — mission "data ≠ execution"). OI : tendance relative à l'historique propre de l'instrument (RISING/FALLING/FLAT, même logique que ATR/RVOL). Funding : lu directement (déjà un pourcentage normalisé), seuil `±0.05%/8h` pour "crowded long/short". Alignement causal des deux séries sur chaque bougie (comme MTF) — jamais une valeur future. Codes : `oi_rising` / `oi_falling`, `funding_crowded_long` / `funding_crowded_short`.

**Piège trouvé en live (2026-09-16)** : tous les tickers spot n'ont pas un ticker futures identique — `PEPEUSDT` renvoie un tableau vide `200 OK` (pas une erreur) sur les deux endpoints futures ; le vrai ticker est `1000PEPEUSDT`. `_FUTURES_SYMBOL` dans `binance_futures.py` mappe les exceptions connues ; tout le reste est supposé identique au ticker spot et revient simplement vide si cette hypothèse est fausse pour un futur listing (jamais une erreur pour "pas de marché futures pour ce token").

Uniquement pour les symboles câblés sur `binance` (crypto spot) — forex/métaux/actions n'ont pas ce concept. Best-effort : toute erreur réseau ou symbole sans marché futures dégrade gracieusement vers `None`/pending, jamais un crash (même convention que MTF).

### ADX (V3 expérimental, promu en gate actif le 2026-09-16)

`app/indicators/adx.py` — formule Wilder standard (+DI/-DI/DX/ADX, lissage récursif causal), sur OHLCV seul, aucune dépendance réseau. Question "Régime" comme ATR : ne vote jamais LONG/SHORT (règle explicite `docs/METHODS-ROADMAP.md` §6 : "ATR/ADX/Wyckoff ne votent jamais").

Le CDC posait une règle claire pour l'ADX : **"garder seulement si backtest prouve un edge"**. Testé honnêtement sur 3 fenêtres réelles (BTCUSDT 1h/4h, ETHUSDT 1h) en filtrant les entrées PIPELINE sur `ADX ≥ TRENDING` (rejette ABSENT/DEVELOPING) :

| Run | PIPELINE (sans ADX) | PIPELINE + filtre ADX |
|---|---|---|
| BTCUSDT 1h | Sharpe -1.43, dd 11.6% | Sharpe **-0.28**, dd **9.4%** |
| ETHUSDT 1h | Sharpe -9.02, dd 19.8% | Sharpe **-4.76**, dd **9.2%** |
| BTCUSDT 4h | Sharpe -4.84, dd 25.9% | Sharpe **-4.64**, dd **18.9%** |

Amélioration du Sharpe et du drawdown **dans les 3 tests, sans exception** — un edge réel, pas du bruit. Verdict : **edge prouvé, ADX promu en gate actif** dans `app/decision/pipeline.py::_regime_stage`. Concrètement : régime ATR normal mais ADX `ABSENT`/`DEVELOPING` (pas de tendance confirmée) → `fail` → `NO_TRADE`, exactement comme ATR mort/extrême. `TRENDING`/`STRONG` ou ADX absent (historique insuffisant) → aucun effet. Ne change toujours jamais la direction, seulement rétrograde.

Important : ça ne change pas le verdict sur la migration Option C (`docs/CAHIER-DES-CHARGES.md` §4) — même amélioré, `PIPELINE` ne bat toujours pas Ichimoku seul dans l'absolu sur ces 3 fenêtres. C'est un vrai gain pour la qualité interne du pipeline, pas (encore) de quoi renverser la comparaison globale.

`app/backtest/experiments.py` n'a plus de variante séparée `PIPELINE_ADX_FILTER` : depuis que le gate est actif dans `build_pipeline`, la variante `PIPELINE` seule reflète déjà l'ADX — une expérience séparée aurait juste produit les mêmes chiffres.

### Donchian (V3, promu en gate actif le 2026-09-16) + Wyckoff (V3 expérimental, pas promu)

Même règle CDC que l'ADX (`docs/CAHIER-DES-CHARGES.md` : "Wyckoff / Donchian — backtest avant tout droit de vote"), même méthodologie de départ (3 fenêtres réelles, `PIPELINE` avec/sans le filtre) — verdicts différents pour les deux.

**Donchian** (`app/indicators/donchian.py`) — canal turtle-trading classique (plus haut/plus bas des `period=20` bougies **précédentes**, jamais la bougie testée elle-même). Premier passage, filtre backtest seul : ne garde une position `PIPELINE` que si Donchian confirme une vraie cassure de range dans le même sens (`UP` pour LONG, `DOWN` pour SHORT), sinon `NEUTRAL` — réévalué à chaque bougie, même logique de gate continu que le régime ADX.

| Run | PIPELINE (sans filtre) | PIPELINE + filtre Donchian |
|---|---|---|
| BTCUSDT 1h | Sharpe -0.39, dd 9.6%, 45 trades | Sharpe **1.95**, dd **3.9%**, 17 trades |
| ETHUSDT 1h | Sharpe -5.29, dd 9.8%, 32 trades | Sharpe **-1.50**, dd **3.3%**, 9 trades |
| BTCUSDT 4h | Sharpe -4.64, dd 18.9%, 37 trades | Sharpe -4.93 (légèrement pire), dd **8.2%**, 13 trades |

Drawdown amélioré **dans les 3 fenêtres, souvent de moitié ou plus**. Sharpe amélioré sur 2/3 (nettement sur BTCUSDT 1h), très légèrement pire sur BTCUSDT 4h (écart dans le bruit, les deux restent très négatifs) — pas le "3/3 sans exception" d'ADX à la lettre, mais un signal jugé suffisant par décision produit explicite (2026-09-16) pour promouvoir Donchian dans `app/decision/pipeline.py::_regime_stage`, au même titre qu'ADX : régime ATR normal mais Donchian ne confirme pas de vraie cassure dans le sens de la direction Ichimoku → `fail` → `NO_TRADE`, jamais un vote de direction. `app/backtest/experiments.py` n'a plus de variante séparée `PIPELINE_DONCHIAN_FILTER` (même sort que `PIPELINE_ADX_FILTER`) : `PIPELINE` reflète déjà le gate. Sweep élargi (plus de symboles/timeframes) lancé le 2026-09-16 pour vérifier si ça change le verdict Option C — voir section dédiée plus bas.

**Wyckoff** (`app/indicators/wyckoff.py`, "logique maison" explicite — voir docstring du module) — détecte seulement les deux patterns Wyckoff les plus littéraux : SPRING (fausse cassure sous le support du canal Donchian, réabsorbée dans la même bougie, sur volume climax ≥1.5× la moyenne) et UPTHRUST (miroir, fausse cassure au-dessus). `PIPELINE_WYCKOFF_FILTER` neutralise une position `PIPELINE` seulement quand un test Wyckoff actif la contredit directement (LONG pendant un UPTHRUST, SHORT pendant un SPRING). **Reste non promu** — verdict inchangé, voir tableau ci-dessous.

| Run | PIPELINE (sans filtre) | PIPELINE + filtre Wyckoff |
|---|---|---|
| BTCUSDT 1h | Sharpe -0.39, dd 9.6% | Sharpe **0.21**, dd 8.8% |
| ETHUSDT 1h | Sharpe -5.29, dd 9.8% | Sharpe -7.17 (pire), dd 11.0% (pire) |
| BTCUSDT 4h | Sharpe -4.64, dd 18.9% | Sharpe -5.24 (pire), dd 20.4% (pire) |

Nombre de trades quasi inchangé sur les 3 runs (45→44, 32→31, 37→37) — attendu : SPRING/UPTHRUST sont des événements rares, une seule bougie à la fois, donc le filtre touche très peu de trades. Là où il agit, il fait plus de mal que de bien sur 2 fenêtres sur 3. **Pas d'edge démontré, pas promu.** Documenté comme tel plutôt que supprimé silencieusement — la logique reste disponible (`PIPELINE_WYCKOFF_FILTER`) si quelqu'un veut la retester avec un seuil de volume climax différent ou un univers de fenêtres plus large, mais rien ne justifie de lui donner un droit de vote ou même un rôle de filtre aujourd'hui.

### Sweep élargi post-promotion Donchian (2026-09-16) — verdict Option C toujours pas changé

Les 3 fenêtres initiales (BTCUSDT/ETHUSDT) ne suffisaient pas pour juger si `PIPELINE` (maintenant avec le gate Donchian) change la comparaison face à Ichimoku seul (`docs/CAHIER-DES-CHARGES.md` §4, migration Option C). Sweep élargi à **12 symboles crypto × 2 timeframes (1h/4h) = 24 runs**, seuils par défaut, `limit=1000` :

| Métrique | Résultat |
|---|---|
| Sharpe : `PIPELINE` bat `ICHIMOKU_ONLY` | **11/24** (46%) — quasiment pile ou face, pas un edge |
| Drawdown max : `PIPELINE` < `ICHIMOKU_ONLY` | **24/24, sans exception** — moyenne 30.1% → **5.1%** (~6×) |

Verdict honnête et net : **le gate Donchian ne fait pas gagner à `PIPELINE` un edge de rendement sur Ichimoku seul** (Sharpe toujours pas prouvé, conforme à tous les tests précédents) — **mais il réduit le drawdown de façon écrasante et sans une seule exception sur 24 fenêtres**, bien au-delà de ce qu'avait montré ADX seul. `PIPELINE` reste un profil "beaucoup moins de trades, beaucoup moins de risque, rendement pas meilleur" plutôt qu'un edge de rendement pur. **Conclusion Option C inchangée : toujours pas justifiée** — mais l'argument produit pour `PIPELINE` (moteur de gestion du risque, pas générateur d'edge) est maintenant *beaucoup* plus solide qu'avant Donchian, sur un échantillon 8× plus large que les tests précédents.

### Synthetic Market Lab (V3, livré 2026-09-16)

`app/synthetic/` — un laboratoire de marché fabriqué, pour tester si le pipeline interprète correctement une configuration *connue à l'avance*, avant de lui faire confiance sur du bruit réel. Trois modules :

- `generator.py` — `generate_market(regime, params)` fabrique une série `Candle` déterministe (seed contrôlable, même seed ⇒ sortie identique) pour un régime nommé. Le générateur ne connaît rien d'Ichimoku/RVOL/pipeline, seulement prix + volume.
- `scenarios.py` — 5 scénarios catalogués : `bullish_trend`, `bearish_trend`, `false_breakout`, `low_volume_bullish`, `range_market`. Chacun associe les candles à un `GroundTruth` (contexte attendu, fenêtre d'évaluation, décisions acceptables/interdites) que le pipeline ne reçoit jamais.
- `validation.py` — `run_pipeline_over_candles()` rejoue **exactement** les mêmes fonctions que `screener/service.py::scan_symbol` (Ichimoku/RVOL/Structure/ATR/Location/ADX → `build_pipeline`), moins le fetch réseau et les enrichissements qui ne gatent jamais de toute façon (CVD/OI-Funding/MTF — les omettre ne change rien à la décision testée). `validate_scenario()` compare la décision dominante de la fenêtre d'évaluation au ground truth ; `run_lab()` fait tourner les 5 ; `format_report()` produit un rapport lisible.

14 tests verts (`tests/synthetic/`). Calibrer les 5 scénarios a directement mis en évidence deux pièges réels, gardés en commentaire dans `generator.py` :

1. **Bruit trop grand par rapport à la tendance** : un premier essai de `bullish_trend` avec un drift faible et un bruit gaussien plus grand produisait de vrais retournements locaux (Tenkan<Kijun, structure BEARISH) en cours de route — le moteur avait raison de les détecter, c'est le scénario qui n'était pas assez "propre" pour tester ce qu'il prétendait tester.
2. **Décroissance de volume trop douce, ou clampée par un plancher** : `low_volume_bullish` doit maintenir un ratio RVOL structurellement bas (`v_i / avg_i` constant pour une décroissance géométrique pure) ; un taux trop faible (0.985) ne suffit pas à passer sous `RvolParams.low_threshold` (0.7), et un plancher de volume trop haut (1.0) casse la décroissance géométrique en cours de scénario et laisse RVOL se ré-équilibrer vers NORMAL — même piège que celui déjà documenté dans `tests/backtest/test_experiments.py::_uptrend_with_flat_low_volume`.
3. **Effet de bord ATR découvert au passage** : `app/indicators/atr.py` classe le régime par percentile de l'ATR **absolu** sur son propre historique (pas ATR/prix) — un prix qui compound fortement sur des centaines de barres peut dériver vers `EXTREME` par la seule croissance du niveau de prix, sans vraie expansion de volatilité relative. Gardé comme limite connue documentée, pas corrigé ici (hors scope de ce chantier, nécessiterait son propre backtest avant/après pour juger si normaliser par le prix améliore réellement le régime détecté).

Pas encore fait : scénarios C (breakout confirmé), F (reversal), H (haute volatilité) du brief original : celui-ci couvre les 5 jugés les plus utiles pour les critères d'acceptation du CDC déjà en place (RVOL doit pouvoir bloquer un signal directionnel fort, une fausse cassure ne doit pas être prise pour argent comptant). Pas de matrice TP/FP/FN/TN formelle ni d'exposition API/UI — ce chantier reste engine-only pour l'instant.

## Paper trading (V2, approuvé 2026-09-16)

Positions **virtuelles uniquement** — jamais un ordre réel, jamais de broker, jamais d'argent réel (règle mission "paper avant live"). `app/paper/engine.py` ouvre/ferme des positions en lisant `pipeline.decision` dans le temps, table `paper_positions` (migration `83833177e10b`). Deux origines, mêmes règles, tables et logique partagées :

- **`auto_watchlist`** — le cycle `screener/cache.py` (toutes les 5 min) ouvre/ferme automatiquement une position pour chaque symbole du watchlist dès que `pipeline.decision` passe à `BUY`/`SELL`, en réutilisant les lignes déjà calculées (aucun appel réseau en plus). `user_id` toujours `None`.
- **`user_confirmed`** — ouverte à la demande (`POST /api/engine/paper/positions?symbol=...&user_id=...`, appelé par le serveur quand un utilisateur clique "Confirmer" dans le Journal). Idempotent : un second appel pour le même (symbole, timeframe, user_id) renvoie la position existante sans doublon.

Règle de sortie = même logique que le pipeline lui-même : une position se ferme dès que la décision live ne la soutient plus plus (`WATCH`/`NO_TRADE`, ou la direction a changé) — **jamais** inversée automatiquement dans l'autre sens, un nouveau cycle ouvrira une nouvelle position si besoin.

Routes :
```
GET  /api/engine/paper/positions?source=&user_id=&status=
POST /api/engine/paper/positions?symbol=&user_id=&timeframe=1h
POST /api/engine/paper/positions/{id}/close
```

Vérifié en live (2026-09-16) : le cycle automatique avait déjà accumulé 12 positions réelles avant même que je ne teste manuellement ; ouverture/fermeture manuelle sur NEARUSDT avec PnL réel calculé (+0.24%).

Pas fait dans cette passe : Performance/calibration (item CDC séparé, dépend de données paper accumulées dans la durée) ; pas de notification quand une position se ferme (lien naturel avec "Journal watch + notifications", §5.3 du CDC, pas construit).

### Paper multi-classe (V2, livré 2026-09-16)

`PaperPosition` n'a jamais eu de colonne exchange/provider — seulement `symbol`/`timeframe` — donc côté moteur/DB rien n'était réellement crypto-only : la seule barrière était un garde explicite dans `POST /api/engine/paper/positions` (`app/api/routes.py::open_paper_position`), posé pour respecter "paper/watch multi-classe = après paper crypto stable" (docs/HANDOFF-CLAUDE-CDC-CAP-2026-09-16.md §1.5). Le paper crypto étant stable en production depuis, ce garde est levé : `POST /api/engine/paper/positions` accepte maintenant n'importe quel symbole du catalogue (`biquote` — forex/métal/index/énergie — ou `twelve_data` — actions), avec exactement les mêmes règles d'ouverture/fermeture/idempotence que pour le crypto.

À noter : le cycle `auto_watchlist` (screener background) tournait déjà multi-classe *avant* ce changement, sans que personne ne l'ait décidé explicitement — `default_watchlist()` (app/universe/catalog.py) inclut `binance` **et** `biquote` depuis l'ajout du catalogue FX/métal/index/énergie, donc `sync_auto_watchlist` ouvrait/fermait déjà des positions sur EURUSD/XAUUSD/etc. au fil des cycles de 5 min. Seul `user_confirmed` (le clic "Confirmer" utilisateur) était bloqué. Les actions (`twelve_data`) restent hors `default_watchlist` (budget API), donc `auto_watchlist` ne les couvre toujours pas — seul `user_confirmed` (à la demande, un appel réseau par clic) les ouvre.

Front : envoyer des symboles hors Binance à `POST /api/engine/paper/positions` fonctionne dès maintenant, plus besoin d'attendre un signal moteur supplémentaire.

Pas encore fait : `volatility_agent`/`structure_agent` comme `StrategyAgentOutput` à part entière (ce sont pour l'instant des indicateurs purs consommés directement par le pipeline), seuils Location non exposés en query params (contrairement à RVOL/ATR — pas demandé par le CDC pour l'instant).

## Corrélations (V2 optionnel, livré 2026-09-16)

`CDC-VIZ-002` (docs/CAHIER-DES-CHARGES.md §6.2) : « qu'est-ce qui bouge avec BTC ? » — jamais branché sur le pipeline de décision, jamais un vote, juste une lentille en lecture seule pour Contexte/Marché (même règle "observe, ne décide jamais" que le reste). Explicitement **pas** le graphe Grace/GRC (§6.4) : simple matrice de corrélation statistique, pas de topologie "protects/monitors".

`app/correlation/engine.py::compute_correlation_matrix` — corrélation de Pearson (stdlib `statistics.correlation`, pas de numpy/pandas dans ce moteur) sur les rendements log bar-à-bar par défaut (`method=log_returns`, standard finance pour une série de prix non stationnaire), ou sur les clôtures brutes (`method=price`). Symboles alignés sur leurs timestamps **communs** (les providers ferment leurs bougies sur des horloges différentes — biquote vs Binance Vision) ; en dessous de 20 bougies communes, les symboles concernés sont rapportés dans `skipped` plutôt que de produire une corrélation calculée sur une poignée de points. Une paire où un côté a une variance nulle (série plate) renvoie `null`, pas `0.0` — une corrélation nulle et une corrélation non définie ne sont pas la même chose.

Stateless comme `/backtest` : recalculée à chaque appel sur l'historique dispo, rien de caché ni persisté.

## Routes

```
GET  /api/engine/health
GET  /api/engine/universe
GET  /api/engine/screener?timeframe=1h
GET  /api/engine/decisions/{symbol}?timeframe=1h&persist=true
POST /api/engine/decisions/batch
GET  /api/engine/backtest/{symbol}?timeframe=1h&limit=1000
GET  /api/engine/correlations?timeframe=1h&method=log_returns&symbols=
GET  /api/engine/agent/tools
GET  /api/engine/agent/capabilities
POST /api/engine/agent/command
POST /api/engine/agent/batch
GET  /api/engine/context/news?limit=20&sources=
GET  /api/engine/context/calendar?limit=20
```

`/universe` liste tout le catalogue (`classes` + `instruments`, avec `wired`/`provider` par instrument) — c'est la source de vérité pour ce que le produit couvre, pas seulement ce qui a une donnée réelle branchée aujourd'hui.

`persist=true` (par défaut) écrit `strategy_signals`/`agent_predictions`/`decisions` en base à chaque appel, pour la traçabilité (mission §9).

### `POST /decisions/batch` (V2, optionnel, livré 2026-09-16)

Variante batch de `GET /decisions/{symbol}` — flagguée optionnelle dans docs/HANDOFF-CURSOR-SESSION-2026-09-16-SOIR.md §3 ("si le poll N×1 du watch devient lent"), construite maintenant pour que `startJournalWatchJob` (server TS, `app/server/src/notifications/watch.ts`) puisse récupérer tous les symboles confirmés en un seul appel concurrent au lieu d'un `fetch` séquentiel par symbole.

```json
POST /api/engine/decisions/batch
{
  "items": [{"symbol": "BTCUSDT", "timeframe": "1h"}, {"symbol": "EURUSD", "timeframe": "1h"}],
  "persist": true
}
```

Réponse : `{"results": [...]}`, un objet par item **dans l'ordre de la requête** (pas l'ordre de complétion — le calcul tourne concurrent via `ThreadPoolExecutor`, comme `scan_watchlist`). Chaque résultat a la même forme que `GET /decisions/{symbol}` (donc `pipelineFingerprint()` côté server n'a rien à changer) plus `ok: true`, ou `ok: false` + `error` si ce symbole précis échoue — un symbole en erreur ne fait jamais échouer tout le batch. Plafonné à 60 items par requête (`422 batch_too_large` au-delà) ; pas de surcharge RVOL/ATR ni `include_candles`, contrairement à l'endpoint unitaire — un besoin de threshold custom en masse n'a pas été demandé.

Chaque ligne de `/screener` inclut aussi `pipeline` (mêmes champs que `/decisions/{symbol}`) — pas seulement `decision`/`confidence` du combiner legacy.

Depuis le 2026-09-16, chaque ligne inclut aussi `risk` (`{atr, regime, suggested_stop_distance}`, ou `null` si l'ATR n'a pas encore assez d'historique) — le pendant chiffré du texte du stage Régime, pour qu'un appelant qui veut agir sur une décision (paper trading, un futur bouton "brocker" côté front) ait un stop distance exploitable sans parser une phrase en français. Pas de sizing de position ici, juste `price` (déjà présent) + `suggested_stop_distance` (docs/HANDOFF-CURSOR-PIPELINE-NATIVE.md §14).

`POST /paper/positions` accepte désormais les 7 mêmes overrides RVOL/ATR que `/decisions` et `/screener` (parité de fonctionnalité comblée le 2026-09-16 -- manquait uniquement ici). Vérifié en live : `POST .../paper/positions?symbol=ATOMUSDT&user_id=...&rvol_significant=0.9` a réellement ouvert une position SHORT sur ATOMUSDT (`pipeline.decision` était `WATCH` avec le seuil par défaut 1.5, `SELL` avec 0.9) -- mêmes données réelles, seuil de démonstration explicite, jamais un ordre réel.

`/backtest/{symbol}` compare 4 variantes sur le même historique (`app/backtest/experiments.py`) :
- `ICHIMOKU_ONLY` — structure seule.
- `ICHIMOKU_RVOL` — RVOL revérifié à chaque bougie (peut churner).
- `ICHIMOKU_RVOL_ENTRY_GATE` — RVOL confirme seulement à l'entrée, la position tient ensuite sur la structure seule.
- `PIPELINE` — le pipeline à étages (`app/decision/pipeline.py`) : en position seulement quand son label vaut `BUY`/`SELL`, plat sur `WATCH`/`NO_TRADE`. Candidat destiné à remplacer le combiner legacy en production (docs/CAHIER-DES-CHARGES.md : "Combiner → portes comme seule vérité produit (migration)") — l'objectif de ce backtest est de vérifier s'il le devrait vraiment, pas de le supposer.

**Résultat empirique honnête (3 fenêtres réelles, aucune optimisation de paramètres, Location incluse depuis son ajout)** :

| Run | ICHIMOKU_ONLY | ICHIMOKU_RVOL | ICHIMOKU_RVOL_ENTRY_GATE | PIPELINE |
|---|---|---|---|---|
| BTCUSDT 1h (1000 bougies) | Sharpe 0.77, dd 18.5% | Sharpe -1.84 | Sharpe 0.11 | Sharpe -1.18, dd **11.6%** |
| ETHUSDT 1h (1000 bougies) | Sharpe -1.86, dd 27.5% | Sharpe -5.75 | Sharpe -2.91 | Sharpe -8.63, dd **19.1%** |
| BTCUSDT 4h (1000 bougies) | Sharpe 0.30, dd 22.1% | Sharpe -0.15 | Sharpe 0.12 | Sharpe -4.73, dd 26.2% |

## Agent command channel (READ v1, livré 2026-09-16)

`app/agent_channel/` -- un canal de commandes nommées pour un agent (Claude ou tout autre appelant programmatique), séparé du Copilot LLM (`ichivol-app/server/src/agent/`) : zéro LLM ici, zéro nouvelle logique de décision, juste un habillage uniforme `{cmd, args} -> {ok, data|error}` par-dessus des fonctions déjà existantes et déjà testées (`scan_symbol`, `scan_watchlist`, `experiments.compare`, `compute_correlation_matrix`, `compute_ichimoku`, `compute_rvol`).

```
GET  /api/engine/agent/tools                 -- introspection (identique à la commande list_tools)
GET  /api/engine/agent/capabilities          -- stub : version, read_only, write_tier_enabled, max_batch_items
POST /api/engine/agent/command  {cmd, args}  -- une commande
POST /api/engine/agent/batch    {commands}   -- jusqu'à 20, concurrent, ordre stable (même pattern que /decisions/batch)
```

Allowlist v1 (9 commandes, toutes read-only, `app/agent_channel/registry.py::TOOLS`) :

| Commande | Wrap de | Payload |
|---|---|---|
| `scan_market` | cache screener | identique à `GET /screener` |
| `get_symbol_context` | `scan_symbol` + `persist_scan` optionnel | identique à `GET /decisions/{symbol}` |
| `detect_signal` | `scan_symbol` | verdict condensé (decision/direction/stages/risk), pas le détail combiner legacy |
| `compare_timeframes` | `scan_symbol` × N timeframes | un résumé par timeframe, une erreur n'en sabote pas une autre |
| `run_backtest` | `experiments.compare` | identique à `GET /backtest/{symbol}` |
| `get_correlations` | `compute_correlation_matrix` | identique à `GET /correlations` |
| `calculate_ichimoku` | `compute_ichimoku` | état brut (tenkan/kijun/cloud/score), pas de décision |
| `calculate_rvol` | `compute_rvol` | état brut (rvol/anomaly_level/confirmed), pas de décision |
| `list_tools` | ce même registre | identique à `GET /agent/tools` |

Un `cmd` inconnu, un arg manquant/invalide, ou une erreur métier (historique insuffisant, symbole inconnu) ne renvoient jamais un 500 -- toujours `{"ok": false, "cmd": ..., "error": "..."}`, exactement comme `POST /decisions/batch` isole déjà un symbole en échec. `GET /decisions/{symbol}` persiste par défaut (`persist=true`) ; `get_symbol_context` par défaut **ne persiste pas** (`persist=false`) -- un appelant du canal de commandes est censé explorer plus librement qu'un humain qui clique dans l'UI, pas remplir l'historique d'audit à chaque sonde.

**WRITE (paper trading) explicitement hors scope de ce lot** (`write_tier_enabled: false` dans `/agent/capabilities`) -- ouvrir/fermer une position papier reste uniquement `POST /paper/positions` (app/paper/engine.py), jamais via ce canal, tant qu'une allowlist WRITE n'est pas explicitement demandée. Pas de front, pas de Copilot ici : Cursor branche son propre client sur ce contrat en parallèle.

Les helpers de sérialisation (`pipeline_dict`/`risk_dict`/`summary_dict`/`detail_dict`/`metrics_dict`/`backtest_dict`) ont été extraits de `app/api/routes.py` vers `app/api/serializers.py` pendant ce chantier, pour que les routes HTTP et le canal de commandes construisent des payloads identiques sans que l'un importe l'autre -- pas un changement de comportement, juste où vivent ces fonctions.

## Adapters contexte (V3, opt-in, livré 2026-09-16)

`app/context/` -- item CDC "Claude : adapters context (news / calendrier) opt-in, sans toucher Ichimoku×RVOL". Deux sources, toutes les deux gratuites/sans clé (même logique que biquote/CoinGecko, `docs/MARKET-DATA-STRATEGY.md`), toutes les deux **best-effort et jamais bloquantes** : une panne réseau ou un flux qui change de format dégrade vers une liste vide, jamais une exception ou un 502.

- `app/context/news.py` -- titres crypto via RSS (CoinDesk + CoinTelegraph par défaut, `news.FEEDS`), fusionnés et triés par date décroissante. Un flux en échec n'empêche pas l'autre de répondre.
- `app/context/calendar.py` -- calendrier macro de la semaine via le flux JSON communautaire ForexFactory (pas d'API officielle/clé -- accepté comme compromis pour une source de contexte opt-in, non critique).

Routes : `GET /context/news?limit=20&sources=coindesk,cointelegraph`, `GET /context/calendar?limit=20`. Commandes agent équivalentes : `get_news`, `get_calendar` (mêmes payloads, `app/agent_channel/`). **`app/decision/pipeline.py` n'importe ni l'un ni l'autre** -- aucun stage, aucun code, aucune décision n'en dépend ; c'est du contexte à lire, pas un signal à voter.

Vérifié en live (2026-09-16) contre les vrais flux : `/context/news` a renvoyé de vrais titres CoinTelegraph, `/context/calendar` de vrais événements macro (BRICS Summit, indicateurs NZD) de la semaine en cours. 11 tests dédiés (`tests/context/`).

## Collecte automatique de preuve backtest (gate broker live, 2026-09-17)

`app/backtest/evidence.py` -- job d'arrière-plan qui répond à la "condition 1" du gate broker live (`docs/CAHIER-DES-CHARGES.md` §5 V3 : "un vrai edge de rendement prouvé"). Il ne fait rien de nouveau côté calcul : il relance `experiments.compare()` (déjà utilisé par `/backtest/{symbol}` et la page Backtests) sur tout l'univers crypto × [1h, 4h], et persiste chaque métrique dans une nouvelle table `backtest_snapshots` -- pour qu'une tendance devienne visible dans le temps sans que quelqu'un relance un script à la main, exactement comme chaque chiffre des tableaux ADX/Donchian/Wyckoff de ce README a été produit manuellement ce soir.

**Ce module ne décide jamais rien** : il logue, un humain (ou moi) lit et juge si "preuve" veut dire preuve -- même principe que la promotion d'ADX/Donchian, jamais un seuil automatique qui basculerait Option C tout seul.

- Tourne dans le process FastAPI (même pattern `start()`/`stop()`/thread que `ScreenerCache`), pas de conteneur cron séparé. Intervalle par défaut 24h (`BACKTEST_EVIDENCE_INTERVAL_S`), activable/désactivable via `ENABLE_BACKTEST_EVIDENCE` (`.env`) -- **désactive-le en dev local si les reloads `--reload` répétés te gênent** : chaque redémarrage relance immédiatement un cycle complet (confirmé en live ce soir : plusieurs reloads consécutifs ont produit 865+ lignes en moins d'une heure).
- `GET /api/engine/backtest/evidence` -- rollup pour la tuile Overview "Preuve edge (C1)" : `total_rows`, `first_run_at`/`last_run_at`, `distinct_days` (durée écoulée, pas juste jours avec donnée), `latest_pairs`, et `pipeline_beats_ichimoku_sharpe: {beats, compared} | null` calculé sur le cycle le plus récent (fenêtre de 2h) uniquement. Déclarée **avant** `/backtest/{symbol}` dans le router pour que `evidence` ne soit jamais interprété comme un symbole.
- Vérifié en live : `{"total_rows": 865, "latest_pairs": 40, "pipeline_beats_ichimoku_sharpe": {"beats": 20, "compared": 40}}` -- encore une fois ~50%, cohérent avec tout ce qui a été trouvé ce soir (Donchian, Wyckoff, sweep élargi) : pas d'edge de rendement, juste une réduction de risque.
- La logique de comparaison (`_score_pipeline_vs_ichimoku`) est une fonction pure testée isolément de la DB partagée -- nécessaire car le job tourne réellement contre `ichivol_engine_dev`, donc un test qui inférerait le "cycle le plus récent" depuis une requête live serait fragile par construction (confirmé : un vrai cycle a écrit des lignes pendant l'écriture des tests eux-mêmes).
- Migration `3cae25ba04d6_add_backtest_snapshots_table`. 9 tests dédiés (`tests/backtest/test_evidence.py` + `tests/api/test_backtest_evidence_route.py`).

Construit en collaboration avec Cursor : le contrat JSON exact (`BacktestEvidenceSummary`) et la tuile Overview "Preuve edge (C1)" existaient déjà côté front avant que l'endpoint engine ne soit fini -- les deux implémentations sont arrivées presque identiques indépendamment, reconciliées en une seule (logique dans `evidence.py`, route fine dans `routes.py`).

L'hypothèse centrale de la mission ("RVOL confirme et améliore") **n'est toujours pas validée par les données sur cet échantillon** : aucune variante RVOL (continue, entry-gate, ou pipeline à portes) ne bat Ichimoku seul en Sharpe/return sur ces 3 runs. Ajouter Location a nettement réduit l'exposition de `PIPELINE` (11-14% contre 33-36% avant Location, 74-78% pour Ichimoku seul) et le max drawdown dans 2 cas sur 3 (18.5%→11.6% et 27.5%→19.1%) — la porte Location fait bien ce qu'elle est censée faire, réduire l'exposition aux mauvais emplacements — mais le Sharpe reste pire qu'Ichimoku seul partout, et pire qu'avant Location sur BTCUSDT 4h (-2.29 → -4.73). **Conclusion pour la migration "Combiner → portes" (docs/CAHIER-DES-CHARGES.md §4) : toujours pas justifiée par ces données** — l'architecture réduit le risque mais pas encore au prix d'un edge positif net.

**Recalibrage tenté (2026-09-16), toujours pas suffisant** : sur les 3 paramètres qui influencent vraiment le résultat du backtest PIPELINE (`rvol_low` — seul seuil RVOL qui déclenche un `FAIL` de la porte Participation ; `atr_dead_percentile`/`atr_extreme_percentile` — seuils qui déclenchent `NO_TRADE` via la porte Régime ; les autres seuils RVOL n'affectent que l'affichage, pas la décision finale), recherche par grille sur BTCUSDT 1h (in-sample) puis validation sur ETHUSDT 1h et BTCUSDT 4h (jamais vus pendant la recherche, pour éviter l'overfitting) :

| | ICHIMOKU_ONLY | PIPELINE (défaut) | PIPELINE (`rvol_low=1.1, atr_dead=0.20, atr_extreme=0.95`) |
|---|---|---|---|
| BTCUSDT 1h (in-sample) | — | Sharpe -1.25 | Sharpe **+1.35** |
| ETHUSDT 1h (hors échantillon) | Sharpe -1.78 | Sharpe -8.51 | Sharpe -4.96 |
| BTCUSDT 4h (hors échantillon) | Sharpe 0.22 | Sharpe -4.74 | Sharpe -3.88 |

**Mise à jour (2026-09-16, après ADX)** : `PIPELINE` inclut maintenant le gate ADX (voir section dédiée plus bas) — les chiffres `PIPELINE` ci-dessus datent d'avant cet ajout. Nouveaux chiffres (seuils RVOL/ATR toujours par défaut, pas le recalibrage ci-dessus) : Sharpe -0.28/-4.76/-4.64 sur les 3 mêmes fenêtres, drawdown nettement réduit partout. Toujours pas suffisant pour battre Ichimoku seul, mais un vrai progrès — détail dans la section ADX.

Le recalibrage améliore réellement PIPELINE par rapport à ses seuils par défaut, hors échantillon aussi (pas juste de l'overfitting) — mais **PIPELINE recalibré ne bat toujours pas Ichimoku seul** hors échantillon. **Conclusion Option C inchangée : toujours pas justifiée**, même après un effort de calibrage honnête. Ces valeurs (`rvol_low=1.1, atr_dead_percentile=0.20, atr_extreme_percentile=0.95`) sont un point de départ raisonnable à essayer via Settings (query params ci-dessous) si quelqu'un veut pousser plus loin — **pas appliquées comme nouveau défaut moteur** : ce sont des seuils Settings, pas une constante engine, et je n'ai validé leur effet que sur `PIPELINE`, pas sur le combiner legacy (`Option A`, la vérité produit actuelle) qui partage les mêmes `RvolParams`/`AtrParams`.

### Seuils RVOL/ATR configurables (item V1 CDC)

`/decisions/{symbol}`, `/screener` et `/backtest/{symbol}` acceptent tous les mêmes 7 query params optionnels pour piloter les seuils sans redéployer :

```
rvol_low, rvol_significant, rvol_strong, rvol_anomaly   (buckets RVOL, défauts 0.7 / 1.5 / 2.0 / 3.0)
atr_dead_percentile, atr_extreme_percentile, atr_stop_multiplier   (régime ATR, défauts 0.15 / 0.90 / 1.5)
```

Seuls les seuils sont exposés (jamais `primary_window`/`percentile_lookback`/`period`/`regime_lookback`, qui restent des réglages internes de l'indicateur, pas un choix produit). Un paramètre omis garde sa valeur par défaut ; un ordre invalide (`rvol_low < rvol_significant < rvol_strong < rvol_anomaly`, `atr_dead_percentile < atr_extreme_percentile`, `atr_stop_multiplier > 0`) renvoie `422` avec un message explicite plutôt qu'un résultat silencieusement faux.

Sur `/screener`, tout override bypass le cache partagé (recalcul à la demande, jamais persisté en base) — le cache sert la lecture par défaut à tout le monde, un override est une lecture perso, pas la vérité canonique. Sur `/decisions` et `/backtest`, c'est stateless comme le reste : pas de notion de "Settings sauvegardés" côté moteur, c'est au front (Settings) de renvoyer les mêmes valeurs à chaque appel.

## Collecte manuelle

```bash
.venv/Scripts/python -m app.market_data.cli BTCUSDT 1h --limit 300
```

## Ce qui n'existe pas encore

- Monte Carlo (robustesse par variation des paramètres) — mentionné dans la mission, pas encore fait.
- Location (Volume Profile / VWAP / AVWAP) — V1.5, stage `pending` dans le pipeline.
- Matrice de portes (CDC-VIZ-001, V1.5) et graphe de corrélations (CDC-VIZ-002, V2) — pas commencés ; `pipeline` par ligne dans `/screener` est le prérequis API, maintenant en place.
- ~~Autres providers que Binance~~ — fait : forex/metal/index/energy → `biquote` (gratuit/sans clé), actions → `twelve_data` (voir `app/universe/catalog.py`).
- Optimisation de paramètres (volontairement absente — nécessiterait un split train/test pour éviter l'overfitting, mission §11).
