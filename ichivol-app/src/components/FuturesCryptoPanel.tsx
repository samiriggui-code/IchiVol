/**
 * Vue dédiée du portefeuille Futures & Crypto (YM, MGC, BTC), affichée dans la page Portefeuille.
 * Par marché : ce qui est tradé et d'où vient le cours, position ouverte, P&L, risque, dernier verdict et Eve.
 * Plus le plafond de risque global et le choix de l'instrument BTC.
 */

import { useCallback, useEffect, useState } from 'react'
import type { PaperOverview, PaperOverviewPosition } from '../lib/paper'
import { useCopilotNav } from '../lib/useCopilotNav'
import {
  contractsFor,
  fullPositionsLeft,
  getFuturesCryptoView,
  marketRisk,
  setBtcMode,
  signalSentenceFr,
  verdictLabelFr,
  type BtcMode,
  type FuturesCryptoMarket,
  type FuturesCryptoView,
} from '../lib/futuresCrypto'

function eur(n: number | null | undefined, digits = 2): string {
  if (n == null || !Number.isFinite(n)) return '—'
  return `${n.toLocaleString('fr-FR', { minimumFractionDigits: digits, maximumFractionDigits: digits })} €`
}

function pct(n: number | null | undefined, digits = 2): string {
  if (n == null || !Number.isFinite(n)) return '—'
  return `${(n * 100).toLocaleString('fr-FR', { minimumFractionDigits: digits, maximumFractionDigits: digits })} %`
}

function num(n: number | null | undefined, digits = 4): string {
  if (n == null || !Number.isFinite(n)) return '—'
  return n.toLocaleString('fr-FR', { maximumFractionDigits: digits })
}

function when(iso: string | null | undefined): string {
  if (!iso || Number.isNaN(Date.parse(iso))) return '—'
  return new Date(iso).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function Bar({ value }: { value: number | null }) {
  const w = value == null ? 0 : Math.max(0, Math.min(100, value * 100))
  return (
    <div className={`iv-bar fc-bar${value != null && value >= 1 ? ' is-sell' : value != null && value >= 0.8 ? ' is-amber' : ''}`}>
      <i style={{ width: `${w}%` }} />
    </div>
  )
}

function MarketCard({
  market,
  position,
  equity,
  maxOpenRiskPct,
  allowShort,
}: {
  market: FuturesCryptoMarket
  position: PaperOverviewPosition | null
  equity: number | null
  maxOpenRiskPct: number
  allowShort: boolean
}) {
  const { explainDecision } = useCopilotNav()
  const risk = marketRisk(market.symbol, position ? [position] : [], equity, maxOpenRiskPct)
  const sig = market.last_signal
  const contracts = contractsFor(position?.qty, market.contract_size)
  const pnl = position?.unrealized_pnl ?? null

  const askEve = () =>
    explainDecision({
      symbol: market.symbol,
      timeframe: sig?.timeframe ?? '1h',
      price: sig?.price ?? position?.current_price ?? null,
      combiner: 'ichimoku_rvol_v1',
      direction: sig?.direction ?? 'NEUTRAL',
      gateDecision: sig?.decision ?? null,
      stages: (sig?.stages ?? []).map((s) => ({ id: String(s.id), status: String(s.status), summary: s.summary ?? '' })),
    })

  return (
    <section className="iv-card fc-market iv-s4 iv-m-s12">
      <div className="iv-card-head">
        <div className="iv-card-tabs">
          <span className="iv-card-tab is-on">
            {market.slot} · {market.name}
          </span>
        </div>
        <div className="iv-card-tools">{market.venue}</div>
      </div>
      <div className="iv-card-body">
        <p className="fc-note">
          Contrat <b>{market.contract}</b> : {market.contract_unit}. Cours : {market.price_source}. {market.price_note}
        </p>

        <h3 className="fc-sub">Position</h3>
        {position ? (
          <>
            <div className="iv-row">
              <span>Sens</span>
              <b className="iv-row-v">{position.direction === 'SHORT' ? 'Vente' : 'Achat'}</b>
            </div>
            <div className="iv-row">
              <span>Quantité</span>
              <b className="iv-row-v">
                {num(position.qty)}
                {contracts != null && market.contract_size !== 1 ? ` · ${num(contracts, 2)} contrat${contracts >= 2 ? 's' : ''}` : ''}
              </b>
            </div>
            <div className="iv-row">
              <span>Entrée → dernier</span>
              <b className="iv-row-v">
                {num(position.entry_price, 2)} → {num(position.current_price, 2)}
              </b>
            </div>
            <div className="iv-row">
              <span>Stop / objectif</span>
              <b className="iv-row-v">
                {num(position.stop_price, 2)} / {num(position.take_profit_price, 2)}
              </b>
            </div>
            <div className="iv-row">
              <span>P&amp;L latent</span>
              <b className={`iv-row-v ${pnl == null ? '' : pnl > 0 ? 'pos' : pnl < 0 ? 'neg' : ''}`}>
                {eur(pnl)}
                {position.unrealized_pct != null ? ` · ${pct(position.unrealized_pct)}` : ''}
              </b>
            </div>
            <div className="iv-row">
              <span>Exposition</span>
              <b className="iv-row-v">
                {eur(risk.exposure, 0)} · {pct(risk.exposurePctOfEquity, 1)} du capital
              </b>
            </div>
            <div className="iv-row">
              <span>Risque jusqu’au stop</span>
              <b className="iv-row-v">
                {eur(risk.riskAmount)} · {pct(risk.riskPctOfEquity)} du capital
              </b>
            </div>
            <Bar value={risk.shareOfCap} />
            <small className="fc-hint">
              Part du plafond global prise par ce marché : {pct(risk.shareOfCap, 0)}.
              {contracts != null && market.contract_size !== 1
                ? ' Un vrai compte futures n’achète que des contrats entiers : ici la quantité reste fractionnaire pour suivre la règle de risque.'
                : ''}
            </small>
          </>
        ) : (
          <p className="fc-note">Aucune position ouverte sur ce marché.</p>
        )}

        <div className="iv-row">
          <span>P&amp;L réalisé</span>
          <b className="iv-row-v">
            {eur(market.realized_pnl)} · {market.closed_trades} trade{market.closed_trades > 1 ? 's' : ''} fermé
            {market.closed_trades > 1 ? 's' : ''}
            {market.closed_trades > 0 ? `, ${market.wins} gagnant${market.wins > 1 ? 's' : ''}` : ''}
          </b>
        </div>

        <h3 className="fc-sub">Dernier signal (boucle 1h)</h3>
        <div className="iv-row">
          <span>{sig ? `Vu le ${when(sig.seen_at)}${sig.price != null ? ` à ${num(sig.price, 2)}` : ''}` : 'Signal'}</span>
          <b className="iv-row-v">{sig ? verdictLabelFr(sig.decision) : '—'}</b>
        </div>
        <p className="fc-note">{signalSentenceFr(sig, allowShort)}</p>
        <button type="button" className="iv-btn iv-btn--sm" onClick={askEve}>
          Demander à Ève d’expliquer
        </button>

        <small className="fc-hint">
          Coûts supposés par côté : commission {num(market.costs.commission_bps, 1)} pb, spread et glissement{' '}
          {num(market.costs.friction_bps, 1)} pb
          {market.costs.financing_bps_per_day_long
            ? `, financement ${num(market.costs.financing_bps_per_day_long, 1)} pb par jour en achat`
            : ', pas de financement de nuit'}
          . Ce sont des hypothèses, pas des frais mesurés chez un courtier.
        </small>
      </div>
    </section>
  )
}

export function FuturesCryptoPanel({
  overview,
  onChanged,
}: {
  overview: PaperOverview | null
  onChanged: () => void
}) {
  const [view, setView] = useState<FuturesCryptoView | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [choice, setChoice] = useState<BtcMode | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const v = await getFuturesCryptoView()
      setView(v)
      setChoice(v.btc_mode)
      setError(null)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Vue indisponible')
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  if (error && !view) {
    return (
      <section className="iv-card">
        <div className="iv-card-body">
          <p className="fc-note">La vue Futures &amp; Crypto n’a pas pu être chargée : {error}</p>
        </div>
      </section>
    )
  }
  if (!view) return null

  const equity = overview?.account?.equity ?? null
  const openPositions = (overview?.positions ?? []).filter((p) => String(p.status).toUpperCase() === 'OPEN')
  const openRisk = overview?.risk?.open_risk_amount ?? 0
  const capAmount = equity != null ? equity * view.rules.max_open_risk_pct : null
  const left = fullPositionsLeft(openRisk, equity, view.rules.risk_pct, view.rules.max_open_risk_pct)
  const current = view.btc_modes.find((m) => m.mode === view.btc_mode)

  async function saveMode() {
    if (!choice || choice === view?.btc_mode) return
    setSaving(true)
    setSaveError(null)
    try {
      setView(await setBtcMode(choice))
      onChanged()
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : 'Changement impossible')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fc-stack">
      <section className="iv-card fc-intro">
        <div className="iv-card-head">
          <div className="iv-card-tabs">
            <span className="iv-card-tab is-on">Comment marche ce portefeuille</span>
          </div>
        </div>
        <div className="iv-card-body">
          <p className="fc-note">
            Un compte paper à part, qui complète l’univers IchiVol sans le remplacer. Il ne suit que trois marchés : le
            Dow Jones (YM), l’or (MGC) et le bitcoin ({current?.name ?? 'BTC'}). Il applique les mêmes règles
            d’entrée et de sortie que le portefeuille IchiVol, sur la boucle {view.rules.timeframe}
            {view.rules.allow_short ? '' : ', sans vente à découvert'}. Chaque trade risque au plus{' '}
            {pct(view.rules.risk_pct, 1)} du capital jusqu’à son stop, et une position ne dépasse jamais{' '}
            {pct(view.rules.max_notional_pct, 0)} du capital.
          </p>
          {view.other_open_symbols.length > 0 ? (
            <p className="fc-note">
              Position encore ouverte sur un ancien instrument : {view.other_open_symbols.join(', ')}. Elle reste suivie
              (stop et objectif) jusqu’à sa fermeture.
            </p>
          ) : null}
        </div>
      </section>

      <div className="iv-grid">
        <section className="iv-card iv-s6 iv-m-s12">
          <div className="iv-card-head">
            <div className="iv-card-tabs">
              <span className="iv-card-tab is-on">Risque global</span>
            </div>
            <div className="iv-card-tools">
            <span className={`iv-tag ${left === 0 ? 'is-amber' : 'is-muted'}`}>
              {left == null ? '—' : left === 0 ? 'PLAFOND ATTEINT' : `${left} POSITION${left > 1 ? 'S' : ''} PLEINE${left > 1 ? 'S' : ''} POSSIBLE${left > 1 ? 'S' : ''}`}
            </span>
            </div>
          </div>
          <div className="iv-card-body">
            <p className="fc-note">
              Pour éviter que YM, l’or et BTC prennent tous une grosse position en même temps, le risque cumulé de toutes
              les positions ouvertes est plafonné à <b>{pct(view.rules.max_open_risk_pct, 1)}</b> du capital
              {capAmount != null ? ` (${eur(capAmount)})` : ''}. Avec {pct(view.rules.risk_pct, 1)} par trade, cela fait au
              plus deux positions de taille pleine à la fois : la suivante est refusée tant qu’une autre n’est pas
              fermée. Le refus apparaît plus bas dans « Ordres refusés par le risque ».
            </p>
            <div className="iv-row">
              <span>Risque ouvert / plafond</span>
              <span className="iv-row-v">
                {eur(openRisk)} / {capAmount != null ? eur(capAmount) : '—'}
              </span>
            </div>
            <Bar value={capAmount ? openRisk / capAmount : null} />
            {view.markets.map((m) => {
              const r = marketRisk(m.symbol, openPositions, equity, view.rules.max_open_risk_pct)
              return (
                <div key={m.symbol}>
                  <div className="iv-row">
                    <span>{m.slot}</span>
                    <span className="iv-row-v">
                      {eur(r.riskAmount)} · {pct(r.shareOfCap, 0)} du plafond
                    </span>
                  </div>
                  <Bar value={r.shareOfCap} />
                </div>
              )
            })}
            <p className="fc-hint">
              Perte du jour limitée à {pct(view.rules.daily_loss_limit_pct, 0)} du capital : au-delà, plus aucune
              entrée ce jour-là. Au plus {view.rules.max_open_positions} positions ouvertes.
            </p>
          </div>
        </section>

        <section className="iv-card iv-s6 iv-m-s12">
          <div className="iv-card-head">
            <div className="iv-card-tabs">
              <span className="iv-card-tab is-on">Instrument BTC</span>
            </div>
            <div className="iv-card-tools">{current?.contract ?? '—'}</div>
          </div>
          <div className="iv-card-body">
            <p className="fc-note">
              Selon la source de données et le courtier, « BTC » n’est pas le même instrument. Choisis celui que ce
              portefeuille trade. Le changement s’applique au prochain passage de la boucle.
            </p>
            <div className="fc-modes" role="radiogroup" aria-label="Instrument BTC">
              {view.btc_modes.map((m) => (
                <label key={m.mode} className={`fc-mode${choice === m.mode ? ' active' : ''}`}>
                  <input
                    type="radio"
                    name="btc-mode"
                    value={m.mode}
                    checked={choice === m.mode}
                    disabled={view.btc_mode_locked || saving}
                    onChange={() => setChoice(m.mode)}
                  />
                  <span>
                    <b>
                      {m.name} · {m.venue}
                    </b>
                    <small>
                      {m.contract_unit} par unité. Cours : {m.price_source}. {m.price_note}
                    </small>
                  </span>
                </label>
              ))}
            </div>
            {view.btc_mode_locked ? (
              <p className="fc-note">
                Une position BTC est ouverte : l’instrument est verrouillé jusqu’à sa fermeture, pour qu’elle ne change
                pas d’instrument en cours de route.
              </p>
            ) : null}
            {saveError ? <p className="fc-note neg">{saveError}</p> : null}
            <button
              type="button"
              className="iv-btn iv-btn--primary"
              disabled={view.btc_mode_locked || saving || choice === view.btc_mode}
              onClick={() => void saveMode()}
            >
              {saving ? 'Enregistrement…' : 'Utiliser cet instrument'}
            </button>
          </div>
        </section>
      </div>

      <div className="iv-grid">
        {view.markets.map((m) => (
          <MarketCard
            key={m.symbol}
            market={m}
            position={openPositions.find((p) => p.symbol === m.symbol) ?? null}
            equity={equity}
            maxOpenRiskPct={view.rules.max_open_risk_pct}
            allowShort={view.rules.allow_short}
          />
        ))}
      </div>
    </div>
  )
}
