# RS-07 — OF-0 « Order flow intrabarre : information nouvelle ou redite de l'OHLCV ? » : règles et critères figés

**Statut :** **pré-enregistré avant tout téléchargement 1 s et tout calcul** · amendement `VP0-2026-09-28e` · Claude local (session ichivol-e4) sur décision de Samir · 2026-09-28.
**Origine :** audit order flow / footprint du 2026-09-28.

**Constats de l'audit, qui fixent la question :**
- Le delta et le CVD par barre d'IchiVol sont **exacts**. `taker_buy_base` de la kline est égal à Σ aggTrades acheteurs agresseurs : vérifié sur BTCUSDT au 2024-03-01, à la minute et sur la journée.
- Un footprint n'apporte donc, au mieux, que :
  - la répartition **par prix** du volume et du delta dans la barre ;
  - leur **ordre temporel** dans la barre.

**Question OF-0 :** ces informations intrabarre sont-elles (Q1) **non redondantes** avec l'OHLCV + delta déjà disponibles, et (Q2) **liées au rendement futur** ?

**Ce que OF-0 n'est pas :**
- ni un moteur, ni une stratégie, ni une UI, ni un contexte pour agent ;
- aucun changement du pipeline, du paper, de VP1 ni de `location.py`.

**Divulgation :** pendant l'audit, un seul jour de la période (BTCUSDT 2024-03-01, aggTrades et klines 1 min) a été ouvert. Seule l'égalité des sommes a été calculée, aucune des mesures ci-dessous.

---

## 1. Données et fenêtre

| Élément | Valeur figée |
|---------|--------------|
| Actif | **BTCUSDT spot** uniquement |
| Série | Klines **1 s** Binance Vision (archives mensuelles, checksum `.CHECKSUM` vérifié, manifeste sha256), agrégées en barres **1h** UTC |
| Fenêtre | Mesures 2021-07-01 → 2024-12-31. Chargement dès 2021-06-01 (warm-up ATR / RVOL). Troncature `< 2025-01-01`, **assertion** |
| Interdit | Validation 2025, holdout 2026, autres actifs ou TF, toute variante des paramètres §2–§4 |
| Barre valide | ≥ **3 400** secondes présentes sur 3 600. Sinon la barre est exclue, comptée, et ne sert pas de cible |

**Nature des données (étiquetage obligatoire dans tout rapport) :** « footprint **approximé 1 s** ». Chaque seconde porte un volume et un delta exacts, mais son prix n'est connu que dans `[low, high]` de la seconde. Ce n'est **pas** un footprint tick par tick.

## 2. Grille de prix (causale)

- Largeur de bucket `w[t] = ATR14[t−1] / 20`. ATR = moyenne simple du true range sur 14 barres 1h (définition moteur), connue à la clôture de `t−1`.
- Grille ancrée à `floor(low[t] / w) × w`.
- Chaque seconde `s` de la barre est affectée au bucket de son prix typique `(high_s + low_s + close_s) / 3`.
- Delta de la seconde : `2 × taker_buy_s − volume_s` (exact).

## 3. Mesures intrabarre OF (calculées à la clôture de `t`)

Notations : `H, L, V` = plus haut, plus bas, volume de la barre ; `R = H − L` ; `cd(s)` = delta cumulé depuis l'ouverture de la barre jusqu'à la seconde `s` incluse.

| ID | Nom | Définition |
|----|-----|-----------|
| **F1** | `poc_loc` | `(centre du bucket de volume max − L) / R` ; égalité → bucket le plus bas. Borné à [0, 1]. Non défini si `R = 0` |
| **F2** | `delta_top` | Σ delta des secondes dont le prix typique est dans `[H − 0,2R, H]`, divisé par `V` |
| **F3** | `delta_bot` | Idem, dans `[L, L + 0,2R]` |
| **F4** | `delta_path` | `(cd_final − (max cd + min cd)/2) / ((max cd − min cd)/2)`, dans [−1, 1] : position du delta final dans son propre range intrabarre. Non défini si `max cd = min cd` |
| **F5** | `burst_share` | Part de `V` réalisée dans les **36** secondes les plus actives de la barre (1 %) |

Écart avec le message de réservation : « part des gros ordres agressifs » est **remplacé** par F5. Les klines 1 s ne donnent pas la taille des ordres. Ce choix est fait **avant** tout téléchargement 1 s.

## 4. Référence OHLCV + delta (déjà disponibles dans IchiVol)

Toutes les références sont à la barre `t` :
- `clv = (2C − H − L) / R` ;
- `ret = ln(C / O)` ;
- `dr = (2 × taker_buy − V) / V` ;
- `range_atr = R / ATR14[t−1]` ;
- `uw = (H − max(O, C)) / R` et `lw = (min(O, C) − L) / R` ;
- `lrvol = ln(V / moyenne(V[t−20 .. t−1]))`.

**Base de régression :** ces 7 variables, **plus leurs carrés**, plus les produits `clv × dr` et `ret × dr`, soit 16 régresseurs et une constante.

## 5. Q1 — redondance

- Pour chaque `Fi`, R² de l'OLS de `Fi` sur la base §4, sur toutes les barres valides.
- **Q1 réussie** si **au moins 2 des 5** `Fi` ont **R² < 0,5**.
- Lecture par mesure :
  - R² ≥ 0,8 → **redondante** ;
  - 0,5 ≤ R² < 0,8 → partiellement redondante ;
  - R² < 0,5 → information nouvelle.
- Seules les mesures à R² < 0,8 passent en Q2.

## 6. Q2 — lien avec le rendement futur (sur la partie nouvelle seulement)

- **Résidu** `ei` = `Fi` − prédiction OLS de §5 (même ajustement, en échantillon, descriptif).
- **Cible :** `y[t] = ln(open[t+5] / open[t+1])`, soit le rendement sur 4h à partir de l'ouverture suivante. La barre `t+1` doit exister.
- **IC** = corrélation de Spearman(`ei`, `y`).
- **Intervalle :** bootstrap par **jour UTC** (on tire des jours entiers), 10 000 tirages, seed 7. Niveau **1 − 0,05/k**, où `k` = nombre de mesures admises en Q2 (Bonferroni).
- **Q2 réussie pour `Fi`** si les trois conditions sont vraies :
  1. l'intervalle exclut 0 ;
  2. |IC| ≥ **0,02** ;
  3. l'IC a le même signe sur **≥ 3 des 4** périodes (2021 S2, 2022, 2023, 2024).
- **Q2 réussie** si au moins une `Fi` réussit.

## 7. Verdicts

| Verdict | Condition | Suite autorisée |
|---|---|---|
| **REDONDANT** | Q1 échoue | Arrêt de la piste footprint. Seule reste possible la correction de précision du volume profile de `location.py`, en chantier technique séparé, sans prétention d'edge |
| **NOUVEAU, NON PRÉDICTIF** | Q1 réussie, Q2 échoue | Même chose. Une étude de zones (OF-1) demande une décision de Samir et un nouvel amendement |
| **NOUVEAU ET PRÉDICTIF** | Q1 et Q2 réussies | **Rédaction** d'OF-1 (OrderFlowZone, réaction au retest, placebo, coûts) sous nouvel amendement, jugée sur d'autres données que 2021–2024 |

L'IC de Q2 n'est **pas** une stratégie. Même NOUVEAU ET PRÉDICTIF n'autorise aucune intégration au pipeline.

## 8. À reporter (descriptif)

- Nombre de barres valides et exclues.
- Pour chaque `Fi` : distribution, R² de Q1, coefficients principaux, IC et intervalle, IC par année.
- Contrôles C1 et C2 (§9).
- Manifeste des zips.

## 9. Contrôles exigés avant le calcul

1. **C1, agrégation :** l'agrégation 1 s → 1h doit égaler les klines 1h VP1 (volume et `taker_buy`, écart relatif ≤ 1e-6) sur toutes les barres complètes. Sinon, arrêt et diagnostic.
2. **C2, qualité de l'approximation :** part du volume des secondes dont `[low_s, high_s]` couvre plus d'un bucket. Si elle dépasse **10 %**, le rapport marque « approximation fragile » et Q1 / Q2 sont reportées sans verdict REDONDANT / NOUVEAU.
3. **Causalité :** `w[t]` et `lrvol` n'utilisent que `t−1` et avant. Test de troncature : les mesures de `t` sont identiques que la série s'arrête à `t` ou continue.
4. **Tests unitaires :**
   - bucketisation ;
   - F1–F5 sur des barres synthétiques ;
   - égalités et cas limites (`R = 0`, delta constant) ;
   - cible `y` ;
   - assertion < 2025 ;
   - horodatages µs.
5. **Isolation :** code dans `ichivol-app/engine/rs/of0/`, stdlib (+ `tzdata` si nécessaire). Aucune modification ailleurs.

## 10. T10b

+5 lignes `OF-0-BTC-1h-F1` … `F5` (une par mesure testée en Q2, prudence). Q1 seule n'est pas un essai d'edge.
