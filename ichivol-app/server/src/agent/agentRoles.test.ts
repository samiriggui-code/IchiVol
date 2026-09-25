/**
 * Unit tests — Chantier 2b role card status derivation (no DB).
 */
import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  authorityStepFromLogSource,
  deriveRoleCards,
  type RoleSignals,
} from './agentRoles.js'

function baseSignals(over: Partial<RoleSignals> = {}): RoleSignals {
  return {
    engineOk: true,
    databaseOk: true,
    workerStarted: true,
    killSwitchArmed: false,
    openPaperPositions: 0,
    openSessions: 1,
    eveOpenTasks: 0,
    eveLeasedTasks: 0,
    eveRecheckOpen: 0,
    eveLastLogMessage: null,
    eveLastLogAt: null,
    eveNextDueAt: null,
    eveNextKind: null,
    eveNextSymbol: null,
    eveLogs24h: 0,
    llmKeyPresent: true,
    ...over,
  }
}

describe('2b agentRoles deriveRoleCards', () => {
  it('returns 6 cards in maquette order', () => {
    const cards = deriveRoleCards(baseSignals())
    assert.equal(cards.length, 6)
    assert.deepEqual(
      cards.map((c) => c.id),
      ['observer', 'opportunities', 'risk', 'execution', 'position', 'session'],
    )
    assert.equal(cards[1]!.runtimeAgentId, 'eve')
    assert.equal(cards[1]!.kind, 'llm')
    assert.ok(cards.every((c) => c.paperOnly && c.humanConfirmDefault && !c.autoOpen))
  })

  it('marks code agents ERREUR when engine is down', () => {
    const cards = deriveRoleCards(baseSignals({ engineOk: false }))
    const byId = Object.fromEntries(cards.map((c) => [c.id, c]))
    assert.equal(byId.observer!.status, 'ERREUR')
    assert.equal(byId.risk!.status, 'ERREUR')
    assert.equal(byId.execution!.status, 'ERREUR')
    assert.equal(byId.position!.status, 'ERREUR')
  })

  it('marks Eve ACTIF when leased, EN VEILLE when pending only', () => {
    const actif = deriveRoleCards(baseSignals({ eveLeasedTasks: 1, eveOpenTasks: 1 }))
    assert.equal(actif.find((c) => c.id === 'opportunities')!.status, 'ACTIF')

    const veille = deriveRoleCards(baseSignals({ eveOpenTasks: 2, eveLeasedTasks: 0 }))
    assert.equal(veille.find((c) => c.id === 'opportunities')!.status, 'EN VEILLE')
  })

  it('pauses execution when kill switch is armed', () => {
    const cards = deriveRoleCards(baseSignals({ killSwitchArmed: true }))
    assert.equal(cards.find((c) => c.id === 'execution')!.status, 'EN PAUSE')
  })

  it('activates position when open paper exists', () => {
    const cards = deriveRoleCards(baseSignals({ openPaperPositions: 3 }))
    assert.equal(cards.find((c) => c.id === 'position')!.status, 'ACTIF')
  })
})

describe('2b authorityStepFromLogSource', () => {
  it('maps known sources and returns null otherwise', () => {
    assert.equal(authorityStepFromLogSource('runtime.missionRunner'), 'Opportunité')
    assert.equal(authorityStepFromLogSource('missions.create'), 'Opportunité')
    assert.equal(authorityStepFromLogSource('risk_kernel'), 'Risk Kernel')
    assert.equal(authorityStepFromLogSource('unknown.thing'), null)
    assert.equal(authorityStepFromLogSource(null), null)
  })
})
