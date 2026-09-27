# VP3 — rapports A / B / H (BTCUSDT 1h)

> **v3 (VP-GRID1, 2026-09-27)** — time-stop VP2-R1 (entrée = barre 1).  
> Chiffres à jour : [`VP3-REPORT-GRID.md`](./VP3-REPORT-GRID.md) section **BTCUSDT · 1h**.  
> Ce fichier conserve l’historique **v1 / v2** ci-dessous.

---

# Historique — **v2** post VP-FIX1

**Tip code :** branche `cursor/vp-fix1-a2fe` @ `80ffc37` (+ ce doc)  
**Protocole :** `VP0-2026-09-26`  
**Données :** VP1 frozen spot local reconstruit (µs Vision normalisés)  
**Bootstrap :** **stationnaire** Politis–Romano, apparié, **n = 10 000**, seed 7  
**DSR N trials :** 1 (σ empirique T10b non figé — pas de claim EDGE)  
**Date run v2 :** 2026-09-26 (~19:44–20:45 local)

> Pas de claim **EDGE** formel : N T10b = 1 ; grille symbole×TF incomplète ; Q J (B7) non jouée.

## Séries VP1 reconstruites (sha256)

| Série | n_bars (avant → après) | missing | sha256 (nouveau) |
|-------|------------------------|---------|------------------|
| BTCUSDT **1h** | **37 973** → **52 565** | 19 / 52 584 | `3fe8b4708b6953c0331b23d0facb2b9b773574ab9bc66a197e9c639d28da0d88` |
| BTCUSDT **4h** | 9 498 → **13 146** | 0 / 13 146 | `cd8bef9a07f70904dcfc414224411e2ceaeb37b05205c743e1fe87c0bae40782` |
| BTCUSDT **1d** | 1 583 → **2 191** | 0 / 2 191 | `1d04e6bbee290adedc5778823302a4cf4b4de36af7bab3fdd9ede1a7da8ef819` |

- Anciens sha256 : **non archivés** dans le rapport #150 (seul le compteur `n_bars` l’était).  
- Cause écart 1h/1d : Vision spot passe en **µs** au 2025-01-01 — barres 2025–2026 étaient jetées avant VP1-R1.  
- Funding / OI : zips bruts non convertis en séries dans ce run ; spot klines seules normalisées (`≥1e15 → //1000`). Vérifié raw : 2024 = 13 digits (ms), 2025 = 16 digits (µs).

## Tableau avant / après (A · B · H)

| Q | Pair | Métrique | **v1** (#150, pré-fix) | **v2** (VP-FIX1) |
|---|------|----------|-------------------------|------------------|
| A | B1 vs B0 | bi_beats_bj | false | **false** |
| A | | N trades B1 / B0 | 320 / 7 | **317** / 7 |
| A | | Espérance B1 | −19.77 | **−19.90** |
| A | | DSR B1 / B0 | 0.025 / 0.927 | **0.027** / **0.927** |
| A | | Δ mean (IC) | −6.97e−5 exclut 0 | **−6.97e−5** `[−1.32e−4, −5.53e−6]` exclut 0 |
| B | B2 vs B1 | bi_beats_bj | false | **false** |
| B | | N trades B2 / B1 | 129 / 320 | **129** / **317** |
| B | | Espérance B2 | **+0.45** | **−4.31** |
| B | | DSR B2 | 0.524 | **0.410** |
| B | | Δ mean (IC) | +2.13e−5 exclut 0 | **+1.92e−5** `[+3.42e−6, +3.48e−5]` exclut 0 |
| H | B5 vs B2 | bi_beats_bj | false | **false** |
| H | | N trades B5 / B2 | 99 / 129 | **99** / **129** |
| H | | Espérance B5 | **+10.20** | **+5.39** |
| H | | DSR B5 | 0.720 | **0.628** |
| H | | Δ mean (IC) | +3.05e−6 **inclut** 0 | **+3.52e−6** `[−2.38e−6, +9.64e−6]` **inclut** 0 |

### Lecture v2

1. **Verdicts inchangés** : A/B/H toutes `bi_beats_bj = false` — pas d’EDGE.  
2. **B1** toujours dominé par B0 (Δ mean et Sharpe contre B1).  
3. **B2** bat B1 en Δ mean (IC exclut 0) mais DSR reste &lt; 0.95 ; l’espérance trade **passe négative** après correctifs WF/stop (v1 était optimiste).  
4. **B5** vs B2 : Δ non significatif ; DSR et espérance **baissent** vs v1.  
5. −3 trades B1 (320→317) : cohérent avec le point frontière ci-dessous + rebuild 2025–2026.

## Note — signaux dernière barre de pli (INFO Claude)

Un signal émis sur la **dernière barre** d’un pli de test est rempli à l’**open de la 1ʳᵉ barre du pli suivant** (`latency ≥ 1 barre`). Avec l’attribution §5.1.7 (`win[0] ≤ entry_time < win[1]`), ce fill tombe **hors** du pli d’émission **et** hors du pli suivant (gate purge). Il n’est donc compté dans **aucun** pli (~1 barre / pli). **Acceptable** pour VP ; documenté ici pour ne pas interpréter l’écart 320→317 comme une régression silencieuse.

## Setup (inchangé hors correctifs)

| Champ | Valeur |
|-------|--------|
| Symbole × TF | BTCUSDT · 1h |
| Plis | WF1–WF7 (§5) + purge time-stop |
| Harness | VP2 / `sim.py` S1 — stop/TP sur **open brut** ; `force_flat` seulement B0 / VAL / HOLD |
| Bootstrap | stationnaire, blocs géométriques E[L]=24 (1h) |

## Rejouer

```bash
cd ichivol-app/engine
python -m vp3 compare --question A --symbol BTCUSDT --interval 1h --n-boot 10000
python -m vp3 compare --question B --symbol BTCUSDT --interval 1h --n-boot 10000
python -m vp3 compare --question H --symbol BTCUSDT --interval 1h --n-boot 10000
```

Suite (après revue Claude VP-FIX1) : ETH/SOL · 4h · Q **J** · N T10b figé · adverse.
