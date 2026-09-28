/**
 * UI-VP-BADGE — source de vérité copy + filtre ACHAT/VENTE.
 */
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  VP_VALIDATION_BADGE_LABEL,
  VP_VALIDATION_REPORT_HREF,
  VP_VALIDATION_REPORT_PATH,
  VP_VALIDATION_TOOLTIP,
  isActionableBuySell,
  vpValidationTitle,
} from './vpValidationCopy.js'

test('copy VP : label + tooltip + chemin rapport stables', () => {
  assert.equal(VP_VALIDATION_BADGE_LABEL, 'Signal non validé')
  assert.match(VP_VALIDATION_TOOLTIP, /VP3/)
  assert.match(VP_VALIDATION_TOOLTIP, /0\/48/)
  assert.equal(VP_VALIDATION_REPORT_PATH, 'docs/VP3-REPORT-FINAL.md')
  assert.match(VP_VALIDATION_REPORT_HREF, /VP3-REPORT-FINAL\.md/)
  assert.equal(vpValidationTitle(), `${VP_VALIDATION_TOOLTIP} (${VP_VALIDATION_REPORT_PATH})`)
})

test('isActionableBuySell : seulement ACHAT/VENTE', () => {
  assert.equal(isActionableBuySell('BUY'), true)
  assert.equal(isActionableBuySell('SELL'), true)
  assert.equal(isActionableBuySell('STRONG_BUY'), true)
  assert.equal(isActionableBuySell('strong_sell'), true)
  assert.equal(isActionableBuySell('WATCH'), false)
  assert.equal(isActionableBuySell('NO_TRADE'), false)
  assert.equal(isActionableBuySell(null), false)
  assert.equal(isActionableBuySell(''), false)
  assert.equal(isActionableBuySell('HOLD'), false)
})
