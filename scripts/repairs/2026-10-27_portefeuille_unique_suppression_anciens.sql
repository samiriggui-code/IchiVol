-- SUPPRESSION DES ANCIENS PORTEFEUILLES PAPER — NON APPLIQUÉE. Le propriétaire décide de la lancer.
-- Base : ichivol_engine (moteur). Branche : portefeuille-unique-50k (après fix/caisse-ordres-simultanes, #195).
--
-- Demande du propriétaire (27/10/2026) : « on vire tous les portefeuilles et on part sur un nouveau seul
-- portefeuille qui trade tout, 50 000 euros de monnaie virtuelle ».
-- Sauvegarde FAITE avant ce script (pg_dump -Fc des deux bases) :
--   ~/Sauvegardes/ichivol/2026-10-27_avant_portefeuille_unique/
-- Ce script ne peut pas vérifier cette sauvegarde lui-même (elle est hors du serveur de base) : il affiche
-- les compteurs AVANT par table et par compte pour qu'on les compare à la sauvegarde.
--
-- CE QUI EST SUPPRIMÉ — les 8 comptes retirés et TOUT ce qui leur est rattaché (clés étrangères réelles,
-- vérifiées sur une base migrée à la tête d'alembic) :
--   ICHIVOL_BASELINE_V1, ICHIVOL_4H_V1, ICHIVOL_WIDE_V1, ICHIVOL_SHORTS_V1, ICHIVOL_SESSIONS_V1,
--   ICHIVOL_COMBO_V1, RS_D1_PAPER_V1, FUTURES_CRYPTO_V1 (+ tout autre compte qui n'est pas ICHIVOL_MAIN_V1,
--   par ex. un compte de test oublié : listé dans le bloc AVANT).
--   ledger_legs -> ledger_transactions          (grand livre)
--   paper_partial_exits, paper_reinforce_adds   (sorties partielles, renforts)
--   paper_journal_events                        (journal : refus, entonnoir, cycles RS…)
--   paper_orders                                (ordres virtuels)
--   paper_equity_snapshots                      (relevés / courbe de capital)
--   shadow_positions                            (transactions fantômes des filtres / d'Ève / de l'audit)
--   paper_positions                             (positions, y compris les lots hérités sans compte,
--                                                portfolio_id NULL, d'avant les portefeuilles)
--   rs_book_state                               (état du livre RS-D1, clé = code du compte)
--   paper_portfolios                            (les comptes eux-mêmes)
--
-- CE QUI EST GARDÉ — les « calculs du moteur », non rattachés à un compte :
--   candles, indicator_*, strategy_signals, agent_predictions, decisions, signal_evidence (le lien
--   paper_position_id vers un lot supprimé est seulement remis à NULL), backtest_snapshots,
--   strategy_lab_experiments, analyst_snapshot, chart_object_overlays, assets,
--   eve_dossiers et eve_verdicts (aucune clé étrangère vers un compte : le code du compte n'apparaît que
--   dans le JSON decision_time_json.engine_proposals, comme trace historique).
--
-- LE NOUVEAU COMPTE : ICHIVOL_MAIN_V1 (50 000 €) est créé par le moteur lui-même au démarrage
-- (app/paper/portfolio.py, ensure_main_portfolio) avec son profil documenté. Ce script ne le crée pas
-- (le profil JSON vit dans le code) et ne le touche JAMAIS ; il affiche seulement son état.
--
-- MODE D'EMPLOI
--   1. Fusionner #195 puis portefeuille-unique-50k, déployer, vérifier que /paper/portfolios ne rend plus
--      que ICHIVOL_MAIN_V1.
--   2. Arrêter le conteneur du moteur le temps du script (docker compose stop engine) : aucun cycle ne doit
--      écrire pendant la suppression. Le script prend aussi un verrou exclusif sur les tables paper.
--   3. psql -v ON_ERROR_STOP=1 -d ichivol_engine -f 2026-10-27_portefeuille_unique_suppression_anciens.sql
--      Le script finit par ROLLBACK : rien n'est écrit. Lire les blocs AVANT / APRÈS.
--   4. Si tout est conforme, remplacer la dernière ligne « ROLLBACK; » par « COMMIT; », relancer, puis
--      redémarrer le moteur (docker compose start engine).

\set ON_ERROR_STOP on

BEGIN;

LOCK TABLE paper_portfolios, paper_positions, paper_orders, paper_journal_events, paper_equity_snapshots,
           paper_partial_exits, paper_reinforce_adds, shadow_positions, ledger_transactions, ledger_legs,
           rs_book_state
  IN ACCESS EXCLUSIVE MODE;

-- Comptes à supprimer : tout sauf le compte unique.
CREATE TEMP TABLE old_pf ON COMMIT DROP AS
SELECT id, code FROM paper_portfolios WHERE code <> 'ICHIVOL_MAIN_V1';

-- Lots à supprimer : ceux des anciens comptes + les lots hérités sans compte.
CREATE TEMP TABLE old_pos ON COMMIT DROP AS
SELECT id FROM paper_positions
 WHERE portfolio_id IN (SELECT id FROM old_pf) OR portfolio_id IS NULL;

\echo '=== AVANT : comptes présents (seul ICHIVOL_MAIN_V1 doit rester) ==='
SELECT code, label, is_active, initial_cash, cash, realized_pnl, started_at,
       CASE WHEN code = 'ICHIVOL_MAIN_V1' THEN 'GARDÉ' ELSE 'SUPPRIMÉ' END AS sort
  FROM paper_portfolios ORDER BY started_at;

\echo '=== AVANT : lignes par compte et par table ==='
SELECT pf.code,
       (SELECT count(*) FROM paper_positions x        WHERE x.portfolio_id = pf.id) AS positions,
       (SELECT count(*) FROM paper_positions x        WHERE x.portfolio_id = pf.id AND x.status = 'OPEN') AS ouvertes,
       (SELECT count(*) FROM paper_orders x           WHERE x.portfolio_id = pf.id) AS ordres,
       (SELECT count(*) FROM paper_journal_events x   WHERE x.portfolio_id = pf.id) AS journal,
       (SELECT count(*) FROM paper_equity_snapshots x WHERE x.portfolio_id = pf.id) AS releves,
       (SELECT count(*) FROM paper_partial_exits x    WHERE x.portfolio_id = pf.id) AS sorties_partielles,
       (SELECT count(*) FROM paper_reinforce_adds x   WHERE x.portfolio_id = pf.id) AS renforts,
       (SELECT count(*) FROM shadow_positions x       WHERE x.portfolio_id = pf.id) AS fantomes,
       (SELECT count(*) FROM ledger_transactions x    WHERE x.portfolio_id = pf.id) AS grand_livre_tx,
       (SELECT count(*) FROM ledger_legs l JOIN ledger_transactions t ON t.id = l.transaction_id
                                                       WHERE t.portfolio_id = pf.id) AS grand_livre_lignes,
       (SELECT count(*) FROM rs_book_state x          WHERE x.portfolio_code = pf.code) AS etat_rs
  FROM paper_portfolios pf ORDER BY pf.code;

\echo '=== AVANT : lots hérités sans compte (portfolio_id NULL), supprimés aussi ==='
SELECT count(*) AS lots_sans_compte,
       count(*) FILTER (WHERE status = 'OPEN') AS ouverts
  FROM paper_positions WHERE portfolio_id IS NULL;

\echo '=== AVANT : totaux des tables (calculs du moteur compris, pour comparaison) ==='
SELECT 'paper_portfolios' AS t, count(*) FROM paper_portfolios
UNION ALL SELECT 'paper_positions', count(*) FROM paper_positions
UNION ALL SELECT 'paper_orders', count(*) FROM paper_orders
UNION ALL SELECT 'paper_journal_events', count(*) FROM paper_journal_events
UNION ALL SELECT 'paper_equity_snapshots', count(*) FROM paper_equity_snapshots
UNION ALL SELECT 'paper_partial_exits', count(*) FROM paper_partial_exits
UNION ALL SELECT 'paper_reinforce_adds', count(*) FROM paper_reinforce_adds
UNION ALL SELECT 'shadow_positions', count(*) FROM shadow_positions
UNION ALL SELECT 'ledger_transactions', count(*) FROM ledger_transactions
UNION ALL SELECT 'ledger_legs', count(*) FROM ledger_legs
UNION ALL SELECT 'rs_book_state', count(*) FROM rs_book_state
UNION ALL SELECT 'signal_evidence (gardé)', count(*) FROM signal_evidence
UNION ALL SELECT 'signal_evidence liés à un lot supprimé (lien remis à NULL)', count(*)
            FROM signal_evidence WHERE paper_position_id IN (SELECT id FROM old_pos)
UNION ALL SELECT 'strategy_signals (gardé)', count(*) FROM strategy_signals
UNION ALL SELECT 'decisions (gardé)', count(*) FROM decisions
UNION ALL SELECT 'agent_predictions (gardé)', count(*) FROM agent_predictions
UNION ALL SELECT 'eve_dossiers (gardé)', count(*) FROM eve_dossiers
UNION ALL SELECT 'eve_verdicts (gardé)', count(*) FROM eve_verdicts
ORDER BY 1;

-- ---------------------------------------------------------------------------------------------------------
-- Suppression, des feuilles vers la racine (ordre imposé par les clés étrangères).
-- ---------------------------------------------------------------------------------------------------------
DELETE FROM ledger_legs
 WHERE transaction_id IN (SELECT id FROM ledger_transactions WHERE portfolio_id IN (SELECT id FROM old_pf));
DELETE FROM ledger_transactions WHERE portfolio_id IN (SELECT id FROM old_pf);

DELETE FROM paper_partial_exits
 WHERE portfolio_id IN (SELECT id FROM old_pf) OR position_id IN (SELECT id FROM old_pos);
DELETE FROM paper_reinforce_adds
 WHERE portfolio_id IN (SELECT id FROM old_pf) OR position_id IN (SELECT id FROM old_pos);
DELETE FROM paper_journal_events
 WHERE portfolio_id IN (SELECT id FROM old_pf) OR position_id IN (SELECT id FROM old_pos);
DELETE FROM paper_orders
 WHERE portfolio_id IN (SELECT id FROM old_pf) OR position_id IN (SELECT id FROM old_pos);
DELETE FROM paper_equity_snapshots WHERE portfolio_id IN (SELECT id FROM old_pf);
DELETE FROM shadow_positions WHERE portfolio_id IN (SELECT id FROM old_pf);

-- Preuves gardées : seul le lien vers un lot supprimé disparaît.
UPDATE signal_evidence SET paper_position_id = NULL WHERE paper_position_id IN (SELECT id FROM old_pos);

DELETE FROM paper_positions WHERE id IN (SELECT id FROM old_pos);
DELETE FROM rs_book_state WHERE portfolio_code <> 'ICHIVOL_MAIN_V1';
DELETE FROM paper_portfolios WHERE id IN (SELECT id FROM old_pf);

-- Garde-fou : plus aucune ligne paper hors du compte unique.
DO $$
DECLARE n bigint;
BEGIN
  SELECT count(*) INTO n FROM paper_positions p
   WHERE p.portfolio_id IS NULL
      OR p.portfolio_id NOT IN (SELECT id FROM paper_portfolios WHERE code = 'ICHIVOL_MAIN_V1');
  IF n > 0 THEN RAISE EXCEPTION 'il reste % lots hors ICHIVOL_MAIN_V1', n; END IF;
  SELECT count(*) INTO n FROM paper_portfolios WHERE code <> 'ICHIVOL_MAIN_V1';
  IF n > 0 THEN RAISE EXCEPTION 'il reste % anciens comptes', n; END IF;
END $$;

\echo '=== APRÈS : comptes (ICHIVOL_MAIN_V1 seul ; absent = il sera créé à 50 000 € au démarrage du moteur) ==='
SELECT code, label, is_active, initial_cash, cash, realized_pnl, started_at FROM paper_portfolios;

\echo '=== APRÈS : totaux des tables (les calculs du moteur doivent être identiques à AVANT) ==='
SELECT 'paper_portfolios' AS t, count(*) FROM paper_portfolios
UNION ALL SELECT 'paper_positions', count(*) FROM paper_positions
UNION ALL SELECT 'paper_orders', count(*) FROM paper_orders
UNION ALL SELECT 'paper_journal_events', count(*) FROM paper_journal_events
UNION ALL SELECT 'paper_equity_snapshots', count(*) FROM paper_equity_snapshots
UNION ALL SELECT 'paper_partial_exits', count(*) FROM paper_partial_exits
UNION ALL SELECT 'paper_reinforce_adds', count(*) FROM paper_reinforce_adds
UNION ALL SELECT 'shadow_positions', count(*) FROM shadow_positions
UNION ALL SELECT 'ledger_transactions', count(*) FROM ledger_transactions
UNION ALL SELECT 'ledger_legs', count(*) FROM ledger_legs
UNION ALL SELECT 'rs_book_state', count(*) FROM rs_book_state
UNION ALL SELECT 'signal_evidence (gardé)', count(*) FROM signal_evidence
UNION ALL SELECT 'strategy_signals (gardé)', count(*) FROM strategy_signals
UNION ALL SELECT 'decisions (gardé)', count(*) FROM decisions
UNION ALL SELECT 'agent_predictions (gardé)', count(*) FROM agent_predictions
UNION ALL SELECT 'eve_dossiers (gardé)', count(*) FROM eve_dossiers
UNION ALL SELECT 'eve_verdicts (gardé)', count(*) FROM eve_verdicts
ORDER BY 1;

-- Par défaut : rien n'est écrit. Remplacer par COMMIT; une fois les sorties vérifiées.
ROLLBACK;
