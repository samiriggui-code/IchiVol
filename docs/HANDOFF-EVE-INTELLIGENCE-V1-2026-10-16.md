# Handoff — Ève Intelligence V1→V2 (session Cloud → local)

> **Pour :** session Cursor **locale** (reprise après `git pull`)  
> **De :** Cloud Agent (`bc-01a1455c-d7be-7c01-ba50-5330b20f8626`)  
> **Date :** 2026-10-16  
> **Branche :** `cursor/eve-intelligence-v1-8626`  
> **PR :** https://github.com/samiriggui-code/IchiVol/pull/178  
> **HEAD au handoff :** `e76fc34` (`feat(eve): Phase K Shadow en follow-up + calibration sur outcomes`)

**LIS CE FICHIER EN PREMIER** si tu reprends le chantier Ève après sync du repo.

---

## 0. Récupérer le travail

```bash
git fetch origin
git checkout cursor/eve-intelligence-v1-8626
git pull origin cursor/eve-intelligence-v1-8626
# ou depuis main :
# git fetch origin pull/178/head:cursor/eve-intelligence-v1-8626 && git checkout cursor/eve-intelligence-v1-8626
```

Tests rapides (engine) :

```bash
cd ichivol-app/engine
python3 -m pytest tests/eve tests/jev -q --noconftest
```

---

## 1. Mission (rappel)

Faire d’**Ève** l’intelligence centrale IchiVol (pas un assistant collé au pipeline) :

- Modes : **Analyst / Challenger / Guardian / Shadow** (une intelligence, pas 4 LLM)
- JEV System One : **NOUL / CHOICE / SCORE** via **jevos** (VPS) + **TypeSafe** (clé hébergée)
- Décisions stratégiques : **LONG / SHORT / HOLD / CLOSE / ABSTAIN**
- Dossiers + verdicts Postgres, cohérence documentée, calibration ≠ fine-tune LLM
- Paper via **portefeuilles existants** + **Risk Kernel** — **aucun portefeuille Eve**, **aucun trading réel**
- Autonomie paper **OFF par défaut** (`EVE_PAPER_AUTONOMY=false`)

**Ne pas confondre :**

| Terme | Signification |
|---|---|
| **Ève Shadow** | Mode JEV de contre-évaluation (`app/eve`, `app/jev/shadow.py`) |
| **ShadowBroker** | Contrefactuel Python quand un filtre bloque un trade (`app/shadow/`) |
| **OpenRouter / Sonnet** | Chat Copilot — **pas** System One |
| **jevos** | OSS System One local (`feder-cr/jev`) déjà sur VPS |
| **TypeSafe** | System One hébergé (clé officielle) |

---

## 2. Ce qui est livré (état actuel)

### Cycle couvert

| Phase | Statut | Où |
|---|---|---|
| A–G | **Fait** | Contexte FactSheet, modes, orchestrateur, dossiers/verdicts, cohérence, calibration policy |
| Étude Mode×primitive | **Fait** | Routage JEV calibré (pas 3 primitives partout) |
| H–I (Risk Kernel / paper) | **Scaffold V2** | Dry-run par défaut ; open seulement si autonomy ON |
| J (Suivi) | **Fait** | HOLD/CLOSE/ABSTAIN + `outcome_json` (PnL) |
| K (Shadow en suivi) | **Fait** | Shadow dans follow-up ; logué sur dossier |

### Routage JEV (après `primitive_study`)

| Mode | Primitives |
|---|---|
| Analyst | **SCORE** |
| Challenger | **NOUL + CHOICE** |
| Guardian | **NOUL + SCORE** |
| Shadow | **NOUL + CHOICE + SCORE** |

API étude : `GET /api/engine/eve/primitive-study`  
Policy : `app/eve/calibration.py` → `DEFAULT_POLICY.routing` (étude recalculée à l’import).

### Synthèse

`synthesize_action` consomme aussi Shadow :

- SCORE ≤ 1 → ABSTAIN  
- CHOICE ≠ action directionnelle → ABSTAIN  
- NOUL &lt; 0.35 → ABSTAIN  

### Paper V2 (gaté)

- Flag : `EVE_PAPER_AUTONOMY` / `settings.eve_paper_autonomy` (**default false**)
- Hard gate : même `execute=true` ne ouvre **rien** si autonomy off
- LONG/SHORT → `risk_kernel.evaluate` → `open_user_confirmed` (portefeuille existant)
- CLOSE → `close_manually`
- HOLD / ABSTAIN → skip
- Prix/stop : facts dossier → **screener** live
- `POST /eve/evaluate/{symbol}?persist=true` → dry-run RK **auto**

### Phase J/K

- Follow-up déterministe (Guardian + MAE/MFE + Shadow)
- `outcome_json` : followups + closed PnL/frais — **jamais** réécrit `decision_time_json`
- Calibration : `observe_from_dossiers` → `propose_adjustment` (**jamais auto-appliqué**)

---

## 3. Carte des fichiers

### Engine — Ève

```
ichivol-app/engine/app/eve/
  actions.py           # LONG|SHORT|HOLD|CLOSE|ABSTAIN
  context.py           # FactSheet → contexte moteurs
  modes.py             # Analyst/Challenger/Guardian/Shadow + synthesize_action
  orchestrator.py      # evaluate_opportunity (+ paper_dry_run)
  dossier.py           # EveDossier / EveVerdict persist
  coherence.py         # Indice cohérence (≠ JEV score)
  calibration.py       # Policy + observe + propose (≠ finetune)
  primitive_study.py   # Matrice Mode × NOUL/CHOICE/SCORE
  paper_submit.py      # V2 Risk Kernel / CLOSE (flag autonomy)
  followup.py          # Phase J/K suivi + outcomes
```

### Engine — JEV

```
ichivol-app/engine/app/jev/
  adapter.py / providers.py / questions.py / normalize.py
  shadow.py            # compare_decision = NOUL+CHOICE+SCORE
  history.py / client.py
```

### API

`ichivol-app/engine/app/api/eve.py` — préfixe `/api/engine/eve`

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/context/{symbol}` | Contexte |
| POST | `/evaluate/{symbol}` | Cycle modes → verdict (+ dry-run RK si persist) |
| GET | `/dossiers`, `/dossiers/{id}` | Lecture |
| GET | `/verdicts/{id}` | Lecture |
| GET | `/calibration` | Policy + observed + proposal |
| GET | `/primitive-study` | Étude routage |
| GET | `/paper-autonomy` | Flag V2 |
| POST | `/dossiers/{id}/paper-submit` | Dry-run / open (si autonomy) |
| GET | `/followup` | Positions trackées |
| GET/POST | `/dossiers/{id}/followup` | Propose / apply CLOSE dry-run |
| POST | `/outcomes/sync` | Remplit outcomes CLOSED |

### Agent channel

`get_eve_context`, `evaluate_eve`, `list_eve_dossiers`, `get_eve_dossier`,  
`get_eve_paper_autonomy`, `submit_eve_paper` (**toujours dry-run**),  
`list_eve_followup`, `run_eve_followup`, `sync_eve_outcomes`, `eve_calibration_report`

### Frontend

- `EveIntelligencePanel.tsx` — modes, dossiers, dry-run, follow-up, calib stats  
- `EveShadowPanel.tsx` — historique NOUL + CHOICE + SCORE  
- Branchés depuis `AgentsPage.tsx`

### Modèles / migration

- `EveDossier`, `EveVerdict` dans `app/db/models.py`  
- Alembic : `k7l8m9n0o1p2_eve_dossiers_verdicts.py`

### Tests

```
ichivol-app/engine/tests/eve/   # calibration, context, modes, paper, followup, study, synthesize
ichivol-app/engine/tests/jev/   # adapter, shadow_mode, …
```

---

## 4. Env / flags utiles

| Variable | Défaut | Effet |
|---|---|---|
| `JEV_PROVIDER` | `jevos` | `jevos` \| `typesafe` |
| `JEV_URL` | jevos local/VPS | Base URL System One |
| `JEV_API_KEY` / `TYPESAFE_API_KEY` | — | Auth |
| `JEV_SHADOW_ENABLED` | `false` | Route legacy shadow HTTP |
| **`EVE_PAPER_AUTONOMY`** | **`false`** | Seul moyen d’ouvrir/fermer paper via Eve |

Config : `app/config.py` → `eve_paper_autonomy: bool = False`

---

## 5. Commits sur la branche (ordre)

1. `e705ec9` — Adaptateur JEV jevos + TypeSafe  
2. `e942130` — V1-B→G modes, dossiers, UI  
3. `e565781` — chore cleanup  
4. `443758f` — Étude Mode×primitive → routage  
5. `4166ca4` — Synthèse Shadow CHOICE/SCORE + scaffold paper RK  
6. `9921173` — CLOSE/HOLD, screener, dry-run auto, agent+UI  
7. `8ed89a2` — Phase J follow-up + outcomes  
8. `e76fc34` — Phase K Shadow + calibration observe  

---

## 6. Contraintes absolues (ne pas casser)

1. **Ne pas** modifier la baseline déterministe / combiner.  
2. **Ne pas** créer de portefeuille « Eve ».  
3. **Ne pas** activer le trading réel.  
4. Risk Kernel + kill switch restent **impératifs** (Guardian = advisory).  
5. JEV ≠ autorisation de risque.  
6. Calibration ≠ fine-tune LLM ; `decision_time` ≠ outcome (jamais backfill).  
7. Agent channel : **jamais** d’open/close réel (dry-run forcé sur `submit_eve_paper`).

---

## 7. Comment enchaîner en local (suggestions ordonnées)

### A. Valider l’existant (obligatoire avant new work)

1. Pull branche + `pytest tests/eve tests/jev -q --noconftest`  
2. Migration alembic si DB locale pas à jour (`k7l8m9n0o1p2`)  
3. Smoke API :  
   - `GET /api/engine/eve/calibration`  
   - `GET /api/engine/eve/primitive-study`  
   - `POST /api/engine/eve/evaluate/BTCUSDT?persist=true&use_jev=false`  
   - `GET /api/engine/eve/paper-autonomy` → doit être `false`

### B. Prochaines briques produit (pas encore faites)

| Priorité | Item | Notes |
|---|---|---|
| 1 | **Paper autonomy contrôlée** (staging only) | Activer `EVE_PAPER_AUTONOMY=true` sur un env paper ; journaliser ; kill switch armé → vérifier refus |
| 2 | **Boucle mesure** | Comparer baseline vs Eve (avec/sans JEV) sur mêmes symboles ; win-rate net frais déjà dans observe |
| 3 | **Mémoire / historique UI** | Timeline dossier (decision_time → followups → outcome) plus lisible |
| 4 | **V3 configs** | jevos vs TypeSafe, coûts, régimes — brief §19 V3 |
| 5 | **Ajustement autorisé** | Phase J mentionne « ajustement » (trail/partial) — pas encore branché protection Eve |

### C. Pièges connus

- `evaluate` avec `use_jev=true` sans clé/jevos → modes skip JEV ou erreurs provider ; tester d’abord `use_jev=false`.  
- Dry-run RK sans prix → `missing_price` si screener down ; passer `price=` / `stop_distance=`.  
- Import privé `_shadow_answers` utilisé par `followup.py` depuis `modes.py` — OK tant que pas de cycle.  
- `compare_decision` (legacy) envoie maintenant **3** primitives ; mocks tests doivent répondre CHOICE+SCORE.

---

## 8. Points de décision pour Samir

1. Merger **#178** en draft/review tel quel, ou attendre un run paper autonomy sur VPS ?  
2. Quand activer `EVE_PAPER_AUTONOMY` (jamais en prod live) ?  
3. Priorité suivante : **mesure comparative** vs **UI timeline dossier** vs **ajustements protection** ?

---

## 9. Message court pour démarrer la session locale

> Branche `cursor/eve-intelligence-v1-8626` / PR #178.  
> Ève V1 (modes+JEV+dossiers) + V2 paper dry-run (flag off) + Phase J/K follow-up/Shadow + calibration observe.  
> Autonomie paper **off**. Pas de portefeuille Eve. Pas de live.  
> Lire `docs/HANDOFF-EVE-INTELLIGENCE-V1-2026-10-16.md`, pull, pytest `tests/eve`+`tests/jev`, puis enchaîner sur la priorité Samir (§7–§8).

---

*Fin du handoff Cloud → local — 2026-10-16.*
