# HANDOFF — Reprise du chantier IchiVol V3 en local

**LIS CE FICHIER EN PREMIER, avant tout autre fichier du repo.**

**Sync local :** 2026-09-27 · `main` @ **`2a585f8`** (= origin/main · squash #154 VP-NT1).

## Contexte

Tu (Claude, en local) supervisues. **Cursor code, tu vérifies**. Canal : [`docs/HANDOFF-CURSOR-V3.md`](docs/HANDOFF-CURSOR-V3.md) — lire **VP-J1 étape 2 DONE** en premier.

## État au tip `main` `2a585f8`

### Mergé récemment

| PR | Tip | Contenu |
|----|-----|---------|
| #154 VP-NT1 | `2a585f8` | N=24 gelé · DSR barre · grille base+adverse · **0 EDGE / 36** |
| #153 VP-GRID1 | `b1cd43d` | Grille A/B/H N=1 provisoire + VP2-R1 |
| #152 / #151 | … | CI tooltips / VP-FIX1 |

### Job en cours

**VP-J1 étape 2 DONE** — branche `cursor/vp-j1-a2fe`, PR **draft [#155](https://github.com/samiriggui-code/IchiVol/pull/155)** :

1. Fixes B6 (ATR+ADX live) + B7 (`WARMUP_BARS`) @ `9a7a019` + tests  
2. Run N=36 · A/B/H/J · base+adverse · n_boot=10 000  
3. Rapport [`docs/VP3-REPORT-FINAL.md`](docs/VP3-REPORT-FINAL.md) · artefact [`docs/vp3-artifacts/j1_results.json`](docs/vp3-artifacts/j1_results.json)  
4. **Résultat :** **0 EDGE / 48** · 0 `bi_beats_bj`  
5. **STOP** — PR draft, **pas de merge**

**Interdit** sans OK : merge, B3/B4/B8, retuning, CI/T-CYCLE, val 2025 / holdout.

## Méthode

1. Cursor : branche + PR draft + handoff → **STOP**.  
2. Claude : vrai diff + verdict.  
3. Pas de merge sans OK.

## Docs clés

| Fichier | Rôle |
|---------|------|
| [`docs/HANDOFF-CURSOR-V3.md`](docs/HANDOFF-CURSOR-V3.md) | Journal |
| [`docs/VP-T10B-LEDGER.md`](docs/VP-T10B-LEDGER.md) | N=36 gelé · B6/B7 joués · déf. J |
| [`docs/VP3-REPORT-FINAL.md`](docs/VP3-REPORT-FINAL.md) | Rapport FINAL J1 |
| [`docs/vp3-artifacts/j1_results.json`](docs/vp3-artifacts/j1_results.json) | Artefact J1 |
| [`docs/VP3-REPORT-GRID.md`](docs/VP3-REPORT-GRID.md) | Grille v2 NT1 |
| [`docs/VALIDATION-PROTOCOL.md`](docs/VALIDATION-PROTOCOL.md) | VP0 §2 B6/B7 / §9 / §10 |
