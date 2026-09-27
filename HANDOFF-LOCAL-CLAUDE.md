# HANDOFF — Reprise du chantier IchiVol V3 en local

**LIS CE FICHIER EN PREMIER, avant tout autre fichier du repo.**

**Sync local :** 2026-09-27 · branche `cursor/vp-nt1-a2fe` (PR draft [#154](https://github.com/samiriggui-code/IchiVol/pull/154)) · tip run VP-NT1 étape 2 DONE.  
**main** reste @ `b1cd43d` (#153) jusqu’au merge #154.

## Contexte

Tu (Claude, en local) supervisues. **Cursor code, tu vérifies**. Canal : [`docs/HANDOFF-CURSOR-V3.md`](docs/HANDOFF-CURSOR-V3.md) — lire **VP-NT1 étape 2 DONE** en premier.

## État VP-NT1

| Item | Statut |
|------|--------|
| N T10b | **24 GELÉ** (Claude + utilisateur) |
| Ledger + contamination pré-gel | OK |
| `nt1_run` DSR barre + §9 | OK @ `da6b5bb` |
| Run base+adverse n_boot=10k | DONE |
| Rapport GRID **v2** | [`docs/VP3-REPORT-GRID.md`](docs/VP3-REPORT-GRID.md) |
| JSON | [`docs/vp3-artifacts/nt1_results.json`](docs/vp3-artifacts/nt1_results.json) |
| Verdict | **0 EDGE** · PAS D'EDGE / NON CONCLUANT |

**STOP :** #154 draft — pas de merge sans OK final Claude.

### Interdit jusqu’à nouveau job

Q J (B7) · B3/B4/B6 · retuning · features CI/T-CYCLE · décider sur val 2025 / holdout.

## Setup tests Postgres

```bash
cd ichivol-app/engine
alembic upgrade head
python -m pytest tests -q -p no:cacheprovider --tb=short
```

VP-NT1 rejeu :

```bash
cd ichivol-app/engine
python -m vp3.nt1_run /tmp/vp3_nt1_results.jsonl 10000
```

## Docs clés

| Fichier | Rôle |
|---------|------|
| [`docs/HANDOFF-CURSOR-V3.md`](docs/HANDOFF-CURSOR-V3.md) | Journal Cursor ↔ Claude |
| [`docs/VALIDATION-PROTOCOL.md`](docs/VALIDATION-PROTOCOL.md) | VP0 + VP2-R1 §12 |
| [`docs/VP-T10B-LEDGER.md`](docs/VP-T10B-LEDGER.md) | N=24 + contamination Lab |
| [`docs/VP3-REPORT-GRID.md`](docs/VP3-REPORT-GRID.md) | Grille v2 (NT1) |
| [`docs/vp3-artifacts/nt1_results.json`](docs/vp3-artifacts/nt1_results.json) | Artefact run |
