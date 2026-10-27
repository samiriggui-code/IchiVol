/**
 * Bilan du portefeuille unique : libellés, lignes actives, univers groupé, modes d'observation.
 */
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  activeRows,
  arbitrationFr,
  assetClassLabel,
  deciderScores,
  enginesFr,
  modeFr,
  sessionEventFr,
  universeByClass,
  type DeciderRow,
} from './breakdown.ts'

const row = (o: Partial<DeciderRow>): DeciderRow => ({
  decider: 'engine',
  label: 'Moteur seul',
  trades: 0,
  wins: 0,
  losses: 0,
  win_rate: null,
  net: 0,
  fees: 0,
  open: 0,
  avg_win: null,
  avg_loss: null,
  sum_wins: 0,
  sum_losses: 0,
  ...o,
})

test('lignes actives : un trade clôturé ou une position ouverte', () => {
  const rows = [row({ decider: 'eve' }), row({ decider: 'engine', trades: 2 }), row({ decider: 'manual', open: 1 })]
  assert.deepEqual(
    activeRows(rows).map((r) => r.decider),
    ['engine', 'manual'],
  )
})

test('libellé de classe : celui de l’API, sinon le français par défaut', () => {
  assert.equal(assetClassLabel({ asset_class: 'metal', label: '' }), 'Métaux')
  assert.equal(assetClassLabel({ asset_class: 'crypto', label: 'Cryptomonnaies' }), 'Cryptomonnaies')
  assert.equal(assetClassLabel({ asset_class: 'inconnu', label: '' }), 'inconnu')
})

test('univers groupé par classe, ordre de l’API conservé', () => {
  const g = universeByClass([
    { symbol: 'BTCUSDT', asset_class: 'crypto', friction_bps: 1 },
    { symbol: 'EURUSD', asset_class: 'forex', friction_bps: 0.8 },
    { symbol: 'ETHUSDT', asset_class: 'crypto', friction_bps: 1 },
  ])
  assert.deepEqual(g, [
    { asset_class: 'crypto', label: 'Crypto', symbols: ['BTCUSDT', 'ETHUSDT'] },
    { asset_class: 'forex', label: 'Forex', symbols: ['EURUSD'] },
  ])
})

test('mode observation en français', () => {
  assert.equal(modeFr('observe'), 'observation (noté, ne bloque pas)')
  assert.equal(modeFr(null), 'désactivé')
})

test('bilan par décideur du moteur → format des cartes, les 4 décideurs présents', () => {
  const s = deciderScores([row({ decider: 'eve', trades: 3, wins: 2, losses: 1, win_rate: 2 / 3, net: 12.5, open: 1 })])
  assert.equal(s.eve.trades, 3)
  assert.equal(s.eve.winRate, 2 / 3)
  assert.equal(s.eve.net, 12.5)
  assert.equal(s.manual.trades, 0)
  assert.deepEqual(Object.keys(s).sort(), ['engine', 'engine_over_eve', 'eve', 'manual'])
})

test('moteurs et arbitrage du profil traduits, code inconnu gardé tel quel', () => {
  assert.deepEqual(enginesFr(['eve_autopilot_jev', 'autre']), ['pilote d’Ève avec JEV', 'autre'])
  assert.equal(enginesFr(null).length, 0)
  assert.match(arbitrationFr('un_lot_par_symbole_premier_arrive') ?? '', /un seul lot par symbole/)
  assert.equal(arbitrationFr(null), null)
})

test('session à l’entrée en français, jamais de JSON brut', () => {
  assert.equal(sessionEventFr('tokyo_open'), 'ouverture de Tokyo')
  assert.equal(sessionEventFr('london_close'), 'clôture de Londres')
  assert.equal(sessionEventFr('ny_open'), 'ouverture de New York')
  assert.equal(sessionEventFr(null), 'hors fenêtre de session')
  assert.equal(sessionEventFr(undefined), 'hors fenêtre de session')
  assert.equal(sessionEventFr({ event: 'x' }), 'session non reconnue')
})
