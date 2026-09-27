# HANDOFF — Reprise du chantier IchiVol V3 en local

**LIS CE FICHIER EN PREMIER, avant tout autre fichier du repo.**

**Sync local :** 2026-09-26 soir · `main` @ **`7d0f5f4`** (= origin/main GitHub).

## Contexte

Tu (Claude, en local sur le PC de l'utilisateur) reprends le rôle de **superviseur**. **Cursor code, tu vérifies** (code + tests Postgres), tu valides ou tu corriges, puis tu donnes le prochain job. Ne fais pas confiance au seul compte-rendu Cursor sans vérifier le diff.

Canal partagé : **`docs/HANDOFF-CURSOR-V3.md`** — nouvelles entrées **en haut**, jamais effacées. Lis le bloc **« 2026-09-26 soir — SYNC LOCAL »** en premier.

## État au tip `7d0f5f4` (journée 2026-09-26)

### Mergé et gelé (features)

| Chantier | Tip / PR | Règle |
|----------|----------|-------|
| Chart Intelligence (+ briefing #133) | #124→#134 · `df013fb` | **GEL** features ; bugs/hotfixes OK |
| T-CYCLE V0 observe-only + P1–P6 | #123 · `9e2b02f` | **GEL** features ; bugs OK |
| VP0 protocole + AW0 | #140 · `34991b4` | **GEL DOC** — pas de rewrite sans version datée |
| AW1 « Pourquoi ? » | #143 · `7723e53` | MERGED |
| AG0 hygiène + filtre evidence | #144+#145 | MERGED |
| VP1 Vision freeze | #146 · `89e950a` | MERGED · `vp1/data/` gitignored |
| VP2 harness §6 / §1ter | #147 · `91c2795` | MERGED |
| VP3 B0–B7 + compare A/B/H | #148–#150 · **`7d0f5f4`** | MERGED · **aucun claim EDGE** |

### Rapport VP3 provisoire (à review)

[`docs/VP3-REPORT-BTCUSDT-1h.md`](docs/VP3-REPORT-BTCUSDT-1h.md) — BTCUSDT 1h · n_boot=10 000 · Q A/B/H toutes **`bi_beats_bj = false`**.

Pas d’EDGE : N T10b = 1 provisoire ; grille symbole×TF incomplète ; Q J (B7) non jouée.

### Aussi livré aujourd’hui (UI)

Landing V3 · Market TV plein écran · calques Structure/Fib/FVG · fixes mobile/dark Preuves·Pipeline · GOLDEN-RVOL pin Python 3.12 (#139).

## Prochain job (ordre)

1. ~~Review Claude du rapport VP3 A/B/H + tip `7d0f5f4`~~ **FAIT 2026-09-26 nuit** : #140/#143/#144/#145 validés ; **#146 VP1 critique** (timestamps µs 2025+ jetés → validation/holdout vides) ; VP2/VP3 à corriger (DSR σ, bootstrap stationnaire, force_flat par pli…). Détail : bloc « REVIEW Claude a posteriori » de `docs/HANDOFF-CURSOR-V3.md`.
2. **Cursor : VP-FIX1** (PR draft) → rebuild VP1 → rapport BTC 1h **v2** → STOP.
3. **Claude : revue VP-FIX1.** Décision utilisateur en attente : **VP2-R1** (time-stop 48 vs 49 barres).
4. Seulement après : grille **ETH/SOL · 4h · Q J (B7)** · figer **N T10b** · profil **adverse**.
5. Ne **pas** rouvrir features CI / T-CYCLE sans lever de gel explicite.

## Méthode (rappel strict)

1. Cursor : branche + PR draft + entrée handoff → stop.
2. Claude : fetch, **vrai diff**, tests Postgres.
3. Verdict **validé** / **à corriger** avant merge et avant job suivant.

**Incident connu :** merges en masse sans revue (passé). Rester vigilant.

## Setup tests Postgres

```bash
# engine
cd ichivol-app/engine
# DATABASE_URL = postgresql+psycopg://postgres:root@127.0.0.1:5432/ichivol_engine_dev
alembic upgrade head
python -m pytest tests -q -p no:cacheprovider --tb=short

# server
cd ../server && npm ci && npx prisma generate && npx prisma migrate deploy && npm test
```

VP3 replay (données VP1 locales requises) :

```bash
cd ichivol-app/engine
python -m vp3 compare --question A --symbol BTCUSDT --interval 1h --n-boot 10000
```

## Docs clés

| Fichier | Rôle |
|---------|------|
| [`docs/HANDOFF-CURSOR-V3.md`](docs/HANDOFF-CURSOR-V3.md) | Journal Cursor ↔ Claude |
| [`docs/VALIDATION-PROTOCOL.md`](docs/VALIDATION-PROTOCOL.md) | VP0 gelé |
| [`docs/AW0-CONSOLIDATION.md`](docs/AW0-CONSOLIDATION.md) | Consolidation AW0 |
| [`docs/VP3-REPORT-BTCUSDT-1h.md`](docs/VP3-REPORT-BTCUSDT-1h.md) | Rapport A/B/H du jour |
| [`docs/CAHIER-DES-CHARGES.md`](docs/CAHIER-DES-CHARGES.md) | CDC + checkboxes chantiers |
| [`docs/CYCLE_ENGINE_AUDIT.md`](docs/CYCLE_ENGINE_AUDIT.md) | T-CYCLE (observe-only) |

## Ancien backlog (hors file immédiate)

T0-MANAGE-d/e/f (paper / pyramiding), promotion T-CYCLE décision, Eve-piloted briefing — **après** file VP / review Claude.  
Le vieux focus T0-NOTIF (#44) n’est **plus** le travail en tête : la journée a basculé sur CI → T-CYCLE gel → VP0→VP3.
