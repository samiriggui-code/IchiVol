# Annexe — Préconditions techniques (ex-VP0)

**Rôle :** garde-fous techniques (lookahead, budgets, GEL).  
**Ce n’est pas** le protocole de validation produit.

👉 Protocole VP0 (question centrale, B0–B8, A–L, plis, coûts, verdicts) :  
[`VALIDATION-PROTOCOL.md`](./VALIDATION-PROTOCOL.md) (`VP0-2026-09-26`).

---

## Périmètre gelé en amont

| Chantier | État |
|----------|------|
| Chart Intelligence | **GEL** — #134+#133 (`50ea9c4` / `df013fb`) — bugs only |
| T-CYCLE | **GEL** — #123 (`9e2b02f`, P6 inclus) — bugs only jusqu’à VP |
| GOLDEN-RVOL | [#135](https://github.com/samiriggui-code/IchiVol/issues/135) — diagnostic Claude : ULP py3.11 vs 3.12 ; fix pin+approx → [#139](https://github.com/samiriggui-code/IchiVol/pull/139) **MERGÉ** @ c46eda1 ; **ne pas régénérer** ; fermer #135 |

## Invariants techniques (à respecter dans VP1+)

1. **Anti-lookahead** — `known_at` / frame replay / closed candle : T ≤ as_of.
2. **Stabilité d’identité** — `lineage_key` relie les objets à ids changeants (CI-R8).
3. **Budget runtime** — replay &lt; budget proxy ; study cycle &lt; 20 s (P1) ; synthetic validate 2ᵉ appel &lt; 1 s (P6).
4. **Surrogates / nulls** — claim « edge » = score vs nulls (cycle) ou golden figé.
5. **Observe-only** — `promote_to_decision=false` ne mute pas `decision/` ni `paper/` hors runs VP explicitement paper.
6. **Moteur = vérité** — le LLM n’invente aucune valeur numérique.

## Hors scope de cette annexe

Échelle B0–B8, questions A–L, IS/OOS, coûts, critères EDGE — uniquement dans `VALIDATION-PROTOCOL.md`.
