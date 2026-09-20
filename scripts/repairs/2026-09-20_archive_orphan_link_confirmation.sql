-- REPAIR (data) — NOT APPLIED. Present to the owner before running.
-- Target DB: ichivol (server/Prisma), table "decisions". One row, no deletion.
--
-- Record concerned (read from production 2026-09-20 ~19:20 UTC):
--   id            b263c134-40fb-432d-9b1a-ad1449a00406
--   symbol/TF     LINKUSDT / 1h        status=confirmed  gate=WATCH  signalKind=BUY
--   createdAt     2026-09-18 19:41:43  (later updatedAt values are the watch job / dedupe updates)
-- Verified in ichivol_engine (read-only):
--   * 0 paper_positions of source user_confirmed on LINKUSDT, ever
--   * 0 baseline positions and 0 baseline orders on LINKUSDT between 2026-09-18 19:35 and 19:50
--   * no paper_positions.decision_id references any decision (link is not stored engine-side)
--   * no ledger rows exist in production (ledger not deployed) => no financial movement
-- Correction: status 'confirmed' -> 'archived' with an explanatory note. History is kept.
-- The 2026-09-20 16:52 attempts did NOT create a second row (both hit the dedupe update path).

BEGIN;

-- Guard: abort unless the row is exactly the one described.
DO $$
BEGIN
  IF (SELECT count(*) FROM decisions
       WHERE id = 'b263c134-40fb-432d-9b1a-ad1449a00406'
         AND symbol = 'LINKUSDT' AND status = 'confirmed') <> 1 THEN
    RAISE EXCEPTION 'target row not found in expected state';
  END IF;
END $$;

UPDATE decisions
   SET status = 'archived',
       note   = COALESCE(NULLIF(note, '') || ' | ', '')
                || 'archived 2026-09-20: confirmation without any paper position/order (audit, no financial effect)',
       "updatedAt" = now()
 WHERE id = 'b263c134-40fb-432d-9b1a-ad1449a00406'
   AND status = 'confirmed';

-- Expect exactly 1 row updated, then:
SELECT id, symbol, status, note FROM decisions WHERE id = 'b263c134-40fb-432d-9b1a-ad1449a00406';
COMMIT;

-- ROLLBACK (manual, if needed):
--   UPDATE decisions SET status='confirmed', note=NULLIF(replace(note,' | archived 2026-09-20: confirmation without any paper position/order (audit, no financial effect)',''),''), "updatedAt"=now()
--    WHERE id='b263c134-40fb-432d-9b1a-ad1449a00406';
