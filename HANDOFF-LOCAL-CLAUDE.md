# HANDOFF — Reprise du chantier IchiVol V3 en local

**LIS CE FICHIER EN PREMIER, avant tout autre fichier du repo.**

**Sync local :** 2026-09-28 nuit (voir REPRISE DEMAIN) · ancien : 2026-09-27 soir · `main` @ **`99ae3e4`** (+ ce commit handoff).

## ▶ REPRISE DEMAIN — commencer ici

Samir reprend exactement là où on s'est arrêté le 2026-09-28 dans la nuit. Lire **en premier** le bloc « 2026-09-28 nuit — ARRÊT DE SESSION » en haut de `docs/HANDOFF-CURSOR-V3.md`.

**Où on en est :**
- VP3 clos (0 EDGE / 48). Le paper fidèle (#159) perd −62,5 % en développement.
- Samir a lancé le **chantier RS** (stratégie alternative), piloté par Claude local.
- Specs pré-enregistrées (#160).
- **Code RS-D1 Donchian 4h en cours** sur `claude/rs-d1` (`34c1d5c`, non testé).

**Première action demain :** données ETH/SOL 4h (`python -m vp1 download-spot` puis `build-spot`) → note d'implémentation → tests `tests/rs/` → `rs/run.py` → run → rapport RS-D1.

**Idées notées pour après RS-D1 :** variables microstructure testables en historique gratuit, chacune ajoutée **une à la fois** par-dessus RS-D1 et pré-enregistrée :
- OI et ratios long/short en 5 min (Vision `metrics`, depuis fin 2021) ;
- funding ;
- CVD (déjà calculé, jamais utilisé dans les décisions) ;
- offre de stablecoins (DefiLlama).

Les liquidations n'ont pas d'historique gratuit. L'IA sert au contexte des actualités, **pas** de signal testable.

**Autre session Claude :** `ichivol-cd`, responsable de #159 et #161 ; elle doit prévenir quand v2 sera poussé. Pour lui écrire : `ListAgents` puis `SendMessage`.

## Contexte

Tu (Claude, en local) supervises. **Cursor code, tu vérifies.** Canal : [`docs/HANDOFF-CURSOR-V3.md`](docs/HANDOFF-CURSOR-V3.md). Lis en premier le bloc **« 2026-09-27 soir — Claude : VP3 CLÔTURÉ »**.

## État

- **VP3 clôturé** : #151→#155 mergés et revus. **0 EDGE / 48.** B0 (buy & hold) fait mieux presque partout ; B7 (pipeline live) ne bat rien. Rapport : [`docs/VP3-REPORT-FINAL.md`](docs/VP3-REPORT-FINAL.md).
- **Programme VP en PAUSE** (décision de Samir) : on n'ouvre ni la validation 2025 ni le holdout 2026 ; pas de VP4 à VP9.
- **Paper trading** : inchangé, il continue.
- **Gels actifs** : Chart Intelligence (features), T-CYCLE (features), VP0 (doc).

## Prochain job (ordre)

1. **Séance de réflexion stratégie Claude + Samir (sans code).** Piste principale : timing de sortie / mise à l'abri (rester investi, sortir en régime baissier ; viser un drawdown bien plus faible que B0 pour un rendement proche). Chaque idée retenue = nouvelle hypothèse T10b (N=37…).
2. **UI-VP-BADGE** (APPROUVÉ, lancé chez Cursor) : badge « Signal non validé — VP3 : pas d'edge mesuré » sur les verdicts ACHAT/VENTE. Affichage seulement.
3. **Avant tout déploiement VPS** : traiter #142 (CSS mobile qui tourne en prod mais n'est pas mergé).

## Méthode (rappel strict)

1. Cursor : branche + PR draft + entrée handoff → **STOP**.
2. Claude : vrai diff + tests Postgres → verdict écrit dans le handoff.
3. Pas de merge sans verdict Claude (et OK de Samir pour les décisions de fond).

## Setup tests

```bash
cd ichivol-app/engine
.venv/Scripts/python -m pytest tests -q -p no:cacheprovider --tb=short
cd ../server && npm test
```

Échecs connus sous Windows local : `test_p1_study_budget_limit500_under_20s` (budget CPU dépassé sur cette machine).

## Docs clés

| Fichier | Rôle |
|---------|------|
| [`docs/HANDOFF-CURSOR-V3.md`](docs/HANDOFF-CURSOR-V3.md) | Journal Cursor ↔ Claude |
| [`docs/VP3-REPORT-FINAL.md`](docs/VP3-REPORT-FINAL.md) | Verdict VP3 (0 EDGE / 48) |
| [`docs/VP-T10B-LEDGER.md`](docs/VP-T10B-LEDGER.md) | Registre des hypothèses, N=36 |
| [`docs/VALIDATION-PROTOCOL.md`](docs/VALIDATION-PROTOCOL.md) | Protocole VP0 (gelé) |
| [`docs/CAHIER-DES-CHARGES.md`](docs/CAHIER-DES-CHARGES.md) | CDC + cases à cocher des chantiers |

## Backlog hors file immédiate

T0-MANAGE-d/e/f (prise partielle / pyramiding), promotion de T-CYCLE, T8 brokers, réactivation des shorts (5 conditions) : **après** la réflexion stratégie.
