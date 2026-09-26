# Chart Intelligence — intégration dans IchiVol V3

Prototype **React/TS directement intégrable** : composants, hook, types et mock placés dans l'organisation existante de `ichivol-app/src` (`components/<sous-dossier>/` + `lib/`). Aucun nouveau squelette, aucune route, aucune navigation, aucune dépendance ajoutée, aucun fichier existant modifié.

> Branche : `feat/chart-intelligence-prototype` (base `main` @ `8ddeec2`).

---

## 0. Décision structurante : pas de `DrawingObject`, on réutilise `ChartObject`

L'analyse du dépôt montre que le contrat demandé **existe déjà** côté Python et côté front :

- `engine/app/chart_objects/types.py` → `ChartObject` (id déterministe, `type`, `source`, `layer`, `points`, `price_low/high`, `side`, `label`, `confidence`, `as_of`, `origin`, `subtype`) ;
- producteurs déjà branchés : `from_structure.py` (zones S/R, trendlines), `from_breaks.py` (BOS / CHoCH), `from_fvg.py` (T9d), `from_fibonacci.py` (T9e) ;
- miroir TS : `src/lib/chartObjects.ts` + endpoint `GET /api/engine/chart-objects/{symbol}`.

Créer un `DrawingObject` aurait été une **deuxième** vérité à migrer. Le prototype lit donc des `ChartObject` et n'ajoute que des extensions **additives** :

| `DrawingObject` (cahier des charges) | Équivalent `ChartObject` utilisé |
|---|---|
| `id` | `id` (déterministe, inchangé) |
| `symbol`, `timeframe` | idem |
| `type: fibonacci` | `type: horizontal_line`, `layer: fibonacci` (1 objet par niveau, format T9e) regroupés par `origin.group_id` |
| `type: trendline` | `type: trend_line` / `ray`, `layer: structure` |
| `type: support / resistance` | `type: zone`, `layer: structure`, `side` |
| `type: fvg` | `type: rectangle`, `layer: fvg` |
| `type: bos / choch` | `type: marker`, `layer: breaks`, `subtype: bos / choch` |
| `type: channel` | `type: channel` (existe, non utilisé dans le mock) |
| `type: liquidity` | `layer: liquidity` **(nouvelle valeur)** |
| `type: confluence` | `layer: confluence` **(nouvelle valeur)** |
| `source: engine / agent / manual` | `source: engine / claude / user` (existant) |
| `confidence` | `confidence` (0–1, existant) |
| `anchors` | `points` + `origin.anchor_start / anchor_end` |
| `reason` | `origin.reason` |
| `status` | `origin.status` (valeurs FVG existantes `open/partial/filled/invalidated` + `tested/broken/swept/archived`) |
| `metadata` | `origin` |

Swings HH / HL / LH / LL : `type: text`, `layer: breaks`, `origin.kind: swing`.

---

## 1. Fichiers produits

| Fichier | Rôle | Dépendances | Où l'intégrer |
|---|---|---|---|
| `src/lib/chartIntelligence.ts` | Types (enveloppe de réponse, `IntelligenceObject`, `IntelligenceOrigin`), classement en couches UI, libellés, formatage, client `getChartIntelligence()` | `chartObjects.ts`, `engineIndicators.ts` (`ProjectedKumoPoint`), `marketPrefs.ts` (`OBJECT_LAYER_META`), `types.ts` (`Candle`) | Déjà à sa place (`lib/`) |
| `src/lib/useChartIntelligence.ts` | Hook : chargement mock/API, replay `as_of`, sélection, couches (localStorage `ichivol.chart-intelligence.layers.v1`, même pattern que `marketPrefs`) | `chartIntelligence.ts`, `chartIntelligenceMock.ts`, React | `lib/` |
| `src/lib/chartIntelligenceMock.ts` | **MOCK** — réponse Python simulée, objets datés (`known_at`) + historique de statut, `mockChartIntelligenceAt(asOf)` | `chartIntelligenceMock.data.ts` | `lib/` — à supprimer quand l'API existe |
| `src/lib/chartIntelligenceMock.data.ts` | **MOCK généré** — 111 bougies 1H + Tenkan/Kijun + Kumo projeté | — | `lib/` — à supprimer avec le mock |
| `scripts/gen-chart-intelligence-mock.py` | Génère le fichier `.data.ts` (Ichimoku calculé en Python, jamais dans React) | Python 3 stdlib | `ichivol-app/scripts/` |
| `components/chart-intelligence/IntelligenceChart.tsx` | Bougies + volume + Ichimoku via **lightweight-charts** (déjà en dépendance), fournit la projection temps/prix → px aux couches | `lightweight-charts`, `chartColors.ts`, `theme.ts` | — |
| `components/chart-intelligence/chartProjection.ts` | Contexte de projection partagé | React | — |
| `components/chart-intelligence/DrawingLayer.tsx` | Surface SVG au-dessus du canvas, `Chip`, étiquettes de gouttière droite sans chevauchement | `drawingContext.ts` | — |
| `components/chart-intelligence/drawingContext.ts` | Contexte des couches, `useDrawingLayer`, mise en page des étiquettes | `chartIntelligence.ts` | — |
| `MarketStructureLayer.tsx` | HH/HL/LH/LL + BOS/CHOCH (segment depuis le swing cassé) | `DrawingLayer` | — |
| `SupportResistanceLayer.tsx` | Zones S/R (dont HTF 4H) | idem | — |
| `TrendlineDrawing.tsx` | Trendlines / rays | idem | — |
| `FibonacciDrawing.tsx` | Auto Fib groupé, ancres, en-tête « AUTO FIB · source · TF · Confidence » | idem | — |
| `FVGDrawing.tsx` | FVG actives / partielles / comblées | idem | — |
| `LiquidityDrawing.tsx` | BSL / SSL, balayage | idem | — |
| `ConfluenceZone.tsx` | Zone de confluence hachurée | idem | — |
| `LayerControls.tsx` | 8 couches on/off (rendu réel) | `MarketLayersMenu.css` | — |
| `DrawingInspector.tsx` | Détail de l'objet sélectionné (SOURCE, TF, FROM/TO, CONFIDENCE, WHY?, USED BY DECISION ENGINE) | `chartIntelligence.ts` | — |
| `AIAnalysisPanel.tsx` | AI ANALYST + DECISION ENGINE + Waiting | idem | — |
| `ReplayControls.tsx` | ◀ PLAY ▶ + curseur + retour Live | hook | — |
| `ChartIntelligencePanel.tsx` | Assemblage prêt à monter (bloc, pas une page) | tout ce qui précède | Voir §4 |
| `ChartIntelligence.css` | Styles **scopés** `.ci-root` / `.ci-*` + `html.dark .ci-root` | — | Importé par le panel |
| `index.ts` | Barrel d'export | — | — |

---

## 2. Éléments IchiVol réutilisés

- **lightweight-charts v5** (pas de nouvelle lib graphique) ; mêmes options que `PriceChart` (locale fr-FR, formatter d'axe, volume en overlay 0.28, nuage Kumo par double AreaSeries).
- `readChartColors()` / `withAlpha()` (`lib/chartColors.ts`) et `THEME_CHANGE_EVENT` (`lib/theme.ts`) → thème clair/sombre identique.
- Tokens globaux `--bull`, `--bear`, `--tenkan`, `--kijun`, `--span-a/b`, `--cloud`, `--chart-grid` (`theme/camap-tokens.css`).
- Valeurs maquette de `.market-page` (cartes 12 px, `.tag` green/amber/red/gray, Manrope / DM Mono / Newsreader, `.segmented`) recopiées dans des classes `.ci-*` scopées — même méthode que `MarketLayersMenu.css`.
- `MarketLayersMenu.css` : `LayerControls` réutilise **les mêmes classes** (`.mkt-layer-row`, `.mkt-layer-swatch`, `.mkt-layers-quick`…).
- `OBJECT_LAYER_META` (couleurs des calques Structure / Cassures / Fibonacci / FVG).
- Types `ChartObject`, `ChartObjectLayer`, `ChartObjectsResponse`, `Candle`, `ProjectedKumoPoint`.
- Conventions API de `getChartObjects()` (cookie, proxy Node `/api/engine/*`, erreur `detail`).

**Non réutilisés, et pourquoi (sans les modifier) :**

- `PriceChart` : il va chercher lui-même ses overlays au moteur et dessine les objets en price lines pleine largeur, sans sélection. Le brancher aurait imposé de le modifier. Convergence possible plus tard (§6).
- `MarketLayersMenu` (le composant) : lié aux clés `LayerPrefs` de `marketPrefs` ; y ajouter 4 couches = migration `ichivol.market.layers.v5 → v6`. Seul son CSS est repris.
- `VerdictBadge` / `gateTone` : liés à `DecisionLabel` / `PipelineGateLabel` (BUY/SELL/WATCH/NO_TRADE). `PRUDENCE` n'en fait pas partie → `analysisTone()` reconnaît ces gates et affiche tout autre libellé Python tel quel.
- `KeenIcon` : aucune icône nécessaire.

---

## 3. Dépendances ajoutées

**Aucune.** `package.json` inchangé.

---

## 4. Intégration (au choix, rien n'est câblé d'office)

**A. Dans le Marché, sous la carte graphique existante** (`src/pages/MarketPage.tsx`) :

```tsx
import { ChartIntelligencePanel } from '../components/chart-intelligence'
// … après la <section className="card"> du PriceChart, dans .market-layout ou juste après :
<ChartIntelligencePanel symbol={symbol} timeframe={interval} source="mock" />
```

**B. Route de prévisualisation non listée dans la navigation** (`src/Root.tsx`, dans le bloc `/app`) :

```tsx
<Route path="chart-intelligence" element={<div className="market-page"><ChartIntelligencePanel symbol="SOLUSDT" timeframe="1h" /></div>} />
```

**C. À la carte** : chaque couche est un composant autonome sous `<IntelligenceChart><DrawingLayer …>…</DrawingLayer></IntelligenceChart>` (voir `ChartIntelligencePanel.tsx`).

En mode mock, `symbol` / `timeframe` sont ignorés par la source (la réponse est toujours SOLUSDT 1H).

---

## 5. Ce qui est MOCK / ce qui sera remplacé par l'API Python

| MOCK aujourd'hui | Remplacement |
|---|---|
| `chartIntelligenceMock.ts`, `chartIntelligenceMock.data.ts`, `scripts/gen-chart-intelligence-mock.py` | Supprimer |
| `source="mock"` dans le hook / panel | `source="api"` → `getChartIntelligence()` |
| Scores de confluence et confidences | Calculés par Python (`origin.score_is_mock` doit passer à `false`) |
| Textes AI ANALYST | Agent (serveur), jamais autorité de décision |
| `mockChartIntelligenceAt(asOf)` (filtre `known_at` + historique de statut) | Paramètre `as_of` de l'endpoint : Python recalcule sur les bougies ≤ `as_of` |

**Rien à changer dans les composants** : ils ne lisent que `ChartIntelligenceResponse`.

### Contrat Python à créer

`GET /api/engine/chart-intelligence/{symbol}?timeframe=1h&limit=300&as_of=<unix>` (router `settings.engine_api_prefix`, passthrough Node déjà en place), réponse = `ChartIntelligenceResponse` :

```jsonc
{
  "symbol": "SOLUSDT", "timeframe": "1h", "as_of": 1788616800,
  "provider": "binance", "provider_symbol": "SOLUSDT",
  "candles":    [{ "time": 0, "open": 0, "high": 0, "low": 0, "close": 0, "volume": 0 }],
  "ichimoku":   [{ "time": 0, "tenkan": 0, "kijun": 0 }],
  "projection": [{ "time": 0, "senkouA": 0, "senkouB": 0 }],
  "market_state": { "trend": "bullish", "structure": "HH_HL", "volatility": "normal", "rvol": 1.42 },
  "objects": [ /* ChartObject.to_dict() */ ],
  "analysis": { "state": "PRUDENCE", "confidence": 0.78, "summary": "…", "confluence": ["…"], "waiting": ["RVOL > 1.5"] },
  "replay": { "first": 0, "last": 0, "bar_seconds": 3600 }
}
```

Ajouts Python nécessaires (tous additifs) :

1. `ChartObjectLayer` : `LIQUIDITY = "liquidity"`, `CONFLUENCE = "confluence"`.
2. Clés `origin` : `producer`, `known_at` (anti-lookahead), `reason`, `used_by_decision`, `group_id`, `anchor_start/anchor_end` (temps + prix ; aujourd'hui `from_fibonacci` expose `start_bar/end_bar` en index), `swing_time` (BOS/CHOCH), `htf`, `components` (confluence), `score_is_mock`.
3. `from_fibonacci` : ratios 0 et 1 (le moteur n'émet que 0.236 → 0.786 ; `key_only=True` en prod n'émet que 0.5 / 0.618 / 0.786).
4. Producteurs manquants : swings HH/HL (le moteur structure les calcule, pas encore exportés en ChartObject), liquidité, zone de confluence (le module `engine/app/confluence/` observe des poids de familles, pas de zones).
5. `market_state` et `analysis` : à assembler depuis le pipeline de décision et l'agent.

---

## 6. Écarts assumés par rapport au cahier des charges

- **Fib 61,8 %** de 124,30 → 137,80 = **129,46** (pas 130,80–131,40). Le mock aligne donc 61,8 % sur le support 129,40 et la confluence 130,80–131,40 utilise **Fib 50 % (131,05)**.
- **Kijun 1H** vaut 133,61 sur la dernière bougie (calcul réel sur la série) → exclue de la confluence plutôt que d'inventer une valeur.
- **Bullish FVG 131,20–131,85** : ACTIVE pendant tout le replay, puis **PARTIALLY FILLED** sur la dernière bougie, puisque le prix entre dans la zone de confluence qui la chevauche (sémantique moteur T9d).
- Symbole **SOLUSDT** (prix 124–138 cohérents) au lieu de BTCUSDT.
- Libellés de l'inspecteur en anglais comme demandé (SOURCE, WHY?, USED BY DECISION ENGINE) ; textes d'analyse en français.

## 7. Limites connues

- Le glisser de l'échelle de prix n'émet pas d'événement lightweight-charts : la reprojection des couches suit `pointermove` / `wheel`.
- Mise en page des étiquettes simple (empilement vertical à droite du dernier prix) ; version courte sous 600 px.
- `npm run build` échoue déjà sur `main` (erreur TS pré-existante `OverviewPage.tsx:389`), sans rapport avec ce module ; `tsc` ne signale aucune erreur dans les nouveaux fichiers, `oxlint` : 0 avertissement.
