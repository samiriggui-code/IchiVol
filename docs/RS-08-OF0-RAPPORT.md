# RS-08 — Rapport OF-0 « Order flow intrabarre » : **APPROXIMATION FRAGILE, sans verdict**

**Protocole :** `VP0-2026-09-28e`, spec [`RS-07-OF0-ORDER-FLOW-SPEC.md`](./RS-07-OF0-ORDER-FLOW-SPEC.md), approuvée par la revue #168.
**Code :** `ichivol-app/engine/rs/of0/`, 15 tests. Poussé en `b3569cc` **avant** tout calcul.
**Run unique :** 2026-09-28 17:15 UTC.
- Une première tentative avait échoué **à la lecture** de `c1.json` (BOM UTF-8 écrit par PowerShell), avant toute mesure. Rien n'avait été calculé.
**Données :** BTCUSDT spot, klines 1 s Binance Vision, 2021-06 → 2024-12, 43 archives mensuelles, checksums vérifiés. Rien ≥ 2025 n'a été lu (assertion à la lecture).
- Manifeste : sha256 du contenu JSON `dd7c94cd…`. Le fichier sur disque (fins de ligne Windows) a pour sha256 `ee9d18cd…`.
**Étiquette :** « footprint approximé 1 s ».
**Résultat brut :** [`rs-of0/of0_result.json`](./rs-of0/of0_result.json), [`rs-of0/c1.json`](./rs-of0/c1.json).

## 1. Verdict

**APPROXIMATION FRAGILE : sans verdict REDONDANT / NOUVEAU** (RS-07 §9, contrôle C2).
- C2 : **51,4 %** du volume provient de secondes dont `[low, high]` couvre plus d'un bucket (`w = ATR14 / 20`). Le seuil est 10 %.
- Q1 et Q2 sont reportés ci-dessous **à titre descriptif**. Aucune suite (OF-1, intégration) n'est autorisée par ce run.

## 2. Contrôles

### C1 : réussi après diagnostic

Il s'agit d'une **clarification de lecture de C1, décidée avant toute mesure, pas d'une variante**. Elle a été validée par ichivol-95 avec trois conditions, toutes remplies.

- 31 433 heures agrégées, dont 28 619 complètes (3 600 s) et 2 sous 3 400 s.
- 3 heures complètes sur 28 619 diffèrent de VP1 1h au-delà de 1e-6 :

| Heure (UTC) | Agrégat 1 s (volume / taker_buy) | VP1 = archive **mensuelle** 1h |
|---|---|---|
| 2021-12-24 03:00 | 1260,66778 / 653,19147 | 1237,77455 / 646,47015 |
| 2021-12-27 07:00 | 966,63121 / 443,56613 | 953,99767 / 440,38326 |
| 2022-04-13 05:00 | 763,44194 / 390,35286 | 762,56117 / 390,25552 |

- **Quatre sources recoupées** pour chaque heure :
  - les **aggTrades** journaliers ;
  - la **kline 1h journalière** ;
  - pour 2021-12-27 et 2022-04-13, aussi les **klines 1 min** et le **fichier 1 s journalier**.
  
  Toutes égalent **exactement** l'agrégat 1 s. Seule l'archive **mensuelle** 1h diffère.
- **Conclusion :** l'archive mensuelle 1h de Binance est périmée sur ces heures. Les données 1 s d'OF-0 sont justes.
- **INFO VP1 :**
  - Sur ces 3 heures, l'OHLC 1h est identique dans les archives mensuelle et journalière. Seul le volume diffère, plus 0,01 sur une clôture (2022-04-13 05:00 : 40187,89 contre 40187,90).
  - Les **blocs 4h** qui contiennent ces heures ont un **OHLC identique** dans les archives mensuelle et journalière.
  - **RS-D1, qui n'utilise que l'OHLC 4h, n'est pas touché.** VP1 n'a pas été modifié.

### C2 : échoue

51,4 % du volume est dans des secondes qui couvrent plus d'un bucket. C'est l'**activité en rafales** : les secondes à fort volume sont aussi celles qui ont un large range. La position intrabarre du volume n'est donc pas mesurable finement avec des klines 1 s à cette grille.

### Causalité et troncature

Couvertes par les tests : `w[t]` vient de `ATR[t−1]`, les mesures d'une heure ne lisent que ses secondes, et les horodatages en µs sont gardés.

## 3. Q1 — redondance (descriptif)

30 711 barres 1h valides, du 2021-07-01 à 2024-12-31. Régression sur 16 régresseurs OHLCV + delta (RS-07 §4).

| Mesure | R² | Classe | Dépend de la grille de prix ? |
|---|---|---|---|
| F1 `poc_loc` | 0,058 | nouvelle | **oui** (fortement touchée par C2) |
| F2 `delta_top` | 0,310 | nouvelle | en partie (seuil à 20 % du range) |
| F3 `delta_bot` | 0,291 | nouvelle | en partie |
| F4 `delta_path` | 0,671 | partielle | **non** (chemin temporel exact) |
| F5 `burst_share` | 0,201 | nouvelle | **non** (volumes par seconde exacts) |

Si C2 était passé, Q1 aurait été réussie (4 mesures sur 5 avec R² < 0,5).

## 4. Q2 — lien avec le rendement 4h (descriptif)

- 30 695 barres avec cible. Résidus = OLS de §3 ajustée sur **tout l'échantillon**. C'est acceptable parce que Q2 est descriptif (point INFO de la revue #168).
- Spearman(résidu, `ln(open[t+5] / open[t+1])`). Intervalle à **99 %** (Bonferroni, 5 mesures), bootstrap par jour UTC, 10 000 tirages, seed 7, sur les rangs de l'échantillon complet.

| Mesure | IC | IC99 | 2021 S2 | 2022 | 2023 | 2024 | Q2 |
|---|---|---|---|---|---|---|---|
| F1 | +0,0082 | [−0,0072 ; +0,0238] | −0,012 | +0,007 | +0,023 | +0,009 | ✘ |
| F2 | −0,0009 | [−0,0149 ; +0,0138] | +0,010 | −0,017 | −0,004 | −0,000 | ✘ |
| F3 | +0,0036 | [−0,0113 ; +0,0183] | −0,020 | +0,019 | +0,015 | +0,005 | ✘ |
| F4 | −0,0020 | [−0,0172 ; +0,0136] | +0,001 | −0,005 | −0,007 | +0,006 | ✘ |
| F5 | −0,0007 | [−0,0233 ; +0,0220] | +0,005 | +0,005 | −0,020 | −0,026 | ✘ |

**Aucune mesure n'a de lien détectable avec le rendement des 4 heures suivantes.** Tous les |IC| sont < 0,01, sous le seuil de 0,02, et tous les intervalles contiennent 0. Les deux mesures qui **ne dépendent pas** de l'approximation (F4, F5) ne font pas mieux.

## 5. Ce que les données disent, et ce qu'elles ne disent pas

- **Elles disent :**
  - la répartition intrabarre du delta et du volume n'est **pas** une simple redite de l'OHLCV + delta (R² faibles) ;
  - mais, sur BTC 1h de 2021 à 2024, elle **ne prédit pas** le rendement des 4 heures suivantes au niveau d'une barre prise isolément.
- **Elles n'excluent pas** :
  - un effet **conditionnel** (retest de zones après un événement de volume, soit OF-1) ;
  - un effet à un horizon plus court que 4h ;
  - un effet mesurable avec des **aggTrades**, qui donnent le prix exact de chaque trade et lèveraient C2.
  
  Chacune de ces pistes serait une nouvelle hypothèse, sous un nouvel amendement, et relève d'une décision de Samir.
- **Recommandation (avis, pas un verdict) :** ne pas construire de FootprintEngine sur cette base. Le seul gain concret identifié par l'audit reste la **précision du volume profile** de `location.py` : un chantier technique, sans prétention d'edge.

## 6. Reproduire

```
cd ichivol-app/engine
python -m rs.of0.run download --root <data>
python -m rs.of0.run controls --root <data> --vp1 <vp1/data/series/BTCUSDT_spot_1h_*.json> --out <out>
# c1.json : pass=true après diagnostic (clarification §2), pass_raw=false conservé
python -m rs.of0.run measure  --root <data> --out <out>
python -m pytest tests/rs_of0 --noconftest
```
