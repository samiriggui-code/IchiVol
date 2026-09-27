# HANDOFF — Reprise du chantier IchiVol V3 en local

**LIS CE FICHIER EN PREMIER, avant tout autre fichier du repo.**

**Sync local :** 2026-09-27 · `main` @ **`848f194`** (= origin/main GitHub).

## Contexte

Tu (Claude, en local sur le PC de l'utilisateur) reprends le rôle de **superviseur**. **Cursor code, tu vérifies** (code + tests Postgres), tu valides ou tu corriges, puis tu donnes le prochain job. Ne fais pas confiance au seul compte-rendu Cursor sans vérifier le diff.

Canal partagé : **`docs/HANDOFF-CURSOR-V3.md`** — nouvelles entrées **en haut**, jamais effacées. Lis le bloc **« DÉCISIONS Claude »** (~22h45) puis l’entrée **VP-GRID1** en premier.

## État au tip `848f194`

### Mergé récemment

| PR | Tip | Contenu |
|----|-----|---------|
| #151 VP-FIX1 | `3223ec3` | Vision µs, DSR, bootstrap stationnaire, WF, stop@raw, AG0 stream |
| #152 CI packs tooltips | `848f194` | Infobulles packs (exception gel) + fix StrictMode raf |
| #146–#150 VP1→VP3 | … | Voir handoff Cursor |

### Décision tranchée

**VP2-R1** (2026-09-26 ~22h45) : time-stop = 48 barres, **barre d’entrée = barre 1** → sortie `entry+(n−1)·bar`. Clarification §12 (pas nouvelle règle).

### Job en cours

**VP-GRID1** — branche `cursor/vp-grid1-a2fe`, PR **draft** (pas de merge sans verdict Claude) :

1. VP2-R1 dans `sim.py` + test + note §12  
2. Rebuild ETH/SOL (+ BTC) 1h/4h/1d + sha256  
3. Grille A/B/H BTC/ETH/SOL × 1h/4h → [`docs/VP3-REPORT-GRID.md`](docs/VP3-REPORT-GRID.md)  
4. **Interdit** dans la PR : Q J, figer N T10b, adverse, features CI/T-CYCLE  

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

VP grille :

```bash
cd ichivol-app/engine
python -m vp3.grid_run /tmp/vp3_grid_results.jsonl 10000
```

## Docs clés

| Fichier | Rôle |
|---------|------|
| [`docs/HANDOFF-CURSOR-V3.md`](docs/HANDOFF-CURSOR-V3.md) | Journal Cursor ↔ Claude |
| [`docs/VALIDATION-PROTOCOL.md`](docs/VALIDATION-PROTOCOL.md) | VP0 + clarification VP2-R1 §12 |
| [`docs/VP3-REPORT-GRID.md`](docs/VP3-REPORT-GRID.md) | Grille A/B/H (GRID1) |
| [`docs/VP3-REPORT-BTCUSDT-1h.md`](docs/VP3-REPORT-BTCUSDT-1h.md) | Historique v1/v2 ; v3 → GRID |
