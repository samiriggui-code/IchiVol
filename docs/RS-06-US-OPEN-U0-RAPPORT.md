# RS-06 — Rapport RS-U0 « Ouverture US 09:30 New York » : **ÉCHEC**

**Protocole :** `VP0-2026-09-28c`, spec [`RS-05-US-OPEN-SPEC.md`](./RS-05-US-OPEN-SPEC.md), figée au commit `a22a53a` avant tout téléchargement.
**Run :** 2026-09-28 15:47 UTC. Code `ichivol-app/engine/rs/us_open/`, 15 tests.
**Données :** klines 5 min spot Binance Vision, checksums vérifiés, manifeste sha256 `cfa503509cd09c59e23cec2d1305f00e695c458483b8d7218ae1ea75141dca7b`, 377 186 barres par actif.
**Fenêtre :** 2021-07-01 → 2024-12-31, 881 jours NYSE. Rien ≥ 2025 n'a été lu (assertion).
**Résultat brut :** [`rs-u0/rs_u0_result.json`](./rs-u0/rs_u0_result.json).

## 1. Verdict

**ÉCHEC** (RS-05 §5). G4 est vrai sur 3 actifs sur 3, et G2 est faux sur 3 actifs sur 3.
La piste RS-U est **close telle quelle** : aucune variante sans nouvel amendement, marquée post-hoc.

| Actif | n évts (09:30) | Brut moyen | Coût A/R | **Net moyen** | IC95 brut | Réussite | Rang net / 48 | Rang vol15 / 48 | G1 | G2 | G3 | G4 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BTC | 198 | +14,1 bps | 17 | **−2,9** | [+2,1 ; +26,0] | 59 % | 3 | 1 | ✔ | ✘ | ✔ | ✔ |
| ETH | 194 | +4,3 | 17 | **−12,7** | [−11,5 ; +20,0] | 54 % | 14 | 1 | ✔ | ✘ | ✘ | ✔ |
| SOL | 136 | +21,1 | 18 | **+3,1** | [−5,1 ; +48,5] | 48 % | 4 | 1 | ✔ | ✘ | ✔ | ✔ |

## 2. Ce que les données disent

- **Le prémisse est vrai.** 09:30 NY est la demi-heure **la plus volatile** des 48 sur les trois actifs (G1). Les 15 premières minutes font en médiane 63 bps (BTC), 70 (ETH) et 105 (SOL). 10:00 et 10:30 suivent.
- **Il existe un petit retournement brut sur BTC.** +14 bps en moyenne à 60 min, IC95 > 0, 59 % de réussite, rang 3 sur 48. C'est une tendance réelle mais **plus petite que les coûts paper** (17 bps aller-retour). SOL est positif en brut, mais son intervalle inclut 0. ETH n'a rien.
- **Pas exploitable avec nos coûts.** Aucun actif n'a un net > 0 avec un intervalle qui exclut 0.

## 3. Ce que les données n'excluent pas (descriptif, **non concluant, post-hoc**)

Ces lectures viennent **après** le résultat. Elles ne justifient rien sans nouvel amendement jugé sur d'autres données :

| Sous-ensemble | BTC | ETH | SOL |
|---|---|---|---|
| Tercile de vol15 haut | +2,2 (n 82) | −5,7 (n 80) | +30,6 (n 58) |
| Tercile de vol15 bas | −15,6 | −24,5 | −21,0 |
| LONG / SHORT | −4,6 / −1,3 | −21,4 / −5,6 | +2,8 / +3,3 |
| Heure d'été US / hiver | −4,2 / −0,4 | −3,5 / −28,0 | +18,7 / −23,0 |
| 2021 S2 / 2022 / 2023 / 2024 | −19,7 / −5,0 / +1,7 / +0,4 | −5,4 / +2,6 / −21,1 / −27,3 | −9,8 / +5,3 / −19,6 / +18,0 |

Net en bps. Les jours de forte volatilité à l'ouverture font mieux sur les trois actifs, mais les échantillons sont petits (n 58–82) et instables d'une année à l'autre.

- **MAE / MFE**, en R d'un stop placé à l'extrême du balayage, médianes 1,5–1,7 R : en 60 min, le prix va typiquement **au-delà** de l'extrême du balayage. Un stop « au-delà du sommet », comme dans la vidéo, serait touché **plus d'une fois sur deux** (MAE médiane > 1 R).
- **15h30 Paris fixe** contre 09:30 NY sur les 54 jours où les deux diffèrent : 6 à 12 événements par actif, donc trop peu pour dire quoi que ce soit.

## 4. Comptes et exclusions (09:30)

| Actif | Aucun balayage | Balayage sans retour | Ambigu | Exclu | Événements |
|---|---|---|---|---|---|
| BTC | 556 | 124 | 1 | 2 | 198 |
| ETH | 591 | 94 | 0 | 2 | 194 |
| SOL | 655 | 88 | 0 | 2 | 136 |

## 5. Conséquences

- Aucun RS-U1 (simulation) n'est rédigé.
- Rien ne change dans le paper, le pipeline ni VP1.
- Réouverture possible **uniquement** sous un nouvel amendement pré-enregistré, marqué post-hoc s'il s'appuie sur §3, par exemple « ouverture US × vol15 haute ». Il ne pourrait pas être jugé sur 2021–2024, et ce serait une décision de Samir.
- T10b : `RS-U0-U3-5m` passe de « pré-enregistré, non joué » à « **joué : ÉCHEC** ». La mise à jour du ledger est faite au merge par le pilote RS.

## 6. Reproduire

```
cd ichivol-app/engine
python -m rs.us_open.run download --root <data>
python -m rs.us_open.run measure  --root <data> --out <out>
python -m pytest tests/rs_us_open --noconftest
```

Dépendances : stdlib, plus `tzdata` sous Windows pour `zoneinfo`.
