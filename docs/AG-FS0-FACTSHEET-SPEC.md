# AG-FS0 — FactSheet + validateur de sortie (Eve / Copilot)

**Statut :** spec Claude, 2026-09-28, validée dans son principe par Samir (« vas-y »). À implémenter en **1 PR draft → STOP → revue Claude**. Aucun déploiement sans OK de Samir.
**Origine :** audit « agents / skills financiers » du 2026-09-28. Conclusion : pas d'armée d'agents. On garde un orchestrateur unique (Eve), des spécialistes **déterministes** (moteurs Python et fiches AG-S1) et **un** appel LLM, contrôlé.

**Objectif :** Eve ne peut plus affirmer un chiffre, un niveau ou un état qui ne vient pas d'un moteur IchiVol, et chaque affirmation se retrace jusqu'au moteur, au timeframe et à l'instant.

**Hors périmètre de FS-0 :**
- règles de contradiction (FS-1, avec AG-S2) ;
- annotations sur le graphique (FS-2) ;
- Trade Reviewer (FS-3) ;
- adaptateur multi-fournisseurs complet ;
- MCP ;
- earnings / fondamentaux.

---

## 1. FactSheet (moteur Python, déterministe, aucun LLM)

**Module** `engine/app/agents/factsheet.py`. **Route** `GET /api/engine/agents/factsheet?symbol=&timeframe=&as_of=`. **Outil** `agent_channel` `get_factsheet` (`read_only=True`).

**Sources, réutilisées sans recalcul :**
1. `build_analyst_cards` (AG-S1) : une fiche par indicateur avec `value`, `state`, `known_at`, `feature_status`, `decision_role`, `stage`.
2. La décision du pipeline pour `(symbol, tf)` : verdict et statut de chaque étape. **Barres closes seulement.**
3. L'état paper pour le symbole : position ouverte ou non, entrée, stop, taille, P&L latent ; verrous de risque (kill-switch, perte journalière).
4. Le prochain événement macro d'impact « High » (`context/calendar.py`) : titre, heure, minutes restantes.

**Schéma (v1) :**

```json
{
  "schema": "ichivol.factsheet.v1",
  "factsheet_id": "sha256 du JSON canonique (sans generated_at)",
  "symbol": "BTCUSDT", "timeframe": "1h", "as_of": 1790000000,
  "generated_at": "ISO", "engine_version": "…",
  "facts": [
    {
      "id": "rvol.value",
      "engine": "rvol", "field": "value", "value": 1.82, "unit": "x",
      "timeframe": "1h", "as_of": 1790000000, "known_at": 1790000000,
      "source": "engine|provider|paper|calendar",
      "status": "ok|unavailable|stale|engine_absent",
      "validation_status": "NON_VALIDE|VALIDE", "decision_role": "…",
      "display": "1,82"
    }
  ],
  "missing": [{"id": "cvd.value", "reason": "provider_no_taker_volume"}]
}
```

**Règles :**
- **Les ids sont stables et lisibles** (`<engine>.<field>`), identiques d'un appel à l'autre.
- **Une donnée absente est un fait à part entière** : `status != ok`, `value = null`, raison fournie. On ne l'omet jamais en silence.
- **`display`** est la forme **exacte** que le LLM peut citer : format FR, décimales du moteur.
- **Causal** : rien ne dépasse `as_of` ; même troncature que AG-S1.
- **`validation_status`** reprend le verdict VP : tous les signaux du pipeline sont `NON_VALIDE` (VP3 : 0 edge / 48).
- **Taille :** ≤ 60 faits, JSON compact. Viser ≤ 4 000 tokens.

## 2. Appel LLM (serveur, un seul appel, sans boucle d'outils)

- **Modes concernés :** `explain_decision` et `explain_signal` du Copilot, symboles crypto. Les autres modes gardent le chemin actuel.
- **Flag** `AGENT_FACTSHEET_V1=1`, désactivé par défaut. L'ancien chemin reste comme repli.
- **Entrée :**
  - prompt système ;
  - skills `.md` du domaine, via `loadSkills`, placés dans le bloc mis en cache (prompt caching) ;
  - le FactSheet en JSON ;
  - la question.
- **Pas d'outils moteur** dans FS-0 : tout est dans le FactSheet. C'est le plus simple, le moins cher et le plus prévisible.
- **Sortie forcée** par un outil `submit_analysis` (`tool_choice` imposé). Schéma :

```json
{
  "summary": "2–4 lignes",
  "claims": [
    {"text": "…", "kind": "fact|interpretation|scenario|missing", "fact_ids": ["rvol.value"]}
  ],
  "risks": [ {"text": "…", "fact_ids": ["…"]} ],
  "invalidation": [ {"text": "…", "fact_ids": ["…"]} ],
  "missing_data": ["cvd.value"]
}
```

- **Consignes dans le prompt :**
  - citer les valeurs **telles que `display`** ;
  - `kind=fact` exige au moins un `fact_ids` ;
  - si une donnée manque, le dire (`kind=missing`) au lieu de la déduire ;
  - toujours rappeler `NON_VALIDE` quand on cite un signal du pipeline.
- **Modèle :** `LLM_MODEL` inchangé côté configuration. **Relever le défaut** (`claude-sonnet-4-5`, obsolète) vers `claude-sonnet-5`. Budget : 1 appel, `max_tokens` ≤ 1 200.

## 3. Validateur (serveur TS, `agent/factsheetValidate.ts`)

Pour chaque claim, risque et invalidation :

1. **Chaque `fact_ids` existe** dans le FactSheet.
2. **`kind=fact` a au moins un id**, et chacun de ces faits a `status=ok`.
3. **Chaque nombre du texte** est rattaché à un fait cité : `display` exact, ou `value` à une tolérance près (arrondi à la précision affichée, ou écart relatif ≤ 0,5 %).
   - Nombres reconnus : format FR/EN, `%`, `k`, signes, prix.
   - **Exemptions** (liste figée, testée) : libellés de timeframe (`1h`, `4h`, `1d`), noms d'indicateurs (`ATR 14`, `RSI 14`, `Donchian 55`), dates et heures issues d'un fait cité.
4. **Un fait `status != ok`** ne peut être cité que dans un claim `kind=missing`.

**Résultat :** `ok` / `rejected` par claim, plus un rapport.

- **Claim rejeté :** retiré de l'affichage et journalisé.
- **Plus de 30 % de rejets :** **1 seul** nouvel essai, avec la liste des erreurs. S'il échoue encore, afficher « Réponse partielle : N affirmations non vérifiables retirées ».
- **Aucun claim valide :** afficher le FactSheet brut (les 5 portes), sans texte LLM.

## 4. Trace

Dans les métadonnées d'`AgentMessage` :
- `factsheet_id` et le FactSheet sérialisé (ou son hash + le stockage si c'est trop gros) ;
- `schema` ;
- version du prompt et skills chargés ;
- modèle ;
- tokens (entrée, sortie, cache) ;
- rapport du validateur ;
- nombre d'essais.

Le but : rejouer n'importe quelle réponse à l'identique à partir de la trace.

## 5. UI (minimale)

- Réponse d'Eve affichée en **claims**. Chaque claim porte des puces de faits (`RVOL 1,82 · 1h · 14:00`). Un clic ouvre le détail : moteur, champ, `as_of`, `known_at`, statut, `NON_VALIDE`.
- Un badge « N affirmations retirées (non vérifiables) » quand c'est le cas.
- Aucun nouvel écran : on reste dans le Copilot existant.

## 6. Tests exigés

**Moteur :**
- déterminisme (même entrée → même `factsheet_id`) ;
- troncature (`as_of` = T → identique si les données continuent) ;
- fournisseur sans taker volume → `cvd.value` `unavailable` ;
- symbole sans position → faits paper `ok` avec `value=null`, pas d'erreur ;
- calendrier en panne → `unavailable`.

**Validateur :**
- nombre inventé → rejet ;
- valeur arrondie correcte → ok ;
- `1,82` contre `1.82` → ok ;
- `%` ;
- fait `unavailable` cité comme fact → rejet ;
- id inconnu → rejet ;
- exemptions (`1h`, `ATR 14`) → ok ;
- seuil de 30 % → un seul nouvel essai.

**Bout en bout :** LLM simulé (réponse propre, réponse avec 1 chiffre inventé, réponse vide) → affichage attendu.

**Non-régression :**
- flag désactivé → comportement identique à aujourd'hui ;
- goldens OpenAPI / `route_order` : ajout documenté de `GET /agents/factsheet` ;
- `pytest` (Postgres) + `npm test` + `npx tsc -b`.

**Preuve PR :**
- un FactSheet réel BTCUSDT 1h (JSON) ;
- 2 réponses réelles d'Eve avec leur rapport de validation ;
- capture du Copilot (clair, desktop + mobile 390 px).

## 7. Suite (dans l'ordre, chacun sa PR)

| Étape | Contenu | Condition |
|---|---|---|
| **FS-1** | Contradictions **déterministes** en Python (prix / CVD, cassure / RVOL faible, événement macro « High » < 30 min) dans le FactSheet (`contradictions[]`) et le brief AG-S2 | Après FS-0 |
| **FS-2** | Annotations d'Eve sur le graphique via les outils `draw_*` existants, chacune avec `fact_ids`, calque « Eve » effaçable | Après FS-0 |
| **FS-3** | Trade Reviewer à la clôture d'une position paper (FactSheet à l'entrée + à la sortie + prix après), sortie = **proposition d'hypothèse** pour le Lab, jamais un changement de règle | Après FS-0 |
| **Plus tard** | Order flow (après OF-0) ; earnings / fondamentaux (données payantes + périmètre actions) ; plusieurs agents en parallèle (seulement si un besoin est mesuré) | Décision de Samir |
