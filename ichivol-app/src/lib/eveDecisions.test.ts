/**
 * Sort d'une proposition du moteur : exécutée, refusée par Ève, ou acceptée puis bloquée.
 */
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { engineProposalFr, proposalStatusFr, proposalVerdict, type EngineProposalOutcome } from './eveDecisions'

const p = (o: Partial<EngineProposalOutcome>): EngineProposalOutcome => ({
  portfolio_code: 'ICHIVOL_BASELINE_V1',
  engine_action: 'OPEN',
  engine_direction: 'LONG',
  eve_action: 'LONG',
  eve_accepts: true,
  ...o,
})

test('verdicts', () => {
  assert.equal(proposalVerdict(p({ executed: true, status: 'opened' })), 'executed')
  assert.equal(proposalVerdict(p({ eve_accepts: false, eve_action: 'ABSTAIN', status: 'refused_by_eve' })), 'refused_by_eve')
  assert.equal(proposalVerdict(p({ status: 'risk_kernel_refused' })), 'blocked_after')
  assert.equal(proposalStatusFr(p({ status: 'risk_kernel_refused' })), 'Refusé par le Risk Kernel')
  assert.equal(engineProposalFr(p({ engine_action: 'CLOSE' })), 'Clôturer')
  assert.equal(engineProposalFr(p({ engine_direction: 'SHORT' })), 'Vendre à découvert')
})
