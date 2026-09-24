# T10e — Critères de promotion FeatureStatus

**Statut** : document only.  
**Portée** : passage `CANDIDATE` → `VALIDATED` / `PRODUCTION` / `REJECTED`.  
**Non-but** : aucun code de promotion automatique ; le Lab ne mute jamais le registre.

---

## 1. Principes

1. **Lab ≠ promote.** `ablation_oos.decide_recommendation` → `review_candidate` | `inconclusive` | `reject` est un **signal de revue**, pas une écriture de statut.
2. **Humain only.** Changement de `FeatureStatus` = décision Claude + utilisateur (PR dédiée, une feature à la fois).
3. **Garanties live.** `decision/pipeline` et `decision/combiner` ne doivent importer que des indicateurs `PRODUCTION` (garde T11a-bis). Promouvoir en PRODUCTION implique une revue d’imports et de wiring explicite.
4. **Observation first.** Tant qu’un indicateur est CANDIDATE / EXPERIMENTAL / REJECTED, il reste calculable Lab / context API selon le registre — **sans vote** dans le combiner live.

---

## 2. Prérequis avant toute promotion

| # | Prérequis | Preuve |
|---|-----------|--------|
| 1 | **Fiche T10d** à jour (`docs/research/<id>.md`) | Lien dans la PR de statut |
| 2 | **T9g-fix** sur ≥ 1 étude pertinente | `review_candidate` (ou justification écrite si on promeut malgré `inconclusive`) |
| 3 | Gates T9g respectés | `min_oos_trades` (défaut 30, `min(base,var)`), majorité stricte de plis Δ exp OOS > 0, coûts adverses 10/8 bps Δ > 0, PF OOS Δ ≥ 0 |
| 4 | **T10b** lineage noté | `hypothesis_id` + `lineage_trial_count` (ou absence documentée) |
| 5 | **T10c** redondance revue | Chevauchement vs PRODUCTION de la même famille (ex. CMF vs CVD) |
| 6 | **Histoire** | Warning si &lt; 1 an ; idéal deep_history ≥ 2 ans crypto quand la feature trade des cassures / flux |
| 7 | **Pas de lookahead** | Test registry / troncature dédié déjà vert pour l’id |

Sans (1)+(2)+(5)+(7) → **pas de PR PRODUCTION**.

---

## 3. Échelle de statuts

| Statut | Signification | Wiring live |
|--------|---------------|-------------|
| `EXPERIMENTAL` | Lab / chart only | Interdit dans pipeline/combiner |
| `CANDIDATE` | Hypothèse documentée (T10d) | Context / Lab OK ; pas de vote combiner |
| `VALIDATED` | Critères T10e OK, **pas encore** dans le chemin décision | Optionnel ; peut rester inutilisé |
| `PRODUCTION` | Autorisé sur le chemin décision | Import garde + wiring explicite |
| `REJECTED` | Ne pas promouvoir ; Lab encore calculable si utile | `experiment_refs` vers la revue |

### Chemin recommandé

```
EXPERIMENTAL → CANDIDATE (fiche T10d)
            → review_candidate (T9g) + redondance OK
            → [VALIDATED] optionnel
            → PRODUCTION (PR humaine)  OU  REJECTED (fiche + refs)
```

---

## 4. Critères PRODUCTION (checklist PR)

- [ ] Fiche T10d : décision « proposer PRODUCTION » + owners
- [ ] Au moins une étude OOS avec `review_candidate` **ou** argument écrit accepté par Claude
- [ ] Redondance : n’ajoute pas un doublon strict d’un PRODUCTION existant sans valeur marginale documentée
- [ ] Params par défaut stables ; pas de grille magique non testée
- [ ] Wiring proposé (où dans pipeline / evidence / agents) — **diff séparé** si non trivial
- [ ] Garde d’imports reste verte
- [ ] Aucun changement de seuils live « parce que T12e l’a suggéré » sans décision utilisateur

---

## 5. Critères REJECTED

- T9g `reject` répété sur l’univers cible, **ou**
- Lookahead / fuite, **ou**
- Redondance totale vs un PRODUCTION plus simple, **ou**
- Revue humaine (ex. PPO / BEST Cloud / Wyckoff)

Documenter dans la fiche + `experiment_refs` sur la définition registre.

---

## 6. Lien T12e / KEEP

Verdict étude **KEEP** = `review_candidate` T9g → **candidat à fiche T10d**, pas à merge PRODUCTION.  
Voir `docs/ETUDE-T12-ADN-ICHIVOL.md`.

---

## 7. Arrêts (rév.58)

- Pas de promotion automatique
- Pas de modification des règles / seuils de décision LIVE sans l’utilisateur
- LLM sans autorité sur une action de trading ni sur un `FeatureStatus`
