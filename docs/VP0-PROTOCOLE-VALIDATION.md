# VP0 — Protocole de validation IchiVol (document only)

**Statut :** brouillon Cursor · 2026-09-26 · **pas d’implémentation** dans ce ticket.

## But

Définir *comment* on valide qu’un signal / régime / objet chart est digne de confiance **avant** toute promo décision ou paper. VP0 = le protocole ; VP1+ = exécution lab / OOS.

## Périmètre gelé en amont

| Chantier | État |
|----------|------|
| Chart Intelligence | **GEL** — #134+#133 mergés (`50ea9c4`/`df013fb`) — bugs only |
| T-CYCLE | **GEL** — #123 mergé (`9e2b02f`, P6 inclus) — bugs only jusqu’à VP |
| GOLDEN-RVOL | [#135](https://github.com/samiriggui-code/IchiVol/issues/135) — tip vert sur agent CI ; attendre diff Claude |

## Hypothèses à valider (ordre proposé)

1. **Anti-lookahead** — tout `known_at` / frame replay / closed candle respecte T ≤ as_of.
2. **Stabilité d’identité** — `lineage_key` relie les objets à ids changeants (CI-R8).
3. **Budget runtime** — replay &lt; budget proxy ; study cycle &lt; 20 s (P1) ; synthetic validate 2ᵉ appel &lt; 1 s (P6).
4. **Surrogates / nulls** — tout claim « edge » a un score vs nulls (cycle study) ou un golden figé.
5. **RVOL / goldens** — ticket GOLDEN-RVOL : bisect avant régénération.
6. **Décision** — aucun chantier observe-only (`promote_to_decision=false`) ne mute `decision/` ou `paper/`.

## Méthode (doc)

Pour chaque hypothèse H :

1. **Critère** — métrique + seuil + jeu (symbole/TF/fenêtre/seed).
2. **Baseline** — tip `main` + RELEASE VPS.
3. **Preuve** — test automatisé *ou* smoke VPS chiffré dans HANDOFF.
4. **Verdict** — PASS / FAIL / INCONCLUSIVE ; pas de merge feature si FAIL sur H bloquante.

## Hors scope VP0

- Nouveaux producteurs ChartObject / nouvelles pages UI CI
- Nouvelles méthodes spectrales T-CYCLE
- Live trading / broker

## Prochaine étape

Après GOLDEN-RVOL tranché : VP1 = runbook exécutable (scripts + fixtures) calé sur les hypothèses 1–5.
