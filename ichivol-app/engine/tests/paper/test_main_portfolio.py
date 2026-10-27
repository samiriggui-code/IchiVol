"""Portefeuille unique ICHIVOL_MAIN_V1 (2026-10-27) : un seul compte synchronisé, 50 000 €, anciens codes ignorés,
univers explicite + règle de liquidité, filtres et sessions en observation, arbitrage entre moteurs."""

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.agents.types import Direction
from app.db.models import (
    LedgerLeg,
    LedgerTransaction,
    PaperEquitySnapshot,
    PaperJournalEvent,
    PaperOrder,
    PaperPortfolio,
    PaperPosition,
)
from app.db.session import SessionLocal, engine
from app.decision.pipeline import PipelineResult
from app.paper import engine as paper
from app.paper import gates as paper_gates
from app.paper.portfolio import (
    PROFILE_SYNC_EVENT,
    RetiredPortfolioError,
    ensure_main_portfolio,
    ensure_syncable_portfolios,
    list_portfolios,
    lookup_portfolio,
    resolve_trading_portfolio,
)
from app.paper.strategy_profiles import (
    ALL_PROFILES,
    MAIN_CODE,
    MAIN_PROFILE,
    RETIRED_CODES,
    WIDE_EXTRA_SYMBOLS,
    liquidity_exclusion,
    main_universe,
    syncable_profile_codes,
)

try:
    with engine.connect():
        pass
    DB = True
except OperationalError:
    DB = False

db = pytest.mark.skipif(not DB, reason="Postgres not reachable")

RETIRED = (
    "ICHIVOL_BASELINE_V1", "ICHIVOL_4H_V1", "ICHIVOL_WIDE_V1", "ICHIVOL_SHORTS_V1",
    "ICHIVOL_SESSIONS_V1", "ICHIVOL_COMBO_V1", "RS_D1_PAPER_V1", "FUTURES_CRYPTO_V1",
)


# --- profil -----------------------------------------------------------------------------------------------

def test_only_the_main_account_is_synced():
    assert syncable_profile_codes() == [MAIN_CODE]
    assert set(RETIRED_CODES) == set(RETIRED)
    assert MAIN_CODE not in RETIRED_CODES


def test_main_profile_is_explicit_50k_long_only():
    p = ALL_PROFILES[MAIN_CODE]
    assert p["initial_cash_eur"] == 50_000.0
    assert p["risk_pct"] == 0.005 and p["max_notional_pct"] == 0.10
    assert p["max_open_positions"] == 10 and p["max_open_risk_pct"] == 0.04
    assert p["daily_loss_limit_pct"] == 0.03 and p["allow_short"] is False
    assert p["auto_timeframes"] == ["1h"] and p["one_position_per_symbol"] is True


def test_universe_covers_every_class_the_engine_trades():
    traded, excluded = main_universe()
    for s in ("BTCUSDT", "ETHUSDT", "SOLUSDT", "EURUSD", "GBPUSD", "XAUUSD", "XAGUSD", "SPX", "NDX", "WTI", "YM"):
        assert s in traded, s
    assert set(WIDE_EXTRA_SYMBOLS) <= set(traded)
    # exclusions documentées
    assert "PEPEUSDT" in excluded and "liquidité" in excluded["PEPEUSDT"]
    for s in ("USDJPY", "MGC", "BTCPERP", "BTCCME", "AAPL", "TSLA"):
        assert s in excluded and s not in traded
    assert MAIN_PROFILE["universe_symbols"] == traded


def test_every_traded_symbol_has_a_documented_cost():
    for s in MAIN_PROFILE["universe_symbols"]:
        assert liquidity_exclusion(s) is None
        assert s in MAIN_PROFILE["friction_bps_by_symbol"]
    assert liquidity_exclusion("NOPEUSDT") is not None  # coût inconnu → refusé
    assert MAIN_PROFILE["commission_bps_by_symbol"]["EURUSD"] == 0.0  # CFD : spread seul
    assert MAIN_PROFILE["commission_bps_by_symbol"]["YM"] == pytest.approx(0.1)


def test_trades_symbol_follows_the_explicit_universe():
    assert paper.trades_symbol(MAIN_PROFILE, "TRXUSDT")
    assert paper.trades_symbol(MAIN_PROFILE, "YM")
    assert not paper.trades_symbol(MAIN_PROFILE, "PEPEUSDT")
    assert not paper.trades_symbol(MAIN_PROFILE, "MGC")


def test_dynamic_liquidity_rule_on_real_volume_rows_only():
    def row(exchange, vol):
        candles = [SimpleNamespace(close=100.0, volume=vol) for _ in range(30)]
        return SimpleNamespace(exchange=exchange, timeframe="1h", candles=candles)

    # 24 bougies x 100 x 1000 = 2,4 M < 5 M → refus ; 24 x 100 x 5000 = 12 M → ok ; CFD → jamais
    assert paper.liquidity_refusal(MAIN_PROFILE, row("binance", 1000)) == "illiquid_24h_volume"
    assert paper.liquidity_refusal(MAIN_PROFILE, row("binance", 5000)) is None
    assert paper.liquidity_refusal(MAIN_PROFILE, row("biquote", 0)) is None


# --- base de données -----------------------------------------------------------------------------------------

def _pipeline(decision: str) -> PipelineResult:
    direction = {"BUY": Direction.LONG, "SELL": Direction.SHORT}.get(decision, Direction.NEUTRAL)
    return PipelineResult(decision=decision, direction=direction, stages=[])


def _disposable(session, **overrides) -> PaperPortfolio:
    code = f"T_MAIN_{uuid.uuid4().hex[:8]}"
    prof = deepcopy(MAIN_PROFILE) | overrides | {"code": code}
    now = datetime.now(timezone.utc)
    pf = PaperPortfolio(code=code, label="main-test", currency="EUR", initial_cash=50_000.0, cash=50_000.0,
                        realized_pnl=0.0, strategy_profile=prof, is_active=True, started_at=now,
                        created_at=now, updated_at=now)
    session.add(pf)
    session.flush()
    return pf


def _drop(session, pf: PaperPortfolio) -> None:
    pid = pf.id
    session.rollback()
    session.query(PaperEquitySnapshot).filter_by(portfolio_id=pid).delete()
    session.query(LedgerLeg).filter(
        LedgerLeg.transaction_id.in_(session.query(LedgerTransaction.id).filter_by(portfolio_id=pid))
    ).delete(synchronize_session=False)
    for model in (LedgerTransaction, PaperOrder, PaperJournalEvent, PaperPosition):
        session.query(model).filter_by(portfolio_id=pid).delete()
    session.query(PaperPortfolio).filter_by(id=pid).delete()
    session.commit()
    paper_gates.reset_run_memory()


@pytest.fixture()
def session():
    s = SessionLocal()
    yield s
    s.rollback()
    s.close()


@db
def test_main_account_created_at_50k_and_profile_realigned(session):
    pf = ensure_main_portfolio(session)
    session.commit()
    assert pf.code == MAIN_CODE
    # profil stocké divergent → réaligné et journalisé, caisse intacte
    cash = pf.cash
    pf.strategy_profile = {**pf.strategy_profile, "risk_pct": 0.02}
    session.commit()
    pf = ensure_main_portfolio(session)
    session.commit()
    assert pf.strategy_profile["risk_pct"] == 0.005 and pf.cash == cash
    ev = session.query(PaperJournalEvent).filter_by(portfolio_id=pf.id, event_type=PROFILE_SYNC_EVENT).all()
    assert any("risk_pct" in (e.payload or {}).get("changed_keys", []) for e in ev)


@db
def test_new_main_account_starts_with_50k(session):
    existing = session.query(PaperPortfolio).filter_by(code=MAIN_CODE).one_or_none()
    if existing is not None:  # met de côté le compte de la base de test le temps du test
        existing.code = f"T_ASIDE_{uuid.uuid4().hex[:8]}"
        session.commit()
    try:
        pf = ensure_main_portfolio(session)
        session.commit()
        assert pf.initial_cash == 50_000.0 and pf.cash == 50_000.0
        assert pf.strategy_profile["code"] == MAIN_CODE
        _drop(session, pf)
    finally:
        if existing is not None:
            existing.code = MAIN_CODE
            session.commit()


@db
def test_retired_accounts_are_never_synced_listed_or_recreated(session):
    # un ancien compte encore en base (avant le script de suppression), même is_active=true
    code = "ICHIVOL_WIDE_V1"
    old = session.query(PaperPortfolio).filter_by(code=code).one_or_none()
    created = old is None
    if created:
        old = PaperPortfolio(code=code, label="old", currency="EUR", initial_cash=25_000.0, cash=25_000.0,
                             realized_pnl=0.0, strategy_profile={"code": code}, is_active=True)
        session.add(old)
        session.commit()
    try:
        assert [p.code for p in ensure_syncable_portfolios(session)] == [MAIN_CODE]
        assert code not in [p.code for p in list_portfolios(session)]
        with pytest.raises(RetiredPortfolioError):
            resolve_trading_portfolio(session, code)
        assert resolve_trading_portfolio(session, None).code == MAIN_CODE
        from app.eve.paper_submit import virtual_portfolio_codes

        assert virtual_portfolio_codes(session) == [MAIN_CODE]
    finally:
        if created:
            session.delete(old)
            session.commit()
    # un ancien code absent n'est jamais recréé par une simple lecture
    for c in ("RS_D1_PAPER_V1", "FUTURES_CRYPTO_V1", "ICHIVOL_SESSIONS_V1"):
        if session.query(PaperPortfolio).filter_by(code=c).one_or_none() is None:
            assert lookup_portfolio(session, c) is None
            assert session.query(PaperPortfolio).filter_by(code=c).one_or_none() is None


@db
def test_api_lists_only_the_main_account_and_refuses_retired_codes():
    from app.main import app

    client = TestClient(app)
    rows = client.get("/api/engine/paper/portfolios").json()["portfolios"]
    assert [r["code"] for r in rows] == [MAIN_CODE]
    assert client.get(f"/api/engine/paper/portfolios/{MAIN_CODE}/overview").status_code == 200
    r = client.get("/api/engine/paper/preview", params={"symbol": "BTCUSDT", "notional": 100,
                                                         "portfolio_code": "ICHIVOL_BASELINE_V1"})
    assert r.status_code == 403 and "retired_portfolio" in r.text
    assert client.get("/api/engine/paper/futures-crypto").status_code == 404


# --- arbitrage entre moteurs -----------------------------------------------------------------------------------

@db
def test_arbitration_first_engine_owns_the_symbol(session):
    """Scan, Ève et ordre manuel sur le même symbole : un seul lot (premier arrivé), aucun autre moteur n'en
    ouvre un second, ni dans le même sens ni dans l'autre, et le scan ne ferme jamais le lot d'un autre moteur."""
    pf = _disposable(session)
    try:
        # 1) Ève ouvre la première (chemin open_user_confirmed, comme paper_submit)
        lot, created = paper.open_user_confirmed(
            session, symbol="ETHUSDT", timeframe="1h", user_id="eve_intelligence", price=2000.0,
            pipeline=_pipeline("BUY"), stop_distance=40.0, portfolio=pf,
            signal_extra={"eve_dossier_id": "d-test"},
        )
        assert created and lot is not None
        # 2) le scan veut ouvrir le même symbole → aucun second lot
        again = paper.sync_position(
            session, symbol="ETHUSDT", timeframe="1h", source="auto_watchlist", user_id=None, price=2001.0,
            pipeline=_pipeline("BUY"), stop_distance=40.0, portfolio=pf,
        )
        assert again is None
        # 3) un ordre manuel (sens opposé ou même sens) → le lot existant est rendu, rien n'est créé
        same, created2 = paper.open_user_confirmed(
            session, symbol="ETHUSDT", timeframe="4h", user_id="u1", price=2002.0,
            pipeline=_pipeline("SELL"), stop_distance=40.0, portfolio=pf,
        )
        assert not created2 and same.id == lot.id
        # 4) le scan voit le signal se dégrader : il ne ferme pas le lot d'Ève
        paper.sync_position(
            session, symbol="ETHUSDT", timeframe="1h", source="auto_watchlist", user_id=None, price=2003.0,
            pipeline=_pipeline("NO_TRADE"), stop_distance=40.0, portfolio=pf,
        )
        opens = session.query(PaperPosition).filter_by(portfolio_id=pf.id, status="OPEN").all()
        assert [p.id for p in opens] == [lot.id]
        # 5) l'engine_proposal (mode Ève décide) ne propose ni ouverture ni fermeture sur ce lot étranger
        assert paper.engine_proposal(session, portfolio=pf, symbol="ETHUSDT", timeframe="1h",
                                     pipeline=_pipeline("BUY"), signal_actions=True) is None
        assert paper.engine_proposal(session, portfolio=pf, symbol="ETHUSDT", timeframe="1h",
                                     pipeline=_pipeline("NO_TRADE"), signal_actions=True) is None
        assert paper.engine_proposal(session, portfolio=pf, symbol="ETHUSDT", timeframe="1h",
                                     pipeline=_pipeline("SELL"), signal_actions=True) is None
    finally:
        _drop(session, pf)


@db
def test_scan_lot_then_eve_cannot_double_and_short_is_refused(session):
    pf = _disposable(session)
    try:
        lot = paper.sync_position(
            session, symbol="SOLUSDT", timeframe="1h", source="auto_watchlist", user_id=None, price=150.0,
            pipeline=_pipeline("BUY"), stop_distance=3.0, portfolio=pf,
        )
        assert lot is not None and lot.status == "OPEN"
        pos, created = paper.open_user_confirmed(
            session, symbol="SOLUSDT", timeframe="1h", user_id="eve_intelligence", price=150.5,
            pipeline=_pipeline("BUY"), stop_distance=3.0, portfolio=pf,
        )
        assert not created and pos.id == lot.id
        # vente à découvert refusée sur un autre symbole (allow_short=False)
        assert paper.sync_position(
            session, symbol="BNBUSDT", timeframe="1h", source="auto_watchlist", user_id=None, price=600.0,
            pipeline=_pipeline("SELL"), stop_distance=10.0, portfolio=pf,
        ) is None
    finally:
        _drop(session, pf)


def _row(symbol, decision, price, candles, exchange="binance"):
    return SimpleNamespace(
        symbol=symbol, timeframe="1h", exchange=exchange, price=price, candles=candles,
        pipeline=_pipeline(decision), atr=SimpleNamespace(suggested_stop_distance=price * 0.02),
        rvol=None, signal_timing={"signal_bar_close": 1_700_000_000}, mtf_matrix=None,
    )


@db
def test_sync_loop_keeps_filters_in_observation_and_refuses_illiquid(monkeypatch, session):
    """Les filtres (structure/Fibonacci/contexte) bloqueraient : en observation le trade s'ouvre quand même et
    leur verdict est enregistré ; une paire à faible volume 24 h n'ouvre rien."""
    from app.context.gate import ContextGateResult

    pf = _disposable(session)
    session.commit()
    monkeypatch.setattr(paper, "ensure_syncable_portfolios", lambda s: [s.get(PaperPortfolio, pf.id)])

    def _blocking_ctx(pipeline, candles, profile):
        return ContextGateResult(pipeline=_pipeline("WATCH"), blocked=True, reason="rsi_overbought",
                                 context_payload={"rsi": 80}, raw_decision="BUY")

    monkeypatch.setattr(paper, "apply_context_gate", _blocking_ctx)
    liquid = [SimpleNamespace(time=1_700_000_000 + i * 3600, open=100.0, high=101.0, low=99.0, close=100.0,
                              volume=10_000.0) for i in range(60)]
    thin = [SimpleNamespace(time=c.time, open=1.0, high=1.0, low=1.0, close=1.0, volume=10.0) for c in liquid]
    try:
        paper.sync_auto_watchlist(session, [
            _row("LINKUSDT", "BUY", 100.0, liquid),
            _row("AVAXUSDT", "BUY", 1.0, thin),
        ])
        opens = {p.symbol: p for p in session.query(PaperPosition).filter_by(portfolio_id=pf.id, status="OPEN")}
        assert "LINKUSDT" in opens and "AVAXUSDT" not in opens
        observed = (opens["LINKUSDT"].entry_signal or {}).get("filters_observed")
        assert observed and observed["would_block"] is True and observed["context_blocked"] is True
        assert (opens["LINKUSDT"].entry_signal or {}).get("decision_window_observed") is True
        rej = session.query(PaperJournalEvent).filter_by(portfolio_id=pf.id).all()
        assert any((e.payload or {}).get("reason") == "illiquid_24h_volume" for e in rej)
    finally:
        _drop(session, pf)


# --- bilan par décideur / classe d'actifs ------------------------------------------------------------------

def test_breakdown_decider_and_asset_class_rules():
    from app.paper.breakdown import asset_class_of, decider_of, drawdown, score

    P = SimpleNamespace
    assert decider_of(P(source="auto_watchlist", user_id=None, entry_signal={})) == "engine"
    assert decider_of(P(source="user_confirmed", user_id="eve_intelligence", entry_signal={})) == "eve"
    assert decider_of(P(source="user_confirmed", user_id="engine_over_eve",
                        entry_signal={"decided_by": "engine_over_eve"})) == "engine_over_eve"
    assert decider_of(P(source="user_confirmed", user_id="u1", entry_signal=None)) == "manual"
    assert asset_class_of("BTCUSDT") == "crypto" and asset_class_of("TRXUSDT") == "crypto"
    assert asset_class_of("EURUSD") == "forex" and asset_class_of("XAUUSD") == "metal"
    assert asset_class_of("SPX") == "index" and asset_class_of("WTI") == "energy" and asset_class_of("YM") == "future"
    rows = [P(status="CLOSED", realized_pnl=100.0, entry_fee=1.0, exit_fee=1.0, k="a"),
            P(status="CLOSED", realized_pnl=-50.0, entry_fee=1.0, exit_fee=1.0, k="a"),
            P(status="OPEN", realized_pnl=None, k="a")]
    s = score(rows, lambda p: p.k)["a"]
    assert (s["trades"], s["wins"], s["losses"], s["open"], s["net"], s["win_rate"]) == (2, 1, 1, 1, 50.0, 0.5)
    dd = drawdown([50_000, 55_000, 49_500, 52_000], 50_000)
    assert dd["max_pct"] == pytest.approx(0.1) and dd["current_pct"] == pytest.approx(3_000 / 55_000)


@db
def test_breakdown_route_for_the_main_account():
    from app.main import app

    body = TestClient(app).get(f"/api/engine/paper/portfolios/{MAIN_CODE}/breakdown").json()
    assert [d["decider"] for d in body["by_decider"]] == ["eve", "engine_over_eve", "engine", "manual"]
    assert body["rules"]["initial_cash"] > 0 and body["rules"]["allow_short"] is False
    assert any(x["symbol"] == "YM" for x in body["universe"]["symbols"])
    assert any(x["symbol"] == "PEPEUSDT" for x in body["universe"]["exclusions"])


@db
def test_positions_route_filters_on_the_main_account_and_paginates():
    from app.main import app

    c = TestClient(app)
    body = c.get("/api/engine/paper/positions", params={"portfolio_code": MAIN_CODE, "limit": 1}).json()
    assert "total" in body and len(body["positions"]) <= 1
    assert c.get("/api/engine/paper/positions", params={"portfolio_code": "NOPE_X"}).status_code == 404


def test_decision_summary_exposes_the_synthesis_rule():
    from app.eve.dossier import decision_summary

    d = SimpleNamespace(
        id="d1", created_at=None, symbol="BTCUSDT", timeframe="1h", baseline_decision="BUY", eve_action="LONG",
        execution_status="opened", decision_time_json={}, verdict_id=None,
        modes_json={"synthesis": {"decision_rule": "analyst", "rationale": "Règle 4"}},
    )
    assert decision_summary(d, None)["decision_rule"] == "analyst"
