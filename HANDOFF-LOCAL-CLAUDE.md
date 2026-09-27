# HANDOFF — Reprise du chantier IchiVol V3 en local

**LIS CE FICHIER EN PREMIER, avant tout autre fichier du repo.**

**Sync local :** 2026-09-27 · `main` @ **`2a585f8`** (= origin/main · squash #154 VP-NT1).

## Contexte

Tu (Claude, en local) supervisues. **Cursor code, tu vérifies**. Canal : [`docs/HANDOFF-CURSOR-V3.md`](docs/HANDOFF-CURSOR-V3.md) — lire **VP-J1 étape 1** en premier.

## État au tip `2a585f8`

### Mergé récemment

| PR | Tip | Contenu |
|----|-----|---------|
| #154 VP-NT1 | `2a585f8` | N=24 gelé · DSR barre · grille base+adverse · **0 EDGE / 36** |
| #153 VP-GRID1 | `b1cd43d` | Grille A/B/H N=1 provisoire + VP2-R1 |
| #152 / #151 | … | CI tooltips / VP-FIX1 |

### Job en cours

**VP-J1 étape 1** — branche `cursor/vp-j1-a2fe`, PR **draft [#155](https://github.com/samiriggui-code/IchiVol/pull/155)** :

1. Ledger +12 hyps B6/B7 → **N proposé = 36**  
2. Définition J figée (Bj = max DSR_i B0–B6, tie → plus simple)  
3. Audit B6/B7 vs §2 (écarts listés, **pas de fix**)  
4. **STOP** — attendre validation N=36 + déf. J + écarts  

**Interdit** jusqu’à validation : runs, B3/B4/B8, retuning, CI/T-CYCLE.

## Méthode

1. Cursor : branche + PR draft + handoff → **STOP**.  
2. Claude : vrai diff + verdict.  
3. Pas de merge / étape 2 sans OK.

## Docs clés

| Fichier | Rôle |
|---------|------|
| [`docs/HANDOFF-CURSOR-V3.md`](docs/HANDOFF-CURSOR-V3.md) | Journal |
| [`docs/VP-T10B-LEDGER.md`](docs/VP-T10B-LEDGER.md) | N=24 gelé · N=36 proposé · déf. J · audit B6/B7 |
| [`docs/VP3-REPORT-GRID.md`](docs/VP3-REPORT-GRID.md) | Grille v2 NT1 |
| [`docs/vp3-artifacts/nt1_results.json`](docs/vp3-artifacts/nt1_results.json) | Artefact NT1 |
| [`docs/VALIDATION-PROTOCOL.md`](docs/VALIDATION-PROTOCOL.md) | VP0 §2 B6/B7 / §9 / §10 |
