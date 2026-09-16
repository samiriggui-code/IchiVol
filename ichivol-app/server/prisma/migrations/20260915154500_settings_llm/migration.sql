-- AlterTable
ALTER TABLE "settings" ADD COLUMN "llmProvider" TEXT NOT NULL DEFAULT 'openrouter';
ALTER TABLE "settings" ADD COLUMN "llmModel" TEXT NOT NULL DEFAULT 'openai/gpt-4o-mini';
ALTER TABLE "settings" ADD COLUMN "llmApiKeyEnc" TEXT;
