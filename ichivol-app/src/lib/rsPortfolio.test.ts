/**
 * RS-D1 paper — sélection du portefeuille et absence d'actions manuelles (RS-09 §7).
 */
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  BASELINE_PORTFOLIO_CODE,
  RS_D1_CODE,
  RS_D1_LABEL,
  SESSIONS_CODE,
  isRsPortfolio,
  manualActionsAllowed,
  portfolioFromParam,
} from './rsPortfolio.ts'

test('le paramètre ?pf ne sélectionne RS-D1 que pour son code exact', () => {
  assert.equal(portfolioFromParam(RS_D1_CODE), RS_D1_CODE)
  assert.equal(portfolioFromParam(null), BASELINE_PORTFOLIO_CODE)
  assert.equal(portfolioFromParam('rs_d1_paper_v1'), BASELINE_PORTFOLIO_CODE)
  assert.equal(portfolioFromParam('AUTRE'), BASELINE_PORTFOLIO_CODE)
})

test('aucune action manuelle sur RS-D1, baseline inchangé', () => {
  assert.equal(isRsPortfolio(RS_D1_CODE), true)
  assert.equal(manualActionsAllowed(RS_D1_CODE), false)
  assert.equal(manualActionsAllowed(BASELINE_PORTFOLIO_CODE), true)
})

test('Sessions : sélectionnable par son code exact, actions manuelles permises', () => {
  assert.equal(portfolioFromParam(SESSIONS_CODE), SESSIONS_CODE)
  assert.equal(portfolioFromParam('ichivol_sessions_v1'), BASELINE_PORTFOLIO_CODE)
  assert.equal(isRsPortfolio(SESSIONS_CODE), false)
  assert.equal(manualActionsAllowed(SESSIONS_CODE), true)
})

test('libellé exact demandé', () => {
  assert.equal(RS_D1_LABEL, 'RS-D1 — validé 2025, holdout 2026 non ouvert')
})
