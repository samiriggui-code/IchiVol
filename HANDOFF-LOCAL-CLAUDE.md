# HANDOFF — Reprise du chantier IchiVol V3 en local

**LIS CE FICHIER EN PREMIER, avant tout autre fichier du repo.**

**Sync local :** 2026-09-27 · `main` @ **`b1cd43d`** (= origin/main GitHub · squash #153 VP-GRID1).

## Contexte

Tu (Claude, en local sur le PC de l'utilisateur) reprends le rôle de **superviseur**. **Cursor code, tu vérifies** (code + tests Postgres), tu valides ou tu corriges, puis tu donnes le prochain job. Ne fais pas confiance au seul compte-rendu Cursor sans vérifier le diff.

Canal partagé : **`docs/HANDOFF-CURSOR-V3.md`** — nouvelles entrées **en haut**, jamais effacées. Lis d’abord **VP-NT1 étape 1** (ledger N), puis l’historique GRID1 / DÉCISIONS Claude.

## État au tip `b1cd43d`

### Mergé récemment

| PR | Tip | Contenu |
|----|-----|---------|
| #153 VP-GRID1 | `b1cd43d` | Grille A/B/H × BTC/ETH/SOL × 1h/4h + VP2-R1 + réserves Claude |
| #152 CI packs tooltips | `848f194` | Infobulles packs + fix StrictMode raf |
| #151 VP-FIX1 | `3223ec3` | Vision µs, DSR, bootstrap, WF, stop@raw, AG0 stream |
| #146–#150 VP1→VP3 | … | Voir handoff Cursor |

### Décision tranchée

**VP2-R1** : time-stop = 48 barres, **barre d’entrée = barre 1**. Clarification §12.

### Job en cours

**VP-NT1 étape 1** — branche `cursor/vp-nt1-a2fe`, PR **draft [#154](https://github.com/samiriggui-code/IchiVol/pull/154)** :

1. Ledger exhaustif → [`docs/VP-T10B-LEDGER.md`](docs/VP-T10B-LEDGER.md)  
2. **N proposé = 24** — **STOP** jusqu’à validation Claude + utilisateur  
3. **Étape 2 interdite** avant validation de N (rerun grille base+adverse)

**Interdit** jusqu’à validation N : Q J, adverse rerun, features CI/T-CYCLE, tuning.

## Méthode (rappel strict)

1. Cursor : branche + PR draft + entrée handoff → **STOP**.
2. Claude : fetch, **vrai diff**, tests Postgres.
3. Verdict **validé** / **à corriger** avant merge et avant job suivant.

## Setup tests Postgres

```bash
cd ichivol-app/engine
alembic upgrade head
python -m pytest tests -q -p no:cacheprovider --tb=short
```

VP grille (étape 2 seulement, après gel N) :

```bash
cd ichivol-app/engine
python -m vp3.grid_run /tmp/vp3_grid_results.jsonl 10000
```

## Docs clés

| Fichier | Rôle |
|---------|------|
| [`docs/HANDOFF-CURSOR-V3.md`](docs/HANDOFF-CURSOR-V3.md) | Journal Cursor ↔ Claude |
| [`docs/VALIDATION-PROTOCOL.md`](docs/VALIDATION-PROTOCOL.md) | VP0 + VP2-R1 §12 |
| [`docs/VP-T10B-LEDGER.md`](docs/VP-T10B-LEDGER.md) | Compteur N T10b (VP-NT1) |
| [`docs/VP3-REPORT-GRID.md`](docs/VP3-REPORT-GRID.md) | Grille A/B/H v1 (GRID1) |
| [`docs/VP3-REPORT-BTCUSDT-1h.md`](docs/VP3-REPORT-BTCUSDT-1h.md) | Historique v1/v2 ; v3 → GRID |
