# Inventaire UI fiches — Chantier 1 phase A

**Branche** : `cursor/ui-fiches-a2fe`  
**Base** : `origin/main` @ `225549d` (#109)  
**Logique récupérée** : composants V1/V2 @ `604a8b0` (reuse calculs/champs, **pas** l’ancien CSS)  
**Règle** : donnée manquante → « — » + raison ; jamais inventer ; paper only.

---

## Légende placement

| Code | Signification |
|---|---|
| **FD / Synthèse** | `FicheDecision` onglet Synthèse |
| **FD / 5 portes** | `FicheDecision` onglet 5 portes |
| **FD / Preuves** | `FicheDecision` onglet Preuves |
| **FD / Plan** | `FicheDecision` onglet Plan |
| **FD / Historique** | `FicheDecision` onglet Historique |
| **FD / Pied** | Footer actions (toutes fiches décision) |
| **Phase B** | `FichePosition` / `FicheRun` / Calques — hors phase A |
| **Non affiché** | Volontairement hors fiches (surface maquette / autre page / redondant) |

---

## 1. Champs moteur `DecisionDetail`

Source front : `lib/decisions.ts` (+ payload natif `pipeline`).

### 1.1 Identité / verdict

| Champ | Placement | Notes |
|---|---|---|
| `symbol` | FD / Synthèse (titre) + toutes entrées | |
| `timeframe` | FD / Synthèse + deep-link `decision:SYM:tf` | |
| `price` | FD / Synthèse (phrase) ; FD / Plan (entrée) | |
| `decision` (combiner legacy) | FD / Synthèse (cycle dérivé) ; diagnostic | Option B : action = portes |
| `direction` | FD / Synthèse ; FD / 5 portes (Direction) | |
| `confidence` | FD / Synthèse | |
| `probability` | **Non affiché** | Redondant avec confidence côté UI V1 ; pas dans maquette fiche |
| `ichimoku_score` | FD / 5 portes (Direction) + phrase Synthèse | |
| `rvol` | FD / 5 portes (Participation) ; Preuves/contexte | |
| `pipeline.decision` | FD / Synthèse (cycle WATCH/ARMED/TRIGGERED) | |
| `pipeline.direction` | FD / Synthèse / 5 portes | Prioritaire si natif |
| `pipeline.strategy_version` | FD / Synthèse | Sinon `strategy_version` |
| `pipeline.stages[]` | FD / 5 portes | id/status/summary/codes |
| `strategy_version` | FD / Synthèse | |
| `timestamp` | FD / Synthèse (« Données au ») | Epoch s/ms → formaté |
| `agreement` | FD / Preuves (accord agents) | |
| `weights_used` | FD / Preuves (détail replié) | Objet brut clé→poids ; si vide « — · moteur sans poids » |
| `volume_type` | FD / 5 portes (RVOL) | Fallback `rvol_detail.volume_type` |
| `lab_context` (screener) | **Non affiché** (phase A) | Observation Lab ; pas dans fiche décision maquette |
| `data_quality` | FD / Synthèse notice si `stale` / `data_late` | Sinon non affiché |
| `data_provenance` | **Non affiché** | Audit Lab ; pas surface fiche |

### 1.2 Listes de preuves / risques

| Champ | Placement |
|---|---|
| `reasons` | FD / Preuves |
| `risks` | FD / Preuves |
| `invalidation` | FD / Synthèse (1ʳᵉ) + FD / Preuves (liste) |
| `positive_evidence` | FD / Preuves (fallback `evidence.positive_evidence` puis `reasons`) |
| `contradictions` | FD / Preuves |
| `why_not` | FD / Preuves (fallback `evidence.why_not_long/short` selon direction, puis `risks`) |

### 1.3 Agents `ichimoku` / `rvol_detail`

| Champ | Placement | Notes |
|---|---|---|
| `ichimoku.direction` | FD / 5 portes | |
| `ichimoku.confidence` | FD / 5 portes | |
| `ichimoku.probability` | **Non affiché** | Idem probability top-level |
| `ichimoku.reasons` | FD / 5 portes (codes Direction) | |
| `ichimoku.metadata.tenkan` | FD / 5 portes | Hint vocabulaire Tenkan |
| `ichimoku.metadata.kijun` | FD / 5 portes | Hint Kijun |
| `ichimoku.metadata.tk_cross` | FD / 5 portes | |
| `ichimoku.metadata.price_vs_kumo` / cloud | FD / 5 portes | |
| `ichimoku.metadata.chikou_state` | FD / 5 portes | Hint Chikou |
| `ichimoku.metadata` autres (senkou…) | FD / 5 portes si présent ; sinon **Non affiché** | Pas inventé |
| `rvol_detail.direction` | FD / 5 portes | |
| `rvol_detail.confidence` | FD / 5 portes | |
| `rvol_detail.reasons` | FD / 5 portes | |
| `rvol_detail.metadata.rvol` | FD / 5 portes | Aligné `detail.rvol` |
| `rvol_detail.metadata` seuil / anomaly | FD / 5 portes si présent | Seuil UI de repli ≥ 1,5 si moteur n’envoie pas |
| `rvol_detail.volume_type` | FD / 5 portes | |

### 1.4 `evidence` (EvidencePack)

| Champ | Placement |
|---|---|
| `evidence_engine_version` / `rules_version` / `feature_version` | FD / Preuves (pied version) |
| `strategy_version` (pack) | FD / Preuves si ≠ top-level |
| `calibration_note` | FD / Preuves (sample) |
| `historical.sample_size` | FD / Preuves |
| `historical.sample_quality` | FD / Preuves |
| `historical.status` | FD / Preuves |
| `historical.horizon` | FD / Preuves |
| `historical.mean_return_pct` / `median_return_pct` | FD / Preuves |
| `historical.favorable_rate` | FD / Preuves |
| `historical.mean_mfe_pct` / `mean_mae_pct` | FD / Preuves |
| `ablation[]` | FD / Preuves (`table-wrap`) |
| `positive_evidence` / `contradictions` / `invalidation` | Voir §1.2 |
| `why_not_long` / `why_not_short` | FD / Preuves (via `why_not`) |
| `evidence.context` | Fusionné avec `detail.context` → portes / preuves |

### 1.5 `context` (moteur / evidence)

| Sous-arbre | Placement | Gap moteur? |
|---|---|---|
| `context.ichimoku.{direction,tk_state,price_vs_cloud,chikou_state}` | FD / 5 portes | Présent via evidence context |
| `context.volume.{rvol,volume_type,participation_state}` | FD / 5 portes | |
| `context.structure.{trend,breakout_state}` | FD / 5 portes (BOS/CHoCH si codes) | CHoCH explicite : si absent du payload → « — · champ CHoCH non exposé » |
| `context.regime.{pipeline_regime,codes}` | FD / 5 portes | |
| Autres clés context | **Non affiché** sauf utiles aux 5 portes | Éviter dump JSON |

### 1.6 `order_intent`

| Champ | Placement |
|---|---|
| `actionable` / `reason` | FD / Plan + pied (disabled) |
| `pipeline_decision` / `direction` | FD / Plan |
| `price` / `entry_fill` | FD / Plan |
| `qty` / `notional` | FD / Plan |
| `stop_price` / `stop_distance` / `stop` | FD / Plan |
| `take_profit_price` / `targets[]` | FD / Plan |
| `risk_pct` / `risk_amount` | FD / Plan (+ R = \|Δtarget\|/\|Δstop\|) |
| `equity` / `cash` / `portfolio_code` | FD / Plan |
| `volume_type` | FD / Plan |
| `evidence_summary` | FD / Plan / Preuves |
| `invalidation` | FD / Synthèse fallback |
| `signal_timing` | FD / Plan si présent ; sinon « — » |
| `trigger` / `expiration` / `session` / `codes` / `versions` | FD / Plan (bloc technique replié) si présents |
| Frais estimés | FD / Plan via `previewPaperBuy` quand qty/stop/R connus | Sinon « — · aperçu frais non calculé » |
| Scénarios | FD / Plan via preview `scenarios` (`ScenariosPanel` logique, classes maquette) | |

---

## 2. Composants V1/V2 @ `604a8b0` → fiches

### 2.1 Décision (phase A — `FicheDecision`)

| Composant historique | Ce qu’il montrait | Placement phase A |
|---|---|---|
| **DecisionPipelinePanel** | 5 stages (question, status, summary, codes) + reading blocks PA/MTF/Location/ATR | FD / 5 portes |
| **GateMatrix** | Matrice screener portes + verdict + paper | Surface Opportunités (maquette) ; clic → FD ; **pas** dupliqué dans fiche |
| **SignalEvidenceCard** | Ichimoku/RVOL/structure/régime, preuves +/−, why_not, contradictions, invalidation, historical, ablation, versions | FD / 5 portes + Preuves |
| **TradePlanCard** | Montant, qty, entrée, stop, TP, risque %, durée, règles sortie, stages | FD / Plan |
| **ProposePaperTradePanel** | Intent actionable, portes, qty/stop/TP, CTA | FD / Plan + Pied → PaperConfirmSheet |
| **ScenariosPanel** | Objectif/Stop/Crash + holding | FD / Plan |
| **CostsPanel** | Coûts portefeuille agrégés (gross/fees/net) | **Non affiché** dans FD — agrégat Desk/Portefeuille ; frais **estimés trade** = Plan |
| **WhyCard** | Résumé FR + stages + RVOL + invalidation | Remplacé : carte Opportunités ouvre FD |
| **BiasPanel** | Pipeline + CTA « Préparer le trade » | Surface Marché (lecture) ; CTA → FD Plan |
| **VerdictBadge** | Combiner + portes | FD / Synthèse (tags maquette) |

### 2.2 Position / paper (phase B)

| Composant | Contenu | Placement |
|---|---|---|
| **PaperTradeSheet** | Position open/closed, PnL, partials, pourquoi, CTA close | **Phase B** `FichePosition` |
| **PositionChart** | Mini OHLC + entrée/stop/TP/exit | **Phase B** |
| **PaperConfirmSheet** | Preview buy + scenarios + confirm | Gardé (hors fiche) ; déclenché depuis FD Pied |

### 2.3 Lab / runs / calques (phase B ou non affiché)

| Composant | Contenu | Placement |
|---|---|---|
| **BacktestRunsPanel** | Liste runs, beats Ichimoku | **Phase B** `FicheRun` / page Lab |
| **LabResearchPanel** | Poids familles, compare, audit, MC, walk-forward | **Phase B** / Lab ; walk-forward hint vocabulaire si métrique présente |
| **TestProgressPanel** | Jauge trades/jours, checks verdict | **Non affiché** fiche décision — Ops/Desk |
| **ActivityJournal** | Feed ordres/événements | FD / Historique (décisions journal + positions symbole) ; feed global reste Ops |
| **MarketLayersMenu** | Calques chart Ichimoku/FVG/… | **Phase B** Calques (Marché) |
| **MarkTradeSheet** | Points user entry/stop/target + R | **Non affiché** FD — outil Marché |
| **BacktestOverlaySheet** | Overlay trades + WHY | **Phase B** / Marché Lab |

---

## 3. Onglets `FicheDecision` (contrat UI)

| Onglet | Contenu obligatoire |
|---|---|
| **Synthèse** | Cycle, direction, confiance, phrase lisible (`buildDecisionSummary`), invalidation, strategy version, timestamp données |
| **5 portes** | PASSE / PRUDENCE / ÉCHEC (+ BLOQUÉ matrice) + mesures réelles Ichimoku (prix vs nuage, Tenkan/Kijun, Chikou), RVOL (valeur, seuil, volume_type), structure BOS/CHoCH, placement, régime + pourquoi le statut |
| **Preuves** | reasons, positive_evidence, contradictions, why_not, risks, sample (size, quality, calibration) + ablation si présent |
| **Plan** | order_intent (entry, stop, target, qty, amount, risk €/%, R), frais estimés, scenarios |
| **Historique** | Décisions journal (`/api/decisions`) + positions paper passées pour le symbole |
| **Pied** | Voir le graphique · Enregistrer la décision · Ouvrir en paper → ; disabled expliqués (« Déjà en portefeuille », « Portes non passées : avis Attente ») |

Vocabulaire : chaque terme technique → une ligne muted sous la valeur via `lib/decisionLabels.ts` (`termHint`).

---

## 4. Deep links shell

| Forme | Comportement phase A |
|---|---|
| `?fiche=decision:<SYMBOL>:<tf>` | Ouvre `FicheDecision` (tf défaut `1h`) |
| `?fiche=decision:…` + `tab=plan\|synthese\|portes\|preuves\|historique` | Onglet initial |
| `?fiche=position:<id>` | `FichePosition` (skeleton phase B) |
| `?fiche=run:<id>` | Stub « Phase B » |
| `?fiche=agent:<id>` | Stub « Phase B » |
| Browser back | Ferme la fiche (push history à l’ouverture) |

Toute page peut ouvrir n’importe quelle fiche via helper `openFiche`.

---

## 5. Points d’entrée (câblage A3)

| Surface | Action | Cible |
|---|---|---|
| Marché | « Voir la fiche décision ↗ » | FD Synthèse |
| Marché | Clic rangée 5 portes / lecture | FD 5 portes |
| Marché | « Préparer le trade → » | FD Plan |
| Opportunités | Clic ligne matrice | FD (remplace dialog local) |
| Opportunités | « Pourquoi X ? » / Ouvrir la fiche | FD |
| Desk | Chaque opportunité listée | FD |
| Desk | Positions ouvertes / concentration | `FichePosition` (`?fiche=position:id`) |
| Portefeuille | Ligne position ouverte | `FichePosition` |
| Journal | Chaque décision sauvegardée | FD (as-of si moteur le permet ; sinon live + mention) |
| Journal | Trades clôturés / « Rejouer » | `FichePosition` (trades) ou FD (décisions) |
| Copilot | Symbole mentionné dans une réponse | Lien → FD |

---

## 6. Gaps moteur (à noter — pas de patch `engine/` / `server/` ici)

| Besoin UI | État |
|---|---|
| CHoCH explicite dans `context.structure` | Souvent absent ; codes pipeline `choch_*` expérimentaux → « — · CHoCH non exposé » |
| Tenkan/Kijun numériques | Via `ichimoku.metadata` si agent les envoie ; sinon « — » |
| Seuil RVOL moteur | Pas de champ dédié stable → repli documenté 1,5 |
| Décision as-of (replay historique Journal) | API détail = live ; mention « lecture courante, pas as-of » |
| Frais dans `order_intent` sans preview | Besoin `previewPaperBuy` côté front |
| Ablation / historical | Parfois absents → « — · pas encore calculée » |
| `probability` top-level | Non mappé maquette |

---

## 7. Compteurs (phase A)

| Catégorie | Affichés dans FD | Non affiché / Phase B / autre page |
|---|---:|---:|
| Champs `DecisionDetail` (+ sous-arbres listés) | **52** | **14** |
| Blocs composants V1/V2 inventoriés | **9** (décision) | **11** (position/lab/calques/outils) |

*Comptage §1 + mapping §2 ; les sous-clés metadata optionnelles comptent comme « affiché si présent ».*
