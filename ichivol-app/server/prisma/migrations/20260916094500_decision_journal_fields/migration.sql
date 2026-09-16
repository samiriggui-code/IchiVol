-- AlterTable
ALTER TABLE "decisions" ADD COLUMN IF NOT EXISTS "gateDecision" TEXT;
ALTER TABLE "decisions" ADD COLUMN IF NOT EXISTS "confidence" DOUBLE PRECISION;

-- CreateIndex
CREATE INDEX IF NOT EXISTS "decisions_userId_createdAt_idx" ON "decisions"("userId", "createdAt");
