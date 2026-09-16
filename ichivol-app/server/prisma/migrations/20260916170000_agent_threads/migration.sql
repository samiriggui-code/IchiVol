-- CreateTable
CREATE TABLE IF NOT EXISTS "agent_threads" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "title" TEXT,
    "assumedSymbol" TEXT,
    "assumedTimeframe" TEXT,
    "pendingIntent" TEXT,
    "lastMode" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "agent_threads_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE IF NOT EXISTS "agent_messages" (
    "id" TEXT NOT NULL,
    "threadId" TEXT NOT NULL,
    "role" TEXT NOT NULL,
    "content" TEXT NOT NULL,
    "mode" TEXT,
    "intent" TEXT,
    "citations" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "agent_messages_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX IF NOT EXISTS "agent_threads_userId_updatedAt_idx" ON "agent_threads"("userId", "updatedAt");

-- CreateIndex
CREATE INDEX IF NOT EXISTS "agent_messages_threadId_createdAt_idx" ON "agent_messages"("threadId", "createdAt");

-- AddForeignKey
DO $$ BEGIN
  ALTER TABLE "agent_threads" ADD CONSTRAINT "agent_threads_userId_fkey"
    FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  ALTER TABLE "agent_messages" ADD CONSTRAINT "agent_messages_threadId_fkey"
    FOREIGN KEY ("threadId") REFERENCES "agent_threads"("id") ON DELETE CASCADE ON UPDATE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
