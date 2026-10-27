/**
 * Portefeuille unique : le code par défaut est ICHIVOL_MAIN_V1 et aucun ancien compte n'est sélectionnable.
 */
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  MAIN_PORTFOLIO_CODE,
  RETIRED_PORTFOLIO_CODES,
  isRetiredPortfolio,
  portfolioFromParam,
  portfolioLabel,
} from './mainPortfolio.ts'

test('le code par défaut est ICHIVOL_MAIN_V1', () => {
  assert.equal(MAIN_PORTFOLIO_CODE, 'ICHIVOL_MAIN_V1')
  assert.equal(portfolioFromParam(null), 'ICHIVOL_MAIN_V1')
  assert.equal(portfolioFromParam(''), 'ICHIVOL_MAIN_V1')
})

test('un ancien code dans ?pf= n’est jamais sélectionné', () => {
  assert.equal(RETIRED_PORTFOLIO_CODES.length, 8)
  for (const code of RETIRED_PORTFOLIO_CODES) {
    assert.equal(portfolioFromParam(code), MAIN_PORTFOLIO_CODE)
    assert.ok(isRetiredPortfolio(code))
  }
  assert.equal(portfolioFromParam('ALL'), MAIN_PORTFOLIO_CODE)
  assert.equal(portfolioFromParam('N_IMPORTE_QUOI'), MAIN_PORTFOLIO_CODE)
  assert.ok(!isRetiredPortfolio(MAIN_PORTFOLIO_CODE))
})

test('libellés : « IchiVol » pour le compte unique, « compte retiré » pour l’historique', () => {
  assert.equal(portfolioLabel(MAIN_PORTFOLIO_CODE, 'IchiVol — portefeuille unique (50 000 €)'), 'IchiVol')
  assert.equal(portfolioLabel('ICHIVOL_WIDE_V1'), 'ICHIVOL_WIDE_V1 (compte retiré)')
})
