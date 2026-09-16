# Handoff Claude — Contrat UI pipeline (Cursor a déjà branché le front)

> **Pour :** Claude Code (`engine/` decision pipeline)  
> **De :** Cursor (2026-09-15 soir)  
> **Lire après :** [`HANDOFF-CLAUDE-REALIGN-NORTHSTAR.md`](./HANDOFF-CLAUDE-REALIGN-NORTHSTAR.md)

---

## 0. Ce que Cursor a fait (ne pas refaire côté front)

| Fichier | Rôle |
|---------|------|
| `ichivol-app/src/lib/decisionPipeline.ts` | Types 5 portes + adapter depuis `DecisionDetail` |
| `ichivol-app/src/components/DecisionPipelinePanel.tsx` | UI sheet Décisions |
| `ichivol-app/src/pages/DecisionsPage.tsx` | Affiche le pipeline ; agents bruts en `<details>` |
| `DecisionDetail.pipeline?` | Champ optionnel typé |

Aujourd’hui le front **adapte** Ichimoku + RVOL → portes 1–2 ; portes 3–5 = `pending`.

Dès que tu renvoies `pipeline` natif sur `GET /api/engine/decisions/:symbol`, l’UI l’utilise **sans autre change front**.

---

## 1. Shape JSON attendu (optionnel, additive)

Sur la réponse détail décision, ajouter :

```json
{
  "pipeline": {
    "stages": [
      {
        "id": "direction",
        "status": "pass",
        "summary": "LONG · score 72 · conf 81%",
        "codes": ["price_above_kumo", "bullish_tk_cross"]
      },
      {
        "id": "participation",
        "status": "fail",
        "summary": "RVOL 0.84× — participation insuffisante",
        "codes": ["low_participation"]
      },
      {
        "id": "structure",
        "status": "pending",
        "summary": "Price Action + MTF — bientôt",
        "codes": []
      },
      {
        "id": "location",
        "status": "pending",
        "summary": "VP + VWAP — V1.5",
        "codes": []
      },
      {
        "id": "regime",
        "status": "pending",
        "summary": "ATR — bientôt",
        "codes": []
      }
    ]
  }
}
```

### Enums

| Champ | Valeurs |
|-------|---------|
| `id` | `direction` \| `participation` \| `structure` \| `location` \| `regime` |
| `status` | `pass` \| `fail` \| `watch` \| `pending` \| `skip` |

- `summary` : une ligne, **chiffres réels** seulement  
- `codes` : codes machine existants (raisons) — le front les traduit FR  

Garde `ichimoku`, `rvol_detail`, `decision`, etc. pour compat.

---

## 2. Mapping produit → stages

| Stage | Source V1 | status typique |
|-------|-----------|----------------|
| `direction` | Ichimoku agent | pass / watch (NEUTRAL) |
| `participation` | RVOL gate (≥1.5) | pass / watch / fail |
| `structure` | PA + MTF (à coder) | pending → pass/fail/watch |
| `location` | VP + VWAP (V1.5) | pending |
| `regime` | ATR (à coder) | pending → pass/watch/fail (jamais LONG/SHORT) |

**Ne pas** remplir `direction` depuis RVOL ou ATR.

---

## 3. Ordre de travail suggéré pour toi

1. Realign north star (déjà)  
2. Finir univers / MarketData si en cours  
3. Remplacer combiner × par portes ; exposer `pipeline` (même si structure/regime encore `pending`)  
4. Puis structure_agent + ATR → remplir stages 3 et 5  

---

## 4. Collision

Ne modifie pas les fichiers `src/lib/decisionPipeline.ts` / `DecisionPipelinePanel.tsx` sauf accord — le contrat est déjà figé côté front.
