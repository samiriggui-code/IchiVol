# État réel d'IchiVol — 2026-09-20 (soir)

Rédigé après lecture des données de production (VPS, lecture seule), tests API/DB locaux et test de migration sur copie.
Rien de ce document n'a été déployé en production par cette session après le déploiement de 17:33 UTC (correctifs « décisions sur bougies clôturées » + affichage des erreurs).

## 0. Corrections de mes annonces précédentes

- « Deux confirmations LINK orphelines » : **faux**. Il n'existe qu'**une** ligne LINK dans le journal (`b263c134…`, créée le 18/09 à 19:41, gate WATCH). Les deux `POST /api/decisions` du 20/09 à 16:52 ont pris le chemin « dédoublonnage » (HTTP 200) et ont simplement mis à jour cette ligne.
- « Aucune décision orpheline ne sera créée » : incomplet. Le chemin de dédoublonnage **modifie** une confirmation existante (biais, gate, RVOL) même si l'ouverture est ensuite refusée. Corrigé en profondeur : le front ouvre désormais la position **avant** d'écrire au journal (local, non déployé).
- « Le VPS contient du travail absent de mon arbre (mt5.py, PaperTechPage.tsx) » : **faux**. Ce sont deux fichiers **supprimés volontairement du dépôt** (commits 269a02b « retire le pont MT5… » et 7899dc8) mais restés sur le VPS comme reliquats non référencés.
- Mon déploiement de 17:33 a reconstruit le moteur sans que le verrou « un seul lot par symbole » soit dans l'image (voir §4).

## 1. Parcours d'ouverture (Achat → confirmation → position → journal → compte)

Testé au niveau API sur la base de développement avec un résultat de scan contrôlé ([test_open_flow.py](../ichivol-app/engine/tests/api/test_open_flow.py), 6 tests) :

| Exigence | Résultat |
|---|---|
| Confirmation acceptée → une seule position | OK : 1 position, 1 ordre, 1 événement `OPENED`, 1 écriture comptable |
| Débit unique | OK : débit = notionnel + frais d'entrée, une seule fois |
| Refus (Portes ≠ Achat) → motif exploitable, compte intact | OK : HTTP 422 `not_actionable…`, aucune position/ordre/événement, solde inchangé |
| Refus pour fonds insuffisants | **Défaut trouvé et corrigé** : le moteur ouvrait une position « poussière » (0,5 € au lieu de ~1 250 €). Il refuse maintenant si le lot cash-limité est < 25 % du lot prévu ou < 10 € (`min_fill_fraction`, `min_notional`, configurables par profil) |
| Nouvelle tentative | OK : renvoie la position existante (`already_open`), pas de 2ᵉ débit |
| Double clic simultané | **Défaut trouvé et corrigé** : `SELECT … FOR UPDATE` ne verrouille pas une ligne qui n'existe pas encore ; deux requêtes simultanées pouvaient créer deux lots. Ajout d'un verrou consultatif PostgreSQL par (portefeuille, symbole) ; 6 requêtes simultanées → 1 position |
| Montants cohérents après actualisation | OK : `equity = cash + investi + latent` |

**Non vérifié visuellement** : aucun accès navigateur (authentification). Ce qui reste à voir à l'écran : la fenêtre de confirmation avec la bannière d'erreur, et le message « journal non enregistré » si l'écriture journal échoue après l'ouverture.

## 2. Comportement des signaux

Réglage conservé : calcul sur **bougies clôturées** (`DECIDE_ON_CLOSED_CANDLES=true`). Nouvelles métadonnées (`signal_timing`, [timing.py](../ichivol-app/engine/app/screener/timing.py)), exposées dans le détail de décision et dans l'intention d'ordre :

| Notion | Champ | Sens |
|---|---|---|
| Heure de clôture de la bougie utilisée | `signal_bar_close` | fin de la dernière bougie **clôturée** |
| Heure du calcul | `computed_at` | quand le scan a tourné |
| Cours live affiché | `live_price` | dernier prix négocié (dans la bougie en formation) |
| Prix d'exécution simulé | *(broker)* | ask/bid si cotation, sinon prix + friction configurée ; jamais le prix du signal |
| Retard de données | `lag_bars`, `data_late`, `stale` | ≥1 : clôture attendue non livrée (tolérance 120 s après la frontière) ; ≥2 : **périmé → ordre refusé** (`stale_data`) |

Tests ([test_timing.py](../ichivol-app/engine/tests/screener/test_timing.py)) : passage de 09:59:50 à 10:00:20 (la 09:00 devient la bougie du signal), arrivée tardive de la clôture (drapeau après la tolérance), obsolescence (fournisseur bloqué → refus). Ce n'est **pas** équivalent à « quatre appels identiques en 70 s » : ces tests contrôlent l'horloge.

Ce qui peut encore refuser une ouverture alors que le signal reste stable : verrou « lot déjà ouvert », plafond de positions, cash/pouvoir d'achat (dont le lot poussière), stop ATR absent, donnée périmée, refus de cotation (mode `quote_based`). Le prix, l'ATR-stop et l'éligibilité varient entre deux clôtures ; le **signal**, non.

**Protections entre deux clôtures** : indépendantes du signal (voir §3).

## 3. Stops et objectifs

- **Défaut confirmé** : avant correction, stops/objectifs n'étaient évalués que lors du rafraîchissement du screener (toutes les 5 min, `refresh_interval_s=300`), sur **un seul échantillon de prix**, et le contrôle ne trouvait pas les positions `user_confirmed` (recherche filtrée par source). Le verrou multi-sources ajouté ensuite dans l'arbre de travail ne corrige que la recherche, pas l'échantillonnage.
- **Correction (locale, testée, non déployée)** : [protection.py](../ichivol-app/engine/app/paper/protection.py), boucle indépendante toutes les 60 s, pour **toutes** les positions ouvertes financées avec niveaux, quelle que soit la source ou le portefeuille :
  1. reste de la minute d'entrée : ticks agrégés **depuis l'heure exacte d'entrée** (aucun plus haut/bas antérieur à l'entrée) ;
  2. minutes entières suivantes : barres 1 min via la règle de franchissement prudente (gap au-delà d'un niveau → exécution à l'ouverture) ;
  3. si stop et objectif tombent dans la même minute : ticks de cette minute, sinon **stop d'abord** (documenté dans la note).
  4. sortie horodatée à l'heure du franchissement, écriture comptable idempotente.
- **Positions existantes non réécrites** : une position ouverte avant la surveillance est « legacy » : la surveillance démarre **à partir de maintenant** ; un franchissement passé est seulement **rapporté**, jamais appliqué.
- Tests ([test_protection.py](../ichivol-app/engine/tests/paper/test_protection.py), 7) : entrée en milieu de minute avec plus haut antérieur ignoré, gap, ordre des niveaux, minute non clôturée, position confirmée manuellement clôturée à l'heure du franchissement + réconciliation, position legacy jamais fermée.

**APT (position `061c22cd`, confirmée manuellement)** — reconstruction sur données Binance réelles :
- entrée `2026-09-18 20:38:49,456 UTC` à 0,72836 ; stop 0,70308 ; objectif 0,77894 ; 1 719,89 unités, 1 252,71 €.
- reste de la minute d'entrée : 6 trades, tous à 0,728 (rien).
- 2 741 barres 1 min analysées jusqu'à 20/09 18:19 : **premier franchissement = objectif, le 2026-09-19 à 04:15 UTC** (barre 0,775/0,782/0,766/0,780 ; stop non touché dans cette barre).
- Le stop a été touché plus tard (plus bas 0,696), donc la position aurait de toute façon été fermée.
- La position est **restée ouverte** ; elle est valorisée à 0,741 (+21,73 € latent). Si l'objectif avait été appliqué : ≈ +87 € bruts (−1,25 € de frais d'entrée). L'écart (~65 €) est l'effet du défaut, **non réécrit**.
- Le mode « legacy » de la nouvelle surveillance confirme ce résultat en essai à blanc (données réelles, copie de production) : `take_profit_hit à 2026-09-19T04:15:00Z`, sans rien fermer.
- Aucune fermeture n'est proposée sans votre décision explicite.

**LTC et AVAX** : positions historiques **sans quantité, sans stop, sans objectif** (`unprotected_legacy_no_levels`). Aucune surveillance possible : ce sont des suivis de signal, pas des lots financés (voir §8).

## 4. Les deux entrées NEAR

**Défaut technique, pas une accumulation voulue.** Chronologie du portefeuille de base :

| Heure UTC | Événement | Notionnel |
|---|---|---|
| 16:14:14 | ouverture automatique NEAR (`008e9a8f`) | 1 240,28 € |
| 16:20:01 | **confirmation manuelle** NEAR (`4c47b5e1`) alors que le lot automatique est ouvert | 1 222,15 € |
| 16:56:56 | le lot automatique se ferme sur objectif (+99,05 €) | |
| 17:34:36 | **nouvelle ouverture automatique** NEAR (`04cd6b2b`) alors que le lot manuel est encore ouvert | 1 097,49 € |

- Cause 1 (16:20) : le contrôle « un lot par symbole » n'existait pas dans l'image du moteur (construite à 11:42) ; il n'a été copié sur le VPS qu'à 17:04–17:47.
- Cause 2 (17:34) : ma reconstruction de 17:34 a repris des fichiers qui **ne contenaient pas** encore ce verrou (le fichier a été remplacé sur l'hôte à 17:47, après la construction). Le conteneur en marche n'a toujours pas le verrou : vérifié (`_get_open_by_symbol` absent du module chargé).
- Exposition cumulée : jusqu'à 2 462 € sur NEAR (≈ 49 % du capital) alors que le plafond de 25 % s'applique **par ordre**, pas par instrument. Le verrou « un lot par (portefeuille, symbole) » est le contrôle par instrument ; il est en place dans le code local et testé (séquentiel + 6 requêtes simultanées).
- Concurrence : les 4 lots NEAR de 17:34:36 appartiennent à 4 **portefeuilles différents** (comptes de stratégie parallèles : baseline, TRENDLN, CTX_FLOW, CTX_REGIME) ; c'est voulu. Le doublon fautif est uniquement dans le portefeuille de base. Il a depuis été fermé (le lot auto de 17:34 n'apparaît plus à 19:05).
- Transactions existantes **préservées** ; aucune réparation de données proposée pour NEAR (c'est un défaut de code, corrigé côté code).

## 5. Confirmation LINK

Enregistrement présenté avant toute action : voir [le script](../scripts/repairs/2026-09-20_archive_orphan_link_confirmation.sql).

- `decisions.id = b263c134-40fb-432d-9b1a-ad1449a00406`, LINKUSDT 1h, `confirmed`, gate `WATCH`, signal BUY, confiance 0,1, RVOL 0, créée le 18/09 19:41:43.
- Vérifié côté moteur : 0 position `user_confirmed` sur LINK de tout temps ; 0 position et 0 ordre du portefeuille de base sur LINK entre 19:35 et 19:50 ce jour-là ; aucun `paper_positions.decision_id` renseigné (le lien journal↔moteur n'est pas stocké) ; aucune écriture comptable (le journal comptable n'est pas en production).
- Réparation **préparée, non appliquée** : `confirmed → archived` avec note, sans suppression, avec garde, requête de contrôle et retour arrière.
- AVAX (`b454b835…`, 19/09 19:32) a une position historique AVAX ouverte le 18/09 18:38 (sans quantité) : non orpheline au sens strict, mais cette position est non financée (§8).

## 6. Réconciliation des versions

Comparaison à trois (HEAD git / arbre local / arbre du VPS `/opt/ichivol`) sur 317 fichiers (engine/app, migrations, src, server/src) : **36 diffèrent**.

| Catégorie | Fichiers | Décision |
|---|---|---|
| Reliquats VPS supprimés du dépôt | `market_data/mt5.py`, `pages/PaperTechPage.tsx` | **Ne pas restaurer.** Retirés du dépôt volontairement (269a02b, 7899dc8), non référencés sur le VPS. À supprimer du VPS au prochain déploiement complet ; l'historique git les conserve |
| Copie de mon travail broker déjà poussée sur l'hôte à 17:47 (non validée) | `brokerage/*`, `binance_quotes`, `contracts`, `quality`, migration `e5f6a7b8c9d0`, `db/models.py`, `universe/types.py`, `api/routes.py` | **Danger** : voir §6.1 |
| Versions hôte différentes de HEAD **et** du local | `config.py`, `paper/broker.py`, `paper/engine.py`, `screener/service.py` | Fusionner : le local est un sur-ensemble (verrou consultatif, timing, protection, valeurs par défaut) |
| Local modifié, non déployé | `api/serializers.py`, `main.py`, `paper/{intent,risk,protection,counters,gates}.py`, `screener/timing.py`, `indicators/{best_cloud,ppo}.py`, 5 fichiers `strategy_lab`, `DecisionsPage.tsx` | À livrer dans l'ordre du §6.2 |

### 6.1 Risque immédiat

Le VPS contient déjà le code broker/ledger sur l'hôte alors que l'**image en marche ne l'a pas**. Le script d'entrée du moteur exécute `alembic upgrade head` à chaque démarrage : **la prochaine reconstruction du moteur créera les tables du journal comptable et activera la double écriture en production**, sans essai à blanc. Tant que la version cohérente ci-dessous n'est pas validée, **ne pas reconstruire ni relancer l'image du moteur**. L'autre session Claude active (`ichivol-69`) s'est engagée à ne pas le faire.

### 6.2 Version cohérente à livrer (schéma et code)

- **Schéma requis** : Alembic `e5f6a7b8c9d0` (tables `ledger_transactions`, `ledger_legs` ; **purement additive**, testée montée/descendue/remontée sur une copie de production : empreintes des positions, portefeuilles, ordres, journal identiques avant/après). Production actuelle : `d4e5f6a7b8c9`.
- **Ordre de livraison proposé** (chaque étape commit + essai à blanc) :
  1. Correctifs sans schéma : verrou par symbole, `min_fill_fraction`, `signal_timing`/`stale_data`, front (ordre ouvrir→journal, bannière d'erreur).
  2. Surveillance des protections (`enable_protection_monitor`), d'abord en `dry_run` sur la production pour rapporter, puis active.
  3. Journal comptable + migration + double écriture (après validation de la copie, avec ouverture `CORRECTION` par portefeuille).
  4. Profils de frais versionnés / exécution sur cotation, portefeuilles opt-in seulement.
- **Ce que je n'ai pas fait** : aucun commit ni branche. L'arbre partagé contient le travail de plusieurs sessions (`ichivol-69` : `counters/gates`, `research_lab`, hooks dans `paper/engine.py` ; Cursor : Synthèse/BrokerAccount). Les fichiers `paper/engine.py` et `DecisionsPage.tsx` mélangent plusieurs auteurs, donc un commit unilatéral ne serait pas propre. Un manifeste par fichier est reproductible via le script de comparaison (`threeway.py`, dossier scratchpad de session) ; à figer dans git par chaque auteur dans l'ordre ci-dessus.
- Les sauvegardes (`/opt/ichivol/.backup-20260920-decisions-fix`) ne constituent pas une version reproductible : le VPS n'est **pas** un dépôt git et l'hôte est modifié par plusieurs acteurs (constaté à 17:47 : fichiers moteur remplacés + web reconstruit sans lien avec ma session).

## 7. Inventaire du nouveau broker

E = existe (code) · I = implémenté (fonctionne isolément) · T = testé · Int = intégré au broker existant · D = déployé en production.

| Composant | E | I | T | Int | D | Remarque |
|---|---|---|---|---|---|---|
| Journal comptable (ledger) | ✔ | ✔ | ✔ (DB) | ✔ double écriture open/close | ✘ | migration prête, non appliquée |
| Réconciliation ledger↔cash | ✔ | ✔ | ✔ (12/12 portefeuilles, copie prod) | ✔ | ✘ | `portfolio.cash` reste la valeur opérationnelle ; ledger = dérivé réconcilié |
| Cotations bid/ask | ✔ (Binance) | ✔ | ✔ + essai réel | ✘ (opt-in `quote_paper`) | ✘ | aucun flux normal ne l'utilise |
| Modèle d'exécution | ✔ | ✔ | ✔ | partiel (via `quote=` du broker) | ✘ | bougies seules : friction configurée en bps |
| Commissions versionnées | ✔ | ✔ | ✔ | ✔ (si `fee_profile_id`) | ✘ | **barème Binance = hypothèse non vérifiée** |
| Autres frais (financement, marge, conversion) | ✔ (conversion) | partiel | ✔ (min. par ordre, fills partiels) | ✘ | ✘ | financement, marge, règlement absents |
| Gestion des positions | ✔ | ✔ | ✔ | ✔ | ✔ (ancienne version) | verrou par symbole : local seulement |
| Stops et objectifs | ✔ | ✔ | ✔ | ✔ (boucle 60 s) | ✘ | ancien contrôle sur échantillon : en production |
| Limites de risque | partiel | partiel | ✔ | ✔ | ✔ (anciennes) | plafond **par ordre** ; ajout par-symbole (verrou) et lot minimal locaux ; pas de plafond d'exposition globale ni de perte journalière |
| Migrations | ✔ | ✔ | ✔ (copie prod, aller-retour) | — | ✘ | additive ; aucune donnée existante touchée |
| Compatibilité données actuelles | ✔ | ✔ | ✔ | — | — | positions historiques sans quantité = « non financées » |

**Deux sources de vérité comptable ?** Non, par construction : le solde opérationnel reste `paper_portfolios.cash` ; le ledger n'est qu'une écriture dérivée, initialisée avec le solde courant en cause `CORRECTION` (jamais un faux dépôt) et vérifiée par `is_reconciled`. Un basculement (ledger source de vérité) est une étape ultérieure distincte.

## 8. Comptabilité et Synthèse

Portefeuille de base, production à 19:05 UTC (identités vérifiées sur les données) :

| Poste | Valeur |
|---|---|
| Liquidités (`cash`) | 2 611,11 € |
| Coût des positions ouvertes (`investi`) | 2 474,86 € (NEAR 1 222,15 + APT 1 252,71) |
| Latent | +18,11 € (NEAR −3,62 + APT +21,73) |
| Réalisé | +87,21 € = somme exacte des 138 positions fermées |
| Valeur totale (`equity`) | 5 104,09 € = 2 611,11 + 2 474,86 + 18,11 |
| Résultat total | +104,09 € |
| Frais d'entrée des positions ouvertes | 1,24 € (NEAR 0,6111 + APT 0,6264) |

- `cash = capital + réalisé − investi − frais d'entrée ouverts` : 5 000 + 87,21 − 2 474,86 − 1,24 = **2 611,11 € (exact)**.
- **Écart d'affichage** : réalisé + latent = 105,32 € ≠ résultat total 104,09 €. Différence 1,23 € = frais d'entrée des lots ouverts : ils sont déjà payés (débités du cash) mais ne passent dans le « réalisé » qu'à la fermeture. Ce n'est pas une erreur comptable, c'est une ligne **non affichée** (le travail parallèle en cours ajoute `open_entry_fees` / `pnl_explained` à l'API).
- **Les 1,86 € de la capture** : je n'ai pas la capture ni son horodatage ; les instantanés d'équité ne permettent pas de la retrouver précisément. L'explication est la même : la somme des frais d'entrée des lots financés ouverts à ce moment-là. Trois lots de ~0,62 € chacun donnent 1,86 € ; à vérifier sur l'instantané exact si vous me donnez l'heure.
- **Cartes AVAX et LTC sans montant** : positions historiques (18/09) **sans quantité ni notionnel**, sans stop ni objectif. Elles n'ont **aucun effet sur le cash ni sur le réalisé/latent financiers** (`realized_pnl` nul, pas de débit). Elles sont comptées dans « 4 positions ouvertes » alors que **2** sont financées, ce qui prête à confusion. 115 des 138 positions fermées du portefeuille de base sont dans le même cas : ce sont des **performances de signal**, pas des positions financées. Le tableau de bord doit les afficher comme telles (le travail parallèle expose `valuation_status = missing_qty`) ; l'API ne fournit pas encore un compteur « positions financées » dédié.

## 9. Synthèse

**Fonctionne et vérifié** : parcours d'ouverture (acceptation, refus, double clic, concurrence) ; comptabilité du portefeuille de base (identités exactes) ; migration additive sur copie ; réconciliation du journal (12/12) ; reconstruction APT.

**Défauts confirmés** : (1) stops/objectifs non surveillés entre rafraîchissements et absents pour les positions confirmées manuellement (APT dépasse son objectif le 19/09 04:15) ; (2) doublon NEAR par absence du verrou inter-sources dans l'image en marche ; (3) double clic simultané pouvant créer deux lots ; (4) lot « poussière » quand le cash manque ; (5) écrasement d'une confirmation existante par une tentative refusée ; (6) frais d'entrée ouverts non affichés dans la Synthèse ; (7) positions non financées comptées comme positions.

**Corrigé et testé (local)** : 1, 3, 4, 5 côté moteur/front ; 2 côté code ; 223 tests passent, `tsc` OK.
**Déployé** : uniquement les correctifs de 17:33 (décisions sur bougies clôturées, bannière d'erreur, compensation journal — cette dernière remplacée localement par l'ordre ouvrir→journal).
**Préparé, non déployé** : verrou par symbole, lot minimal, `signal_timing`, surveillance des protections, ledger et migration, réparation LINK.
**Réparations de données proposées** : archivage de la confirmation LINK (script prêt). Aucune autre : APT, NEAR et l'historique ne sont pas réécrits.

## 10. Prochaine étape concrète pour un broker virtuel opérationnel

1. Vous validez : (a) l'archivage LINK, (b) le passage de la surveillance en essai à blanc en production.
2. Figer dans git, dans l'ordre du §6.2, les correctifs sans schéma puis la surveillance ; reconstruire **une seule fois** l'image moteur à partir d'un commit, avec `alembic` déjà validé.
3. Décider du sort d'APT (fermer à l'objectif du 19/09 par correction explicite, ou laisser vivre) : décision de gestion, pas une correction automatique.
4. Puis seulement : brancher les cotations et les frais versionnés sur un portefeuille opt-in, vérifier le barème Binance, et étendre aux autres classes d'actifs.

## Erratum et incident du 20/09 à 19:55 UTC (après le déploiement D1)

- **Incident** : 30 s après le redémarrage de D1 (19:55:03), la boucle automatique a fermé **4 positions confirmées manuellement** du portefeuille de base avec `pipeline_downgraded` : APT (sortie 0,75062, **+37,01 €**), NEAR (4,15592, **+26,40 €**), LTC et AVAX (positions historiques sans quantité, sans effet financier). Portefeuille de base désormais à plat.
- **Cause** : la recherche « un lot par symbole, toutes sources » (ajoutée à `sync_position`, embarquée dans D1) rend les lots `user_confirmed` visibles à la boucle automatique, qui applique alors la sortie sur signal. Avant, les lots manuels n'étaient jamais touchés par cette boucle.
- **Mon erreur** : mes tests couvraient l'ouverture, pas la fermeture de lots manuels par la boucle automatique, et j'ai écrit « aucune position n'a été fermée » sans vérifier les fermetures après le redémarrage. Cette affirmation était fausse.
- **Correctif préparé** (non déployé) : `sync_position` ne ferme plus, sur signal, un lot d'une autre source ; seuls ses stop/objectif (contrôle existant + surveillance des protections) ou l'utilisateur peuvent le fermer. Test de régression (échoue sans le correctif, passe avec). Branche `release/d1b-2026-09-20`.
- **Données** : aucune réécriture ; les 4 fermetures restent dans l'historique.

