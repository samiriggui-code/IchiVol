-- RÉPARATION (données) — NON APPLIQUÉE. Le propriétaire décide de la lancer.
-- Base : ichivol_engine (moteur). Compte paper : ICHIVOL_WIDE_V1 uniquement.
--
-- Incident (lu en production le 27/10/2026, lecture seule) : deux ventes à découvert user_confirmed,
-- APTUSDT (03:02:23) et AAVEUSDT (03:02:36), ~6 200 € chacune. Le relevé de 03:02:39 comptait la caisse
-- d'avant AAVE (6 209 €) mais les deux positions (24 889 €) : ~6 200 € fantômes, +24 % affichés
-- (compute_portfolio_performance prend l'equity du dernier relevé).
--
-- Cause (branche fix/caisse-ordres-simultanes) : snapshot_equity lisait portfolio.cash sur l'objet chargé
-- plus tôt dans le cycle de scan, et les positions par une requête fraîche. Les ouvertures et clôtures
-- prennent un verrou de ligne depuis le 20/09 : paper_portfolios.cash devrait donc être juste ; seul le
-- financement de nuit pouvait encore l'écraser. Ce script le VÉRIFIE au lieu de le supposer :
--   A. caisse attendue = capital initial + PnL réalisé des lots clos
--                        − Σ (mise + frais d'entrée + financement payé) des lots ouverts.
--      La caisse n'est corrigée que si l'écart vaut exactement la mise (+ frais) d'APTUSDT, d'AAVEUSDT
--      ou des deux. Tout autre écart est seulement signalé (WARNING) : à analyser à la main.
--   B. relevés depuis l'ouverture d'APTUSDT : caisse recalculée à l'instant du relevé. Seuls les relevés
--      dont l'écart vaut exactement une de ces mises sont corrigés (caisse et equity), puis le drawdown
--      est recalculé (le pic gonflé par le relevé fantôme fausserait sinon tous les drawdowns suivants).
-- Limite : la valeur des ventes à découvert dans les relevés historiques (gain latent omis, défaut corrigé
-- dans le code) n'est pas recalculée ici : les cours de l'époque ne sont pas stockés.
--
-- MODE D'EMPLOI
--   1. Déployer d'abord le correctif (sinon un cycle de scan peut réécrire un relevé faux), ou arrêter
--      le moteur pendant la réparation.
--   2. psql -v ON_ERROR_STOP=1 -d ichivol_engine -f 2026-10-27_wide_v1_caisse_et_releves.sql
--      Le script finit par ROLLBACK : rien n'est écrit. Lire les blocs « AVANT » / « APRÈS ».
--   3. Si tout est conforme, remplacer la dernière ligne « ROLLBACK; » par « COMMIT; » et relancer.

\set ON_ERROR_STOP on

BEGIN;

-- Verrou du compte : aucune ouverture, clôture ni relevé du moteur ne s'intercale pendant la réparation.
SELECT id FROM paper_portfolios WHERE code = 'ICHIVOL_WIDE_V1' FOR UPDATE;

-- Les deux lots de l'incident (identifiés sans dépendre du fuseau des heures citées).
CREATE TEMP TABLE wide_lots ON COMMIT DROP AS
SELECT p.id, p.symbol, p.entry_time, p.notional + p.entry_fee AS stake
  FROM paper_positions p JOIN paper_portfolios pf ON pf.id = p.portfolio_id
 WHERE pf.code = 'ICHIVOL_WIDE_V1'
   AND p.symbol IN ('APTUSDT', 'AAVEUSDT') AND p.direction = 'SHORT' AND p.source = 'user_confirmed'
   AND p.entry_time >= timestamptz '2026-10-26 22:00+00' AND p.entry_time < timestamptz '2026-10-27 06:00+00';

DO $$ BEGIN
  IF (SELECT count(*) FROM wide_lots) <> 2 THEN
    RAISE EXCEPTION 'attendu 2 lots (APTUSDT, AAVEUSDT) du 27/10 sur ICHIVOL_WIDE_V1, trouvé %',
      (SELECT count(*) FROM wide_lots);
  END IF;
END $$;

-- Caisse qu'aurait le compte à l'instant t, d'après les seuls lots (lots capital : qty non nulle).
CREATE FUNCTION pg_temp.wide_cash_at(t timestamptz) RETURNS double precision LANGUAGE sql STABLE AS $f$
  SELECT pf.initial_cash
       + COALESCE((SELECT sum(COALESCE(p.realized_pnl, 0)) FROM paper_positions p
                    WHERE p.portfolio_id = pf.id AND p.qty IS NOT NULL
                      AND p.status = 'CLOSED' AND p.exit_time <= t), 0)
       - COALESCE((SELECT sum(COALESCE(p.notional, 0) + COALESCE(p.entry_fee, 0)) FROM paper_positions p
                    WHERE p.portfolio_id = pf.id AND p.qty IS NOT NULL AND p.entry_time <= t
                      AND (p.exit_time IS NULL OR p.exit_time > t)), 0)
       - COALESCE((SELECT sum((e.payload ->> 'charge')::double precision)
                     FROM paper_journal_events e JOIN paper_positions p ON p.id = e.position_id
                    WHERE e.portfolio_id = pf.id AND e.event_type = 'FINANCING' AND e.created_at <= t
                      AND (p.exit_time IS NULL OR p.exit_time > t)), 0)
    FROM paper_portfolios pf WHERE pf.code = 'ICHIVOL_WIDE_V1'
$f$;

-- Un écart est « celui de l'incident » s'il vaut la mise d'APT, d'AAVE ou des deux (à 5 centimes près).
CREATE FUNCTION pg_temp.wide_is_incident_gap(gap double precision) RETURNS boolean LANGUAGE sql STABLE AS $f$
  SELECT abs(gap - (SELECT stake FROM wide_lots WHERE symbol = 'APTUSDT')) < 0.05
      OR abs(gap - (SELECT stake FROM wide_lots WHERE symbol = 'AAVEUSDT')) < 0.05
      OR abs(gap - (SELECT sum(stake) FROM wide_lots)) < 0.05
$f$;

-- ─── AVANT ────────────────────────────────────────────────────────────────────────────────────────
\echo '=== AVANT : compte ==='
SELECT code, initial_cash, cash, realized_pnl,
       pg_temp.wide_cash_at(now())        AS caisse_attendue,
       cash - pg_temp.wide_cash_at(now()) AS ecart
  FROM paper_portfolios WHERE code = 'ICHIVOL_WIDE_V1';

\echo '=== AVANT : lots ouverts ==='
SELECT p.symbol, p.direction, p.source, p.entry_time, p.qty, p.initial_qty, p.notional, p.entry_fee
  FROM paper_positions p JOIN paper_portfolios pf ON pf.id = p.portfolio_id
 WHERE pf.code = 'ICHIVOL_WIDE_V1' AND p.status = 'OPEN' AND p.qty IS NOT NULL
 ORDER BY p.entry_time;

\echo '=== AVANT : relevés (5 avant l incident, puis tous depuis) ; ecart attendu ~0 avant 03:02 ==='
SELECT s.timestamp, s.cash, s.positions_value, s.equity, s.drawdown_pct,
       pg_temp.wide_cash_at(s.timestamp)            AS caisse_recalculee,
       s.cash - pg_temp.wide_cash_at(s.timestamp)   AS ecart,
       pg_temp.wide_is_incident_gap(s.cash - pg_temp.wide_cash_at(s.timestamp)) AS a_corriger
  FROM paper_equity_snapshots s JOIN paper_portfolios pf ON pf.id = s.portfolio_id
 WHERE pf.code = 'ICHIVOL_WIDE_V1'
   AND (s.timestamp >= (SELECT min(entry_time) FROM wide_lots)
        OR s.id IN (SELECT s2.id FROM paper_equity_snapshots s2
                     WHERE s2.portfolio_id = pf.id AND s2.timestamp < (SELECT min(entry_time) FROM wide_lots)
                     ORDER BY s2.timestamp DESC LIMIT 5))
 ORDER BY s.timestamp;

-- ─── A. Caisse du compte ──────────────────────────────────────────────────────────────────────────
DO $$
DECLARE
  v_pid      text;
  v_cur      text;
  v_cash     double precision;
  v_expected double precision := pg_temp.wide_cash_at(now());
  v_gap      double precision;
  v_ledger   numeric;
BEGIN
  SELECT id, currency, cash INTO v_pid, v_cur, v_cash FROM paper_portfolios WHERE code = 'ICHIVOL_WIDE_V1';
  v_gap := v_cash - v_expected;
  IF abs(v_gap) < 0.01 THEN
    RAISE NOTICE 'A. caisse juste (% €, écart % €) : rien à corriger', round(v_cash::numeric, 2), round(v_gap::numeric, 4);
    RETURN;
  END IF;
  IF NOT pg_temp.wide_is_incident_gap(v_gap) THEN
    RAISE WARNING 'A. écart de % € qui ne correspond pas à l incident : caisse NON corrigée, à analyser',
      round(v_gap::numeric, 2);
    RETURN;
  END IF;

  UPDATE paper_portfolios SET cash = v_expected, updated_at = now() WHERE id = v_pid;
  INSERT INTO paper_journal_events (id, portfolio_id, position_id, event_type, payload, created_at)
  VALUES (gen_random_uuid()::text, v_pid, NULL, 'CASH_CORRECTION',
          json_build_object('reason', 'lost update 2026-10-27 (APTUSDT/AAVEUSDT opened 13 s apart)',
                            'cash_before', v_cash, 'cash_after', v_expected, 'delta', -v_gap,
                            'script', 'scripts/repairs/2026-10-27_wide_v1_caisse_et_releves.sql'),
          now());
  RAISE NOTICE 'A. caisse corrigée : % € -> % € (delta % €)',
    round(v_cash::numeric, 2), round(v_expected::numeric, 2), round((-v_gap)::numeric, 2);

  -- Grand livre (s'il est déployé et déjà utilisé par ce compte) : écriture de correction explicite.
  IF to_regclass('ledger_transactions') IS NOT NULL THEN
    EXECUTE 'SELECT sum(l.amount) FROM ledger_legs l JOIN ledger_transactions t ON t.id = l.transaction_id
              WHERE t.portfolio_id = $1 AND l.currency = $2'
       INTO v_ledger USING v_pid, v_cur;
    IF v_ledger IS NOT NULL AND abs(v_ledger - v_expected::numeric) > 0.0001 THEN
      EXECUTE 'WITH tx AS (
                 INSERT INTO ledger_transactions (id, portfolio_id, key, ref, ts)
                 VALUES (gen_random_uuid()::text, $1, ''correction:2026-10-27:lost-update'', NULL, now())
                 RETURNING id)
               INSERT INTO ledger_legs (id, transaction_id, seq, currency, amount, cause, memo)
               SELECT gen_random_uuid()::text, tx.id, 0, $2, $3, ''correction'',
                      ''lost update 2026-10-27 (APTUSDT/AAVEUSDT)'' FROM tx'
        USING v_pid, v_cur, (v_expected::numeric - v_ledger);
      RAISE NOTICE 'A. grand livre : correction de % €', round(v_expected::numeric - v_ledger, 2);
    END IF;
  END IF;
END $$;

-- ─── B. Relevés fantômes ──────────────────────────────────────────────────────────────────────────
CREATE TEMP TABLE wide_bad_snaps ON COMMIT DROP AS
SELECT s.id, s.cash - pg_temp.wide_cash_at(s.timestamp) AS gap
  FROM paper_equity_snapshots s JOIN paper_portfolios pf ON pf.id = s.portfolio_id
 WHERE pf.code = 'ICHIVOL_WIDE_V1'
   AND s.timestamp >= (SELECT min(entry_time) FROM wide_lots)
   AND pg_temp.wide_is_incident_gap(s.cash - pg_temp.wide_cash_at(s.timestamp));

\echo '=== B. relevés corrigés (nombre) ==='
UPDATE paper_equity_snapshots s
   SET cash = s.cash - b.gap, equity = s.equity - b.gap
  FROM wide_bad_snaps b WHERE b.id = s.id;

-- Drawdown recalculé comme snapshot_equity : equity / max(capital initial, plus haut equity jusque-là) − 1.
UPDATE paper_equity_snapshots s
   SET drawdown_pct = r.dd
  FROM (SELECT s2.id,
               s2.equity / GREATEST(pf.initial_cash,
                                    max(s2.equity) OVER (ORDER BY s2.timestamp, s2.id
                                                         ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)) - 1 AS dd,
               s2.timestamp
          FROM paper_equity_snapshots s2 JOIN paper_portfolios pf ON pf.id = s2.portfolio_id
         WHERE pf.code = 'ICHIVOL_WIDE_V1') r
 WHERE r.id = s.id AND r.timestamp >= (SELECT min(entry_time) FROM wide_lots);

-- ─── APRÈS ────────────────────────────────────────────────────────────────────────────────────────
\echo '=== APRÈS : compte (ecart doit valoir 0) ==='
SELECT code, initial_cash, cash, realized_pnl,
       pg_temp.wide_cash_at(now())        AS caisse_attendue,
       cash - pg_temp.wide_cash_at(now()) AS ecart
  FROM paper_portfolios WHERE code = 'ICHIVOL_WIDE_V1';

\echo '=== APRÈS : relevés depuis l incident (ecart doit valoir 0, sauf écarts signalés hors incident) ==='
SELECT s.timestamp, s.cash, s.positions_value, s.equity, s.drawdown_pct,
       s.cash - pg_temp.wide_cash_at(s.timestamp) AS ecart,
       s.equity / pf.initial_cash - 1             AS rendement
  FROM paper_equity_snapshots s JOIN paper_portfolios pf ON pf.id = s.portfolio_id
 WHERE pf.code = 'ICHIVOL_WIDE_V1' AND s.timestamp >= (SELECT min(entry_time) FROM wide_lots)
 ORDER BY s.timestamp;

-- Par défaut : rien n'est écrit. Remplacer par COMMIT; une fois les sorties vérifiées.
ROLLBACK;
