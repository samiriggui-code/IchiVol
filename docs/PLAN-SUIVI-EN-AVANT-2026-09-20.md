# Plan de suivi en avant (forward test) — proposition, non déployée

Statut : **à valider par l'utilisateur**. Aucun déploiement, aucune écriture VPS, aucun ordre réel.

## Objectif
Mesurer en temps réel, sans retoucher les paramètres, si la référence corrigée et la variante la plus prometteuse ont une espérance nette positive après frais réalistes. L'historique (études du 2026-09-20) ne suffit pas à décider.

## Portefeuilles (5 000 € virtuels chacun, indépendants, mêmes cycles et mêmes prix)
| Code proposé | Règle | Justification |
|---|---|---|
| `FWD_A_REF` | référence corrigée : bougies clôturées (déjà en production depuis 2026-09-20 17:34:36 UTC), un lot par symbole, garde-fous agrégés (`max_open_risk_pct` 4 %, `max_symbol_notional_pct` 25 %, `daily_loss_limit_pct` 3 %, `one_entry_per_signal_run`), `log_rejections` | contrôle |
| `FWD_E_LONG` | entrées de A, **longs seulement**, sortie sur stop/objectif/changement de direction Ichimoku | seule variante positive en validation (+719 €), à confirmer |
| `FWD_A_LONG` | A, longs seulement | isole l'effet « longs seulement » de l'effet « sortie E » |

Le baseline `ICHIVOL_BASELINE_V1` et les 11 autres portefeuilles ne sont pas modifiés et servent de témoin séparé (historique pré-17:34 non mélangé).

## Règles figées pendant le test
- Paramètres, barème de frais et règles ne changent pas pendant au moins **8 semaines** (jusqu'au 2026-11-15 au plus tôt) ; toute modification ouvre une nouvelle expérience.
- Barème de coûts : commission 7,5 bps (frais spot réels avec BNB), spread/slippage par instrument selon le barème de `docs/REVUE-SIM-ET-COUTS-ichivol-36-2026-09-20.md` (hypothèses de palier signalées), scénario défavorable rapporté en parallèle.
- Pas de levier, pas de martingale, pas de hausse de mise après perte.

## Critères de décision fixés à l'avance
- Minimum 150 transactions clôturées par portefeuille **et** 8 semaines ; sinon « résultat insuffisant pour décider ».
- Candidat retenu seulement si : net après frais réalistes > 0 **et** net > 0 sans ses 3 meilleures transactions **et** positif sur au moins 2 des 3 périodes de ~19 jours **et** drawdown < 15 % **et** non négatif en scénario défavorable de −0,5 × son net réalisé au plus.
- Sinon : conserver la référence, ne pas déployer la variante.

## Rapport
Hebdomadaire, automatique : transactions, brut/frais/net, espérance, drawdown, exposition, causes de sortie, compteurs de rejets (`PIPELINE_FUNNEL`, `SIGNAL_REJECTED`), part des 3 meilleures transactions.

## Prérequis (décisions utilisateur)
1. Création des trois profils/portefeuilles (code, dans un commit dédié, puis déploiement D5 avec sauvegarde).
2. Option « longs seulement » dans le profil (aujourd'hui absente du broker : à ajouter par ichivol-49, propriétaire de `paper/broker.py`).
3. Grand livre (D2) : souhaitable avant le démarrage pour une comptabilité vérifiable.
4. Limite connue : un test crypto Binance seulement ; le multimarché reste à faire (voir inventaire des données).
