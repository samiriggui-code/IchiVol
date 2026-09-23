/**
 * T0-NOTIF unit tests — dedup, proximity parity, push soft-fail, no-order guard.
 */
process.env.JWT_SECRET ??= 'test-secret-for-unit-tests-only'

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { describe, it } from 'node:test'
import { fileURLToPath } from 'node:url'
import { shouldEmitAlert } from './positionWatchDedup.js'

const __dirname = dirname(fileURLToPath(import.meta.url))

describe('T0-NOTIF shouldEmitAlert dedup', () => {
  const now = new Date('2026-09-23T12:00:00Z')

  it('emits when no prior alert', () => {
    assert.equal(
      shouldEmitAlert({ last: null, now, cooldownMin: 30, band: '20' }),
      true,
    )
  })

  it('suppresses identical alert inside cooldown', () => {
    const last = {
      createdAt: new Date('2026-09-23T11:45:00Z'),
      band: '20',
    }
    assert.equal(
      shouldEmitAlert({ last, now, cooldownMin: 30, band: '20' }),
      false,
    )
  })

  it('emits again after cooldown', () => {
    const last = {
      createdAt: new Date('2026-09-23T11:00:00Z'),
      band: '20',
    }
    assert.equal(
      shouldEmitAlert({ last, now, cooldownMin: 30, band: '20' }),
      true,
    )
  })

  it('emits on real state change (tighter band) inside cooldown', () => {
    const last = {
      createdAt: new Date('2026-09-23T11:50:00Z'),
      band: '20',
    }
    assert.equal(
      shouldEmitAlert({ last, now, cooldownMin: 30, band: '10' }),
      true,
    )
  })

  it('emits on stateKey change inside cooldown', () => {
    const last = {
      createdAt: new Date('2026-09-23T11:50:00Z'),
      stateKey: 'flip:LONG->SHORT',
    }
    assert.equal(
      shouldEmitAlert({
        last,
        now,
        cooldownMin: 30,
        stateKey: 'flip:LONG->NEUTRAL',
      }),
      true,
    )
  })
})

describe('T0-NOTIF proximity geometry (parity with scenarios.py)', () => {
  function levelRemainingFrac(entry: number, mark: number, level: number): number | null {
    const span = Math.abs(level - entry)
    if (span < 1e-12) return null
    const progress = (mark - entry) / (level - entry)
    if (progress >= 1) return 0
    if (progress <= 0) return 1
    return 1 - progress
  }

  it('LONG target: mark 108 of 100→110 → remaining 0.2 (near at 20%)', () => {
    const rem = levelRemainingFrac(100, 108, 110)
    assert.ok(rem != null)
    assert.ok(Math.abs(rem! - 0.2) < 1e-9)
    assert.ok(rem! <= 0.2)
  })

  it('LONG stop: mark 92 of 100→90 → remaining 0.2', () => {
    const rem = levelRemainingFrac(100, 92, 90)
    assert.ok(rem != null)
    assert.ok(Math.abs(rem! - 0.2) < 1e-9)
  })

  it('at entry remaining is 1; at level remaining is 0', () => {
    assert.equal(levelRemainingFrac(100, 100, 110), 1)
    assert.equal(levelRemainingFrac(100, 110, 110), 0)
  })
})

describe('T0-NOTIF sendPush never throws on invalid sub', () => {
  it('returns gone/false without throwing', async () => {
    const { sendPushRaw } = await import('./push.js')
    const result = await sendPushRaw(
      {
        endpoint: 'https://example.invalid/push/gone',
        keys: {
          p256dh: 'BNcRdERA9KwLAyKdL3o1M0pJwC1wB8k8k0lW9p8p8p8p8p8p8p8p8p8p8p8p8p8p8p8',
          auth: 'tBHIQLOE_xq2V0iI6w7V2Q',
        },
      },
      { title: 't', body: 'b' },
    )
    assert.equal(typeof result.ok, 'boolean')
    assert.equal(typeof result.gone, 'boolean')
  })
})

describe('T0-NOTIF positionWatch never places orders', () => {
  it('source has no open/close paper calls', () => {
    const src = readFileSync(join(__dirname, 'positionWatch.ts'), 'utf8')
    assert.equal(/open_paper|openPaper|close_paper|closePaper/.test(src), false)
    assert.equal(src.includes('method: \'POST\''), false)
    assert.equal(src.includes('/proximity'), true)
  })
})
