-- Chantier 2 E0 — AgentTask queue + AgentLog audit (Comp AI claim/lease pattern)

CREATE TABLE "agent_tasks" (
    "id" TEXT NOT NULL,
    "agentId" TEXT NOT NULL,
    "kind" TEXT NOT NULL,
    "symbol" TEXT,
    "payload" JSONB,
    "condition" JSONB,
    "dueAt" TIMESTAMP(3) NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "leaseUntil" TIMESTAMP(3),
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "idempotencyKey" TEXT NOT NULL,
    "result" JSONB,
    "error" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "agent_tasks_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "agent_logs" (
    "id" TEXT NOT NULL,
    "agentId" TEXT NOT NULL,
    "level" TEXT NOT NULL,
    "source" TEXT NOT NULL,
    "message" TEXT NOT NULL,
    "decisionId" TEXT,
    "positionId" TEXT,
    "taskId" TEXT,
    "meta" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "agent_logs_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "agent_tasks_idempotencyKey_key" ON "agent_tasks"("idempotencyKey");
CREATE INDEX "agent_tasks_status_dueAt_idx" ON "agent_tasks"("status", "dueAt");
CREATE INDEX "agent_tasks_leaseUntil_idx" ON "agent_tasks"("leaseUntil");
CREATE INDEX "agent_tasks_agentId_kind_symbol_idx" ON "agent_tasks"("agentId", "kind", "symbol");

CREATE INDEX "agent_logs_agentId_createdAt_idx" ON "agent_logs"("agentId", "createdAt");
CREATE INDEX "agent_logs_taskId_createdAt_idx" ON "agent_logs"("taskId", "createdAt");
CREATE INDEX "agent_logs_level_createdAt_idx" ON "agent_logs"("level", "createdAt");

ALTER TABLE "agent_logs" ADD CONSTRAINT "agent_logs_taskId_fkey"
  FOREIGN KEY ("taskId") REFERENCES "agent_tasks"("id") ON DELETE SET NULL ON UPDATE CASCADE;
