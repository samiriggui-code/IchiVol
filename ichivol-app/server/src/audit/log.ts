import { db } from '../db.js'

export async function writeAuditLog(input: {
  userId?: string | null
  action: string
  meta?: Record<string, unknown>
}) {
  return db.auditLog.create({
    data: {
      userId: input.userId ?? null,
      action: input.action,
      meta: input.meta ? (JSON.parse(JSON.stringify(input.meta)) as object) : undefined,
    },
  })
}
