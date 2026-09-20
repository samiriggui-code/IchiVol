# Revue lecture seule — D2 (grand livre) avant mise en production

**Auteur :** ichivol-36 · **Date :** 2026-09-20 · **Périmètre lu :** migration `e5f6a7b8c9d0`, `app/brokerage/*`, ajouts du grand livre dans `app/paper/broker.py`, modèles `LedgerTransaction` / `LedgerLeg`. Rien modifié, rien déployé, aucune base de production touchée.

**Vérifications exécutées :**
- `pytest tests/brokerage` : 26 tests passent.
- Migration sur une base SQLite jetable (marquée à `d4e5f6a7b8c9`) : `upgrade head` → `downgrade -1` → `upgrade head` fonctionnent, les deux tables et la contrainte `uq_ledger_portfolio_key` sont créées, puis retirées. **Postgres non exécuté** (pas d'accès de ma part) ; SQLite ne peut pas rejouer la chaîne complète (une ancienne migration utilise `ALTER` de contrainte).
- Formule P&L des shorts et `to_decimal(NaN)` calculés directement (voir M2, M3).

## Verdict

- **Migration : OK pour la production.** Purement additive (deux `CREATE TABLE`), l'entrée `docker-entrypoint.sh` lance `alembic upgrade head` avant l'application.
- **Code du grand livre : conditionnel.** Avant de l'activer, corriger H2 et H3 et M3 ; décider du mode d'échec (H1). M1, M2 peuvent suivre mais doivent être documentés pour que « réconcilié » ne soit pas lu comme une validation économique.

## À traiter avant l'activation

| # | Sujet | Constat | Correctif proposé |
|---|---|---|---|
| **H1** | **Couplage de disponibilité** | `open_capital_position` / `close_capital_position` écrivent dans le grand livre **dans la même transaction**, sans condition. Toute erreur du livre (table absente, `DuplicateConflict`, valeur invalide) annule le trade. Déployer le code sans la migration, ou faire un `downgrade` code présent, casse **toutes** les ouvertures et fermetures. | Décider explicitement : mode strict (voulu) ou « double écriture non bloquante » dans un `SAVEPOINT` (`session.begin_nested()`) avec événement journal `LEDGER_ERROR`, strict après ~2 semaines sans écart. Ordre de déploiement : migration d'abord (l'entrypoint le fait), jamais de `downgrade` sous code D2. |
| **H2** | **L'idempotence ne protège pas là où on l'attend** | Clé d'ouverture `open:{position.id}` avec un `id` fraîchement généré : **elle ne peut jamais entrer en collision**, donc elle n'empêche ni la double ouverture (même signal traité deux fois, relance après timeout, deux workers). `close:{position.id}` ne protège que le livre : `portfolio.cash` est modifié **avant** le `post`, donc une fermeture rejouée crédite deux fois la trésorerie (ou lève `DuplicateConflict` après mutation). Les appelants principaux vérifient `status == OPEN`, mais `quote_paper.close_at_market` et `close_capital_position` elle-même n'ont pas de garde. | (a) Clé d'ouverture au niveau de la **décision** : `open:{portfolio_id}:{decision_id ou signal_key}`. (b) Première ligne de `close_capital_position` : `if position.status != "OPEN": return position`. (c) Verrou de ligne (`SELECT … FOR UPDATE`) sur la position. |
| **H3** | **Trésorerie sans verrou** | `portfolio.cash -= …` est un lecture-modification-écriture sur un flottant, sans verrou de ligne sur `PaperPortfolio` (le `with_for_update` de `paper/engine.py` ne verrouille que les positions par symbole). Deux sessions concurrentes (synchro automatique + confirmation utilisateur) → mise à jour perdue ; le livre enregistre les deux jambes, `cash` en perd une → `MISMATCH`. Idem pour le plafond `max_open_positions` (`_count_open`). | `session.get(PaperPortfolio, id, with_for_update=True)` au début de l'ouverture et de la fermeture. |
| **M3** | **Valeurs non finies acceptées** | `to_decimal(float('nan'))` renvoie `Decimal('NaN')` (vérifié) ; Postgres `numeric` accepte NaN : une jambe NaN empoisonne `balances()` et `reconcile`. | `math.isfinite` avant toute mutation de trésorerie, lever une erreur explicite. |

## À planifier

| # | Sujet | Constat | Correctif proposé |
|---|---|---|---|
| **M1** | Réconciliation tautologique à la fermeture | Jambe d'exécution de clôture = `to_decimal(portfolio.cash - cash_before + exit_fee)` : le livre est dérivé du **delta de trésorerie**, donc `reconcile` ne peut pas détecter une formule de P&L fausse (elle détecte une dérive à l'ouverture ou une modification externe de `cash`). | Calculer les jambes depuis `qty × exit_fill` en `Decimal`, indépendamment de `portfolio.cash`, puis vérifier que le delta de trésorerie est égal (assertion). |
| **M2** | **P&L des shorts faux (défaut préexistant, non introduit par D2)** | `broker.py` calcule `entry_price / exit_fill − 1` au lieu de `(entry − exit) / entry`. Hausse de +10 % : lu −9,09 % au lieu de −10 % ; baisse de −10 % : lu +11,1 % au lieu de +10 % (biais favorable aux shorts, ≈ x² : 0,01–0,04 % du notionnel sur des mouvements d'ATR). En plus, `realized` des shorts **omet le frais d'entrée** alors que celui des longs l'inclut : `portfolio.realized_pnl` surévalué du frais d'entrée par short (la trésorerie, elle, est juste). Le simulateur de recherche utilise la bonne formule. | Corriger avant toute expérience avec shorts ; sans effet sur `FWD_E_LONG` (longs seulement). Le grand livre **ne le détectera pas** (M1). |
| **M4** | Ouverture paresseuse du livre | `ensure_opening` s'exécute dans le chemin d'un trade : deux premiers trades concurrents d'un même portefeuille → violation d'unicité `opening:{id}` → le second trade échoue. Les fermetures de D3 sont datées dans le passé (`at=`) : le solde d'ouverture peut porter une date antérieure aux positions, et le livre n'a **aucune colonne de séquence** (seul `ts`, indexé) pour ordonner les écritures. | Initialiser les portefeuilles en amont (commande dédiée) plutôt que dans le trade ; ajouter un numéro de séquence monotone. |
| **M5** | « Append-only » par convention seulement | Aucun trigger ni retrait de droits `UPDATE/DELETE` ; pas d'`ON DELETE` sur les clés étrangères ; pas d'unicité `(transaction_id, seq)`. Aucune suppression de portefeuille n'existe dans le code aujourd'hui, donc pas de risque immédiat. | Ajouter `UNIQUE(transaction_id, seq)` ; si l'immuabilité compte, retirer `UPDATE/DELETE` au rôle applicatif. |

## Mineur / informatif

- **Arrondi** : `to_decimal` arrondit au 1e-8 (`ROUND_HALF_EVEN`), les frais `_q` en `ROUND_HALF_UP` : écart ≤ 5e-9 par jambe, tolérance de réconciliation 1e-4 → sans conséquence.
- **SQLite vs Postgres** : `post()` compare `Decimal(l.amount)` ; si un backend renvoie un flottant, `Decimal(float)` donne une valeur binaire exacte et déclenche un faux `DuplicateConflict` au rejeu. Postgres renvoie un `Decimal` : pas d'effet en production, mais un test SQLite de rejeu pourrait mentir.
- **Downgrade** : fonctionne (jambes puis transactions) mais **détruit tout l'historique comptable** ; faire un `pg_dump` avant. Le code antérieur à D2 fonctionne après le `downgrade`, le code D2 non (H1).
- **Cohérence des modèles de fill** : `execution.py` parle de demi-spread pour `candle_only`, mais `broker.py` applique `spread_bps` en entier (le simulateur de recherche fait comme le broker) ; à trancher et documenter.
- **Fermeture sur cotation** : la voie `quote` ferme toute la quantité au meilleur prix sans tenir compte de `bid_size` / `ask_size`, alors que `fill_at_quote` sait faire des exécutions partielles.
- **Points corrects** : jambes postées atomiquement avec la trésorerie dans la même session, unicité `(portfolio_id, key)`, `Numeric(28,8)`, fuseaux horaires exigés, CLI de réconciliation en lecture seule avec code de sortie 1 en cas d'écart, base actuelle du VPS non concernée tant que D2 n'est pas déployé.
