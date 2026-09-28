/**
 * UI-VP-BADGE — rendu minimal (pas de DOM browser).
 */
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { VpValidationBadge } from './VpValidationBadge.js'
import {
  VP_VALIDATION_BADGE_LABEL,
  VP_VALIDATION_REPORT_HREF,
  VP_VALIDATION_TOOLTIP,
} from '../lib/vpValidationCopy.js'

test('VpValidationBadge : label + tooltip, pas de lien GitHub', () => {
  const html = renderToStaticMarkup(createElement(VpValidationBadge))
  assert.match(html, /vp-validation-badge/)
  assert.match(html, new RegExp(VP_VALIDATION_BADGE_LABEL))
  assert.match(html, /role="status"/)
  assert.match(html, new RegExp(VP_VALIDATION_TOOLTIP.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  assert.doesNotMatch(html, /href=/)
  assert.doesNotMatch(html, new RegExp(VP_VALIDATION_REPORT_HREF.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  assert.doesNotMatch(html, /target="_blank"/)
})

test('VpValidationBadge compact : classe is-compact', () => {
  const html = renderToStaticMarkup(createElement(VpValidationBadge, { compact: true }))
  assert.match(html, /is-compact/)
})
