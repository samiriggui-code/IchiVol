-- AlterTable
ALTER TABLE "settings" ADD COLUMN IF NOT EXISTS "llmKeysEnc" JSONB;
