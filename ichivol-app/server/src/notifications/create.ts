import { Prisma } from '@prisma/client'
import { db } from '../db.js'

export type NotificationKind = 'journal_confirm' | 'pipeline_change' | 'system_alert' | 'system_digest'

export async function createNotification(input: {
  userId: string
  kind: NotificationKind
  title: string
  body: string
  payload?: Record<string, unknown>
}): Promise<void> {
  await db.notification.create({
    data: {
      userId: input.userId,
      kind: input.kind,
      title: input.title.slice(0, 200),
      body: input.body.slice(0, 1000),
      payload: input.payload
        ? (input.payload as Prisma.InputJsonValue)
        : undefined,
    },
  })
}
