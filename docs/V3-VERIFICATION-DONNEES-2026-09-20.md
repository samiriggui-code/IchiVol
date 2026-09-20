# V3 — Vérification des sources de données (2026-09-20)

Légende : **T** = testé en réel dans cette session ; **D** = lu dans une documentation (non testé) ; **?** = non vérifié.

## Tests réels effectués

| Source | Test | Résultat |
|---|---|---|
| Binance (data-api.binance.vision) | klines 1h, bookTicker, trades, depth(5), klines 1m limit 1000, plus ancienne bougie 1h | **T** OK. Bid/ask et tailles (`bookTicker`), trades avec `isBuyerMaker`, carnet, historique 1h depuis 2017-08-17. Poids de requête renvoyé dans les en-têtes. Archives trades quotidiennes sur data.binance.vision (HEAD 200). |
| biquote | ohlc EURUSD 1h ; 1d et 15m avec count=1000 ; endpoints quote/tick/price/bidask ; /api/symbols | **T** OHLC OK, `volume`=0, `tickVolume` renseigné, `isOpen` par bougie. **Plafond 101 barres** quelle que soit la demande. **Aucun endpoint bid/ask** (404). `/api/symbols` : 1 673 entrées, `hasData` faux pour presque toutes (déjà signalé comme non fiable dans le catalogue). Conditions d'utilisation : **?**. |
| Twelve Data (clé gratuite du .env) | EUR/USD, XAU/USD, AAPL, BTC/USD 1h ; quote ; profondeur ; SPX ; CL ; bid_ask | **T** OK sur forex, or spot, actions US (volume présent), crypto. Historique : EUR/USD 1day jusqu'en 2005 ; 1min jusqu'en 2021 ; AAPL 1day jusqu'en 2001. 5 000 barres par requête max. **Forex/or : pas de volume.** `/quote` : pas de bid/ask ; **endpoint bid_ask inexistant (404)** ; la documentation n'en mentionne aucun. **SPX : refusé** (« Grow or Venture plan ») → bloqué par le plan, pas absent. **Piège** : `CL` renvoie *Colgate-Palmolive* (NYSE), pas le pétrole : les tickers ambigus exigent un identifiant de place explicite. Quota gratuit : 8 crédits/minute (compteur `Api-Credits-Left` observé). |
| Dukascopy (datafeed public) | fichiers ticks horaires EURUSD, XAUUSD, USA500IDXUSD | Fichiers accessibles (HTTP 200, 75–130 Ko), donc bid/ask historique **annoncé** ; je ne les ai pas exploités : les conditions interdisent robots, scrapers et stockage en base (voir plus bas). |
| TradingView MCP | Non testé : OAuth interactif + abonnement Essential requis. | Bloqué faute de compte, pas absence de couverture. |

## Droits d'usage (lus dans les textes)

- **TradingView** — conditions : données « display-only », usage personnel/interne ; interdiction du « non-display usage » : trading automatisé, génération d'ordres, « price referencing », décision algorithmique ; interdiction de distribution. Le MCP est en bêta, données **différées**, ~100 requêtes/min, limites quotidiennes possibles ; pas de bid/ask. → Ne peut pas alimenter le moteur sans autorisation écrite.
- **Twelve Data** — CGU : stockage/cache « au-delà des durées permises par la documentation » interdit (durée non précisée) ; HFT sans licence interdit ; redistribution interdite ; offre gratuite : usage commercial interdit ; dérivés non reconstituables autorisés. Page tarifaire : « internal display data access » dès Grow, « internal **non-display** data access » seulement sur **Ultra**. → À clarifier : un moteur qui calcule des indicateurs côté serveur est-il du « non-display » ?
- **OANDA Europe Markets** — licence API (juillet 2022) : usage autorisé pour trader ses propres comptes, interfaces personnalisées, et **systèmes de trading automatisés sur FXTrade / FXTrade Practice** ; « Internal Use » = recherche, analyse, traitement de données ; pas de redistribution ; obligation de tenir un registre des copies. Pas d'interdiction explicite de stockage, mais rien d'explicite non plus pour un stockage d'historique à des fins de backtest.
- **Dukascopy** — CGU : usage personnel non commercial ; « may not be stored in databases » ; robots/scrapers interdits sans accord écrit → **exclu** du pipeline automatique.

## OANDA : ce qui est établi, ce qui ne l'est pas

- Établi (D) : l'API v20 est offerte à toutes les divisions sauf OANDA Global Markets et OANDA TMS Brokers. Hôtes practice : `api-fxpractice.oanda.com` / `stream-fxpractice.oanda.com`. Limites : 120 req/s REST, 20 flux, 2 nouvelles connexions/s (par IP). Compte démo EU : e-mail + téléphone, pas de vérification d'identité mentionnée, expire 180 jours après la dernière connexion, 50 000 unités virtuelles ; l'Espagne est exclue, la France n'est pas exclue. Le jeton API se génère depuis le portail (My Services → Manage API Access).
- **Non établi** : que la division européenne (OANDA Europe Markets Ltd) délivre un jeton v20 pour un compte **démo** — la page démo EU ne parle que de MT5 et de l'application mobile ; la profondeur réelle et le bid/ask historique via v20 pour un client EU ; les instruments exacts disponibles en CFD pour un résident français (règles ESMA) ; les conditions exactes de stockage. Le KYC n'est **pas** présenté comme acquis : il n'est requis à ma connaissance documentaire que pour le compte réel, ce qui reste à confirmer.

## Twelve Data : tarif

Page tarifaire lue aujourd'hui (USD, hors taxes) : Basic gratuit (8/min, 800/jour, US, forex, crypto) ; **Grow 79 $/mois (66 $/mois en annuel = 790 $/an)** ; Pro 229 $ (191 $) ; Ultra 999 $ (832 $). Grow ajoute matières premières et actions/ETF/indices mondiaux ; Pro : actions EU temps réel. **Écart signalé** : une recherche web donnait Grow à 29 $/mois. Je retiens la page officielle (79 $) et le message d'erreur mentionne aussi un plan « Venture » : la grille bouge, à revérifier avant tout achat. Aucun achat n'est engagé.

## Matrice par famille

Volume : nature. Bid/ask actuel et historique : disponibilité. « Action » : ce qu'il reste à faire.

| Famille | Fournisseur / instrument | Historique OHLCV | Volume | Temps réel / différé | Bid/ask actuel | Bid/ask hist. | Quotas | Droits calcul/stockage | Coût vérifié | Action nécessaire |
|---|---|---|---|---|---|---|---|---|---|---|
| Crypto | **Binance** BTCUSDT (et 19 autres) | T 1h depuis 2017 ; 1m ; 1000/requête | Volume d'échange réel (d'une place) | T temps réel | **T** oui + tailles | Trades T + archives ; carnet historique : ? | Poids 1m (en-têtes) | ? conditions API publiques non relues | 0 | Relire les conditions Binance ; brancher quotes/trades |
| Forex | **Twelve Data** EUR/USD | T 1day depuis 2005 ; 1min depuis 2021 ; 5000/req | **Aucun** | Minute (annoncé) | **Non** | Non | 8/min, 800/j (gratuit) | Voir ci-dessus, non-display à clarifier | 0 (gratuit) ; Grow 66–79 $ | Clarification licence |
| Forex | **biquote** EURUSD | T 101 barres seulement | Tick volume | T temps réel | Non | Non | non documenté | ? inconnus | 0 | Relire CGU ; usage secours/live |
| Forex | **OANDA** practice | D depuis 2005, granularités 5 s→mois | D tick volume | D temps réel | **D** oui | D via candles bid/ask | 120 req/s | D Internal Use + ATS ; stockage à clarifier | 0 (compte démo) | Compte démo (e-mail+tél) + confirmer jeton API EU |
| Métaux | **Twelve Data** XAU/USD | T 1h ok | Aucun | T récent | Non | Non | idem | idem | 0 | idem |
| Métaux | **OANDA** XAU/USD CFD | D | D tick | D | D oui | D | idem | idem | 0 | idem |
| Indices | **Twelve Data** SPX | **Bloqué** par plan (Grow) | ? | ? | Non | Non | — | non-display Ultra | Grow 66–79 $ | Décision budget ou autre source |
| Indices | **biquote** US500, USTEC | T 101 barres | Tick | T | Non | Non | ? | ? | 0 | CGU |
| Indices | **OANDA** CFD indices | D | D | D | D oui | D | idem | idem | 0 | Confirmer liste pour résident FR |
| Actions | **Twelve Data** AAPL | T 1day depuis 2001 ; 1h | T présent (place/consolidé : ?) | T différé/temps réel : ? | Non | Non | 8/min | idem | 0 (US) | Clarification licence ; identifiants de place (piège CL) |
| Futures | Databento CME | D | Réel | D | D | D | ? | D licence CME à ajouter | 179 $/mois + licence (D, blog) | Devis/échantillon avant décision |
| Multi | **TradingView MCP** | D 5000 barres, 1m→1M | Nature ? | **Différé** | Non | Non | ~100/min | **Non-display interdit** | Essential 12,95 €/mois équiv. | Autorisation écrite (question ci-dessous) |

## Deux besoins distincts

- **Alimenter l'analyse** : Binance (crypto) et Twelve Data gratuit (forex, or, actions US, avec historiques profonds) suffisent techniquement aujourd'hui. Le volume n'existe pas pour forex/or : RVOL y est « confirmation volume indisponible », par conception. Indices : rien de gratuit dans Twelve Data ; biquote en secours à 101 barres.
- **Simuler l'exécution** : seul Binance donne un bid/ask testé. Pour forex/métaux/indices, OANDA est le seul candidat trouvé avec bid/ask, sous réserve de l'accès API démo EU. Pour actions/futures : aucun bid/ask gratuit vérifié.
- **Hypothèses du simulateur en `candle_only`** : spread configuré par instrument (documenté comme hypothèse, versionné), slippage en fraction de l'ATR ou en bps, exécution au prix d'ouverture de la bougie suivante, règle prudente stop-avant-objectif si les deux sont touchés dans la même bougie, gap au-delà du stop exécuté à l'ouverture, latence d'une bougie minimum, résultats marqués « exécution dégradée ».

## Question à envoyer à TradingView (à faire par vous, non envoyée)

> Objet : Usage du MCP TradingView par une application privée d'analyse et de simulation
>
> Bonjour, nous développons une application interne, à usage personnel, qui analyse des marchés (indicateurs Ichimoku, volume relatif) et simule des ordres fictifs, sans aucun ordre réel ni redistribution. Nous étudions le MCP officiel TradingView (plan Essential). Merci de préciser par écrit :
> 1. Les données obtenues via le MCP (barres OHLCV, cotations) peuvent-elles être utilisées comme entrée de calculs automatisés (indicateurs, scores, backtests) exécutés par notre logiciel, ou cela relève-t-il du « non-display usage » interdit par vos conditions ?
> 2. Ces données peuvent-elles être conservées dans une base locale (durée éventuelle) pour rejouer des backtests ?
> 3. Un appel MCP effectué par un service automatisé (sans intervention manuelle, jeton OAuth conservé) est-il autorisé ?
> 4. Quelle est la nature du volume (`v`) et le délai des données différées, par classe d'actif ?
> 5. Existe-t-il une offre de données destinée à un usage non-display ?

Point à clarifier : c'est la ligne « non-display usage » (trading automatisé, « price referencing », décision algorithmique) qui bloque ; la réponse conditionne tout usage autre que l'affichage.

## Clarifications contractuelles à prévoir (non bloquantes)

- Twelve Data : un calcul serveur d'indicateurs sur les données Grow relève-t-il de « display » ou de « non-display » ; durée de stockage permise.
- OANDA (api@oanda.com) : jeton v20 pour un démo OANDA Europe Markets ; stockage d'historique pour backtest.
