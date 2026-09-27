# RS-00 — Revue indépendante de la PR #159 (VP-P, paper fidèle)

**Relecteur :** Claude local, pilote du chantier RS (2026-09-28). **Auteur de #159 :** l'autre session Claude, qui reste responsable des corrections.
**Tip relu :** `claude/vp-p-paper-fidele` @ `d218df4` (amendements `VP0-2026-09-27b` + `VP0-2026-09-28`, code `vpp/`, options `sim.py`, rapport v1).
**Tests (Windows, Postgres dev) :** `tests/vpp`, `tests/vp2`, `tests/vp3`, `tests/research_lab` → **tous verts**.

## Verdict

**Travail solide ; merge après les corrections R1–R3 et l'exécution de C2 / C3** (critères déjà pré-enregistrés dans `VP0-2026-09-28`).

- Le simulateur est fidèle et prudent :
  - options opt-in (`levels_anchor=fill`, `gate_equity=cost`, `min_fill_fraction`, `cost_by_symbol`), défauts inchangés (VP antérieurs identiques) ;
  - excursions mesurées seulement sur la partie de la barre de sortie connue avant la sortie ;
  - verrou journalier aligné sur le live.
- Sur la barre d'entrée, `high_seen` / `low_seen` couvrent toute la barre après l'open : correct, puisque l'entrée se fait à l'open.

## Vérifié sur les 5 points demandés par Samir

| Point | État dans #159 | Statut |
|-------|----------------|--------|
| Concordance ciblée sur les BUY | C1 : 300/300, mais **3 BUY seulement**. C2 (BUY stratifiés, cas limites, étape unique bloquante) pré-enregistré, **pas encore exécuté** | ⏳ C2 requis avant merge |
| 2R vs MFE | Écart 857 vs 22 % expliqué (flottants) ; tolérance `ε = 1e-9 R` et ancrage MFE sur le fill pré-enregistrés (Q.1) | ✅ définition ; ⏳ rejeu v2 |
| Tailles, capital commun, exécution | Code conforme à `risk.size_position` / `estimate_equity` ; C3 (rejeu via le **vrai** `sync_position` sur 3 fenêtres) pré-enregistré, **pas encore exécuté** | ⏳ C3 requis avant merge |
| Navigation screener vs opérations automatiques | Documentée (scans UI 15m/4h/1d → positions ; 20 positions sur 43 la 1ʳᵉ semaine hors cœur systématique) ; non reproductible, **à juste titre** | ✅ constat ; décision produit = Samir (voir R4) |
| Conclusions statistiques | Globalement prudentes ; **deux formulations trop fortes** | ❌ R1, R2 |

## Corrections à transmettre à la session #159

**R1 — Surinterprétation sur les sorties (importante).**
Deux phrases vont au-delà des données :
- « Aucune sortie ne peut transformer un signal sans information en gain » (En bref et §5) ;
- « Modifier les sorties … ne ferait que remodeler la distribution … ».

Elles sont vraies pour des sorties **symétriques dans le bruit** (stop 1.5 ATR / objectif 2R en 1h, ce que l'on a mesuré). Elles sont **fausses en général**. Avec une dérive positive et des queues droites épaisses, une entrée sans information associée à une sortie qui **laisse courir** peut gagner. Le buy & hold en est le cas limite : +167 % sur BTC dans le même rapport. Or l'objectif 2R coupe précisément cette queue droite, et la sortie direction ne concerne que 6 % des trades.
→ Reformuler : « Avec les sorties actuelles (stop 1,5 ATR / objectif 2R en 1h), l'entrée B7 ne produit pas d'écart mesurable au-dessus des coûts. Ces données ne disent rien de sorties qui laissent courir les tendances, qui constituent une hypothèse distincte, non testée ici. »
C'est d'autant plus nécessaire que le chantier RS teste justement cette hypothèse (Donchian 4h, trailing, sans 2R).

**R2 — « ne prédit pas mieux que le hasard » (§3.2).**
Sans intervalle, la phrase dépasse ce que montre le tableau. → « Écart moyen ≤ 0,06 pt à 1–24 h, bien inférieur au coût d'un aller-retour (0,22 %). Aucun intervalle à ce stade : P3 le mesurera. » Même remarque pour « le problème principal est à l'entrée » : parler de **constat compatible**, pas de preuve, avant P3.

**R3 — Étude d'événement P3 : un point à préciser avant exécution.**
Les témoins « même symbole, même mois » neutralisent la dérive **mensuelle**. Mais les BUY arrivent **après** une hausse de ~3 ATR (§3.2). Si les rendements à 24–168 h ont une autocorrélation (momentum ou retour à la moyenne), la différence `d` mesure aussi cet effet de « barre après une hausse », pas seulement le filtre B7.
→ **Ne pas changer P3** (il est pré-enregistré). Ajouter seulement au rapport une ligne **descriptive**, sans décision : le rendement moyen après les barres témoins dont la hausse sur 12 barres dépasse 2 R, pour situer ce qui revient au momentum brut. S'il faut plus, ce sera une hypothèse séparée.

**R4 — Navigation UI → positions paper (recommandation produit, décision Samir).**
Tant que les scans UI 15m/4h/1d peuvent ouvrir des positions automatiques, le paper live **ne mesure pas** la stratégie 1h. Je recommande que ces scans ne déclenchent plus `sync_auto_watchlist`, sans toucher aux règles de trading. À traiter comme un **ticket séparé** : ce n'est pas un changement de stratégie.

## Coordination

- La session #159 garde ses amendements `VP0-2026-09-27b` / `VP0-2026-09-28` et ses 3 lignes de ledger (P1, P2, P3).
- **Les nouveaux amendements et lignes de ledger du chantier RS sont centralisés par le pilote RS.** Merci de ne pas ajouter d'amendement RS de votre côté. En cas de conflit sur `VALIDATION-PROTOCOL.md` / `VP-T10B-LEDGER.md` / le handoff, rebaser sur `main` sans réécrire les blocs de l'autre session.
