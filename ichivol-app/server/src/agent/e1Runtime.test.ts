/**
 * Chantier 2 E1 — schedule_recheck + skills + freshness defer tests.
 */
process.env.JWT_SECRET ??= 'test-secret-for-unit-tests-only'

import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { after, before, beforeEach, describe, it } from 'node:test'
import { PrismaClient } from '@prisma/client'
import { CANDLE_GRACE_MS, nextClosedCandleDueAt, timeframeSeconds } from './candleDue.js'
import { loadSkills, MAX_SKILLS_CHARS, resolveSkillsForTask } from './skills/loadSkills.js'
import {
  executeScheduleRecheck,
  MIN_RECHECK_REASON_LENGTH,
  scheduleRecheck,
  validateRecheckReason,
} from './tools/scheduleRecheck.js'
import { createMission } from './missions.js'
import { claimDue, deferTask } from './tasks.js'
import { TASK_STATUS } from './taskConfig.js'
import { freshnessFromContextData } from './runtime/dataQualityGate.js'
import { processClaimedTask } from './runtime/missionRunner.js'

const db = new PrismaClient()
const PREFIX = `e1-test-${randomUUID().slice(0, 8)}`

async function clearFixture(): Promise<void> {
  await db.agentLog.deleteMany({
    where: {
      OR: [
        { task: { idempotencyKey: { startsWith: PREFIX } } },
        { task: { symbol: { startsWith: PREFIX } } },
      ],
    },
  })
  await db.agentTask.deleteMany({
    where: {
      OR: [
        { idempotencyKey: { startsWith: PREFIX } },
        { symbol: { startsWith: PREFIX } },
      ],
    },
  })
}

before(async () => {
  await clearFixture()
})

after(async () => {
  await clearFixture()
  await db.$disconnect()
})

describe('E1 candle dueAt', () => {
  it('computes next closed candle + 60s grace for 1h', () => {
    const now = new Date('2026-09-25T14:20:00.000Z')
    const due = nextClosedCandleDueAt('1h', now)
    assert.equal(due.toISOString(), '2026-09-25T15:01:00.000Z')
    assert.equal(timeframeSeconds('1h'), 3600)
    assert.equal(CANDLE_GRACE_MS, 60_000)
  })

  it('rejects unknown timeframe', () => {
    assert.throws(() => timeframeSeconds('3m'), /unsupported_timeframe/)
  })
})

describe('E1 schedule_recheck validation', () => {
  it('rejects reason shorter than 10 chars', () => {
    assert.ok(validateRecheckReason('short'))
    assert.equal(validateRecheckReason('x'.repeat(MIN_RECHECK_REASON_LENGTH)), null)
  })

  it('executeScheduleRecheck rejects short reason without DB write', async () => {
    const res = await executeScheduleRecheck({
      symbol: 'BTCUSDT',
      reason: 'too-short',
    })
    assert.equal(res.ok, false)
    assert.match(res.content, /at least 10/)
  })
})

describe('E1 schedule_recheck persistence', () => {
  beforeEach(async () => {
    await clearFixture()
  })

  it('creates a recheck and refreshes open row for same symbol', async () => {
    const symbol = `${PREFIX}BTC`
    const first = await scheduleRecheck({
      symbol,
      timeframe: '1h',
      reason: 'Watch kumo twist after next hour close',
      dueAt: new Date(Date.now() + 120_000),
    })
    assert.equal(first.created, true)
    assert.equal(first.refreshed, false)

    const second = await scheduleRecheck({
      symbol,
      timeframe: '1h',
      reason: 'Updated reason after volume spike watch',
      dueAt: new Date(Date.now() + 300_000),
    })
    assert.equal(second.created, false)
    assert.equal(second.refreshed, true)
    assert.equal(second.id, first.id)

    const row = await db.agentTask.findUniqueOrThrow({ where: { id: first.id } })
    assert.equal(row.status, TASK_STATUS.pending)
    assert.equal(row.symbol, symbol.toUpperCase())
    const open = await db.agentTask.count({
      where: { id: first.id, status: TASK_STATUS.pending },
    })
    assert.equal(open, 1)
  })

  it('rejects past due_at via executor', async () => {
    const res = await executeScheduleRecheck({
      symbol: `${PREFIX}ETH`,
      reason: 'Need a future due_at for this recheck',
      due_at: new Date(Date.now() - 60_000).toISOString(),
    })
    assert.equal(res.ok, false)
    assert.match(res.content, /future/)
  })
})

describe('E1 skills on demand', () => {
  it('loads named skills and skips unknown', () => {
    const { names, block } = loadSkills(['ichimoku', 'nope', 'risk'])
    assert.deepEqual(names, ['ichimoku', 'risk'])
    assert.ok(block)
    assert.match(block!, /skill:ichimoku/)
    assert.match(block!, /skill:risk/)
    assert.ok(block!.length <= MAX_SKILLS_CHARS + 80)
  })

  it('resolves default mission skills', () => {
    assert.ok(resolveSkillsForTask('mission', null).includes('ichimoku'))
    assert.deepEqual(resolveSkillsForTask('mission', { skills: ['mtf'] }), ['mtf'])
  })
})

describe('E1 mission 1-symbol', () => {
  it('rejects multi-symbol input', async () => {
    await assert.rejects(
      () =>
        createMission({
          userId: '00000000-0000-4000-8000-000000000099',
          symbol: 'BTCUSDT,ETHUSDT',
          reason: 'bad multi',
        }),
      /exactly one symbol/,
    )
  })
})

describe('E1 deferTask (stale / data_late path)', () => {
  beforeEach(async () => {
    await clearFixture()
  })

  it('releases lease and pushes dueAt without completing', async () => {
    const symbol = `${PREFIX}SOL`
    const { id } = await scheduleRecheck({
      symbol,
      timeframe: '1h',
      reason: 'Baseline recheck before freshness defer test',
      dueAt: new Date(Date.now() - 30_000),
    })
    const claimed = (await claimDue(20)).find((t) => t.id === id)
    assert.ok(claimed)

    const newDue = new Date(Date.now() + 3_600_000)
    assert.equal(await deferTask(id, newDue, 'data_late'), true)

    const row = await db.agentTask.findUniqueOrThrow({ where: { id } })
    assert.equal(row.status, TASK_STATUS.pending)
    assert.equal(row.leaseUntil, null)
    assert.equal(row.error, 'data_late')
    assert.ok(Math.abs(row.dueAt.getTime() - newDue.getTime()) < 1000)
  })
})

describe('E1 freshness gate', () => {
  it('maps stale from engine payload shape', () => {
    const v = freshnessFromContextData({
      data_quality: { stale: true, data_late: false, gate: 'stale', ok: false },
    })
    assert.equal(v.ok, false)
    if (!v.ok) assert.equal(v.reason, 'stale')
  })

  it('maps data_late from engine payload shape', () => {
    const v = freshnessFromContextData({
      data_quality: { stale: false, data_late: true, gate: 'ok', ok: true },
    })
    assert.equal(v.ok, false)
    if (!v.ok) assert.equal(v.reason, 'data_late')
  })

  it('passes when quality ok', () => {
    const v = freshnessFromContextData({
      data_quality: { stale: false, data_late: false, gate: 'ok', ok: true },
    })
    assert.equal(v.ok, true)
  })
})

describe('E1 missionRunner stale → defer no LLM', () => {
  beforeEach(async () => {
    await clearFixture()
  })

  it('defers and logs without completing when data_late', async () => {
    const symbol = `${PREFIX}ADA`
    const scheduled = await scheduleRecheck({
      symbol,
      timeframe: '1h',
      reason: 'Runner freshness defer integration check',
      dueAt: new Date(Date.now() - 10_000),
    })
    await db.agentTask.update({
      where: { id: scheduled.id },
      data: {
        payload: {
          reason: 'Runner freshness defer integration check',
          timeframe: '1h',
          userId: '00000000-0000-4000-8000-000000000001',
          humanConfirmDefault: true,
          autoOpen: false,
        },
      },
    })

    const claimed = (await claimDue(20)).find((t) => t.id === scheduled.id)
    assert.ok(claimed)

    const outcome = await processClaimedTask(claimed, {
      checkFreshness: async () => ({
        ok: false,
        reason: 'data_late',
        stale: false,
        dataLate: true,
      }),
    })
    assert.equal(outcome.action, 'deferred')
    if (outcome.action === 'deferred') assert.equal(outcome.reason, 'data_late')

    const row = await db.agentTask.findUniqueOrThrow({ where: { id: scheduled.id } })
    assert.equal(row.status, TASK_STATUS.pending)
    assert.equal(row.error, 'data_late')

    const log = await db.agentLog.findFirst({
      where: { taskId: scheduled.id, source: 'runtime.missionRunner' },
      orderBy: { createdAt: 'desc' },
    })
    assert.ok(log)
    assert.match(log!.message, /No LLM wake/)
    assert.equal(log!.level, 'PRUDENCE')
  })

  it('defers condition-bearing tasks without LLM (E2 gap)', async () => {
    const symbol = `${PREFIX}XRP`
    const scheduled = await scheduleRecheck({
      symbol,
      timeframe: '1h',
      reason: 'Condition present must not stub-complete in E1',
      dueAt: new Date(Date.now() - 10_000),
      condition: { all: [{ feature: 'rvol', op: 'gte', value: 1.5 }] },
    })

    const claimed = (await claimDue(20)).find((t) => t.id === scheduled.id)
    assert.ok(claimed)

    const outcome = await processClaimedTask(claimed, {
      checkFreshness: async () => ({ ok: true, stale: false, dataLate: false }),
    })
    assert.equal(outcome.action, 'deferred')
    if (outcome.action === 'deferred') assert.equal(outcome.reason, 'condition_deferred_e2')
    const row = await db.agentTask.findUniqueOrThrow({ where: { id: scheduled.id } })
    assert.equal(row.status, TASK_STATUS.pending)
    assert.notEqual(row.status, TASK_STATUS.completed)
  })
})
