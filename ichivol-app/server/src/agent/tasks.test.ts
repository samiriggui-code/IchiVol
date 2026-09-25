/**
 * Chantier 2 E0 — AgentTask queue integration tests (Postgres required).
 * Concurrent claim (SKIP LOCKED), crash recovery (stale lease), idempotency.
 */
process.env.JWT_SECRET ??= 'test-secret-for-unit-tests-only'

import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { after, before, beforeEach, describe, it } from 'node:test'
import { PrismaClient } from '@prisma/client'
import {
  claimDue,
  completeTask,
  reconcileStaleTasks,
  scheduleTask,
} from './tasks.js'
import { TASK_MAX_ATTEMPTS, TASK_STATUS } from './taskConfig.js'

const db = new PrismaClient()
const PREFIX = `e0-test-${randomUUID().slice(0, 8)}`

async function clearFixture(): Promise<void> {
  await db.agentLog.deleteMany({
    where: { task: { idempotencyKey: { startsWith: PREFIX } } },
  })
  await db.agentTask.deleteMany({
    where: { idempotencyKey: { startsWith: PREFIX } },
  })
}

function key(suffix: string): string {
  return `${PREFIX}:${suffix}`
}

function ours<T extends { idempotencyKey: string }>(rows: T[]): T[] {
  return rows.filter((r) => r.idempotencyKey.startsWith(PREFIX))
}

before(async () => {
  await clearFixture()
})

after(async () => {
  await clearFixture()
  await db.$disconnect()
})

describe('E0 scheduleTask idempotency', () => {
  beforeEach(async () => {
    await clearFixture()
  })

  it('returns the same row when idempotencyKey is reused', async () => {
    const dueAt = new Date(Date.now() - 60_000)
    const first = await scheduleTask({
      kind: 'recheck',
      symbol: 'BTCUSDT',
      dueAt,
      idempotencyKey: key('idem-1'),
      payload: { reason: 'first' },
    })
    assert.equal(first.created, true)

    const second = await scheduleTask({
      kind: 'recheck',
      symbol: 'BTCUSDT',
      dueAt,
      idempotencyKey: key('idem-1'),
      payload: { reason: 'retry-after-crash' },
    })
    assert.equal(second.created, false)
    assert.equal(second.id, first.id)

    const count = await db.agentTask.count({
      where: { idempotencyKey: key('idem-1') },
    })
    assert.equal(count, 1)
  })

  it('rejects concurrent inserts of the same key to a single row', async () => {
    const dueAt = new Date(Date.now() - 60_000)
    const idem = key('idem-race')
    const results = await Promise.all(
      Array.from({ length: 8 }, () =>
        scheduleTask({
          kind: 'recheck',
          symbol: 'ETHUSDT',
          dueAt,
          idempotencyKey: idem,
        }),
      ),
    )
    const ids = new Set(results.map((r) => r.id))
    assert.equal(ids.size, 1)
    assert.equal(results.filter((r) => r.created).length, 1)
    assert.equal(await db.agentTask.count({ where: { idempotencyKey: idem } }), 1)
  })
})

describe('E0 claimDue FOR UPDATE SKIP LOCKED', () => {
  beforeEach(async () => {
    await clearFixture()
  })

  it('gives each due task to at most one concurrent claimer', async () => {
    const dueAt = new Date(Date.now() - 30_000)
    const n = 6
    for (let i = 0; i < n; i += 1) {
      await scheduleTask({
        kind: 'recheck',
        symbol: `SYM${i}`,
        dueAt,
        idempotencyKey: key(`claim-${i}`),
      })
    }

    const waves = await Promise.all([claimDue(10), claimDue(10), claimDue(10)])
    const allIds = ours(waves.flat()).map((t) => t.id)
    assert.equal(allIds.length, n)
    assert.equal(new Set(allIds).size, n)

    for (const id of allIds) {
      const row = await db.agentTask.findUniqueOrThrow({ where: { id } })
      assert.equal(row.status, TASK_STATUS.leased)
      assert.ok(row.leaseUntil && row.leaseUntil.getTime() > Date.now())
      assert.equal(row.attempts, 1)
    }
  })
})

describe('E0 crash recovery — stale lease', () => {
  beforeEach(async () => {
    await clearFixture()
  })

  it('releases an expired lease so the task can be claimed again', async () => {
    const dueAt = new Date(Date.now() - 120_000)
    const { id } = await scheduleTask({
      kind: 'recheck',
      symbol: 'SOLUSDT',
      dueAt,
      idempotencyKey: key('stale-1'),
    })

    const past = new Date(Date.now() - 60_000)
    await db.agentTask.update({
      where: { id },
      data: {
        status: TASK_STATUS.leased,
        leaseUntil: past,
        attempts: 1,
      },
    })

    const sweep = await reconcileStaleTasks()
    assert.ok(sweep.released >= 1)

    const after = await db.agentTask.findUniqueOrThrow({ where: { id } })
    assert.equal(after.status, TASK_STATUS.pending)
    assert.equal(after.leaseUntil, null)

    const claimed = ours(await claimDue(20)).find((t) => t.id === id)
    assert.ok(claimed)
    assert.equal(claimed.attempts, 2)
  })

  it('retires a task that exhausted attempts after lease expiry', async () => {
    const dueAt = new Date(Date.now() - 120_000)
    const { id } = await scheduleTask({
      kind: 'recheck',
      symbol: 'ADAUSDT',
      dueAt,
      idempotencyKey: key('retire-1'),
    })

    await db.agentTask.update({
      where: { id },
      data: {
        status: TASK_STATUS.leased,
        leaseUntil: new Date(Date.now() - 60_000),
        attempts: TASK_MAX_ATTEMPTS,
      },
    })

    const sweep = await reconcileStaleTasks()
    assert.ok(sweep.retired >= 1)

    const row = await db.agentTask.findUniqueOrThrow({ where: { id } })
    assert.equal(row.status, TASK_STATUS.retired)
    assert.equal(row.leaseUntil, null)

    const empty = ours(await claimDue(20))
    assert.equal(
      empty.find((t) => t.id === id),
      undefined,
    )
  })

  it('completeTask is idempotent after crash mid-complete', async () => {
    const dueAt = new Date(Date.now() - 30_000)
    const { id } = await scheduleTask({
      kind: 'mission',
      symbol: 'XRPUSDT',
      dueAt,
      idempotencyKey: key('complete-1'),
    })
    const claimed = ours(await claimDue(20)).find((t) => t.id === id)
    assert.ok(claimed)

    assert.equal(await completeTask(id, { phase: 'E0', ok: true }), true)
    assert.equal(await completeTask(id, { phase: 'E0', ok: true }), false)

    const row = await db.agentTask.findUniqueOrThrow({ where: { id } })
    assert.equal(row.status, TASK_STATUS.completed)
    assert.equal(row.leaseUntil, null)
  })
})
