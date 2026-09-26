-- AG0: persist tool-call traces on assistant messages for full conversation rebuild.
ALTER TABLE "agent_messages" ADD COLUMN IF NOT EXISTS "meta" JSONB;
