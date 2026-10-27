"""Caisse d'un compte paper sous accès concurrents (bug ICHIVOL_WIDE_V1 du 27/10/2026).

Deux ventes à découvert ouvertes à 13 s d'intervalle : le relevé suivant comptait la caisse d'avant la
seconde ouverture mais les deux positions, soit une mise « fantôme » dans l'equity (+24 % affichés).

Chaque test utilise un compte jetable (code unique), validé en base pour que plusieurs sessions le
voient, puis supprimé. Vrai PostgreSQL requis (verrous de ligne) : ignorés sinon.
"""

from __future__ import annotations

import threading
import time
import uuid
from copy import deepcopy
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.agents.types import Direction
from app.brokerage import persistence as ledger_db
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
from app.paper import broker
from app.paper import engine as paper_engine
from app.paper.financing import apply_daily_financing, financing_total_for_position
from app.paper.strategy_profiles import BASELINE_PROFILE

try:
    with engine.connect() as _c:
        DB = _c.dialect.name == "postgresql"
except OperationalError:
    DB = False

pytestmark = pytest.mark.skipif(not DB, reason="PostgreSQL not reachable")

INITIAL = 20_000.0


@pytest.fixture()
def pid():
    s = SessionLocal()
    code = f"CONC_{uuid.uuid4().hex[:10]}"
    prof = deepcopy(BASELINE_PROFILE)
    prof.update(code=code, max_open_positions=10, max_notional_pct=0.9)
    p = PaperPortfolio(
        code=code, label="cash-concurrency", currency="EUR",
        initial_cash=INITIAL, cash=INITIAL, realized_pnl=0.0, strategy_profile=prof,
    )
    s.add(p)
    s.commit()
    portfolio_id = p.id
    s.close()
    yield portfolio_id
    s = SessionLocal()
    s.query(LedgerLeg).filter(
        LedgerLeg.transaction_id.in_(
            s.query(LedgerTransaction.id).filter_by(portfolio_id=portfolio_id)
        )
    ).delete(synchronize_session=False)
    for m in (LedgerTransaction, PaperOrder, PaperJournalEvent, PaperEquitySnapshot, PaperPosition):
        s.query(m).filter_by(portfolio_id=portfolio_id).delete(synchronize_session=False)
    s.query(PaperPortfolio).filter_by(id=portfolio_id).delete()
    s.commit()
    s.close()


def _open(s, pf, *, symbol, direction="LONG", price=100.0, notional=6000.0):
    return broker.open_capital_position(
        s, portfolio=pf, symbol=symbol, timeframe="1h", source="user_confirmed", user_id=None,
        direction=direction, price=price, decision="BUY" if direction == "LONG" else "SELL",
        stop_distance=price * 0.05, manual_notional=notional,
    )


def _open_committed(pid, **kw) -> str:
    s = SessionLocal()
    try:
        pos = _open(s, s.get(PaperPortfolio, pid), **kw)
        assert pos is not None
        s.commit()
        return pos.id
    finally:
        s.close()


def _assert_books_balance(pid) -> PaperPortfolio:
    """caisse + Σ(mise + frais d'entrée + financement payé) des lots ouverts = capital initial + PnL réalisé,
    et caisse = solde du grand livre (écritures indépendantes du champ ``cash``)."""
    s = SessionLocal()
    try:
        pf = s.get(PaperPortfolio, pid)
        opens = s.execute(
            select(PaperPosition).where(PaperPosition.portfolio_id == pid, PaperPosition.status == "OPEN")
        ).scalars().all()
        tied_up = sum(
            float(p.notional or 0) + float(p.entry_fee or 0) + financing_total_for_position(s, p.id) for p in opens
        )
        assert pf.cash + tied_up == pytest.approx(pf.initial_cash + pf.realized_pnl, abs=1e-6)
        assert abs(ledger_db.reconcile_cash(s, pf)) < 1e-4
        s.expunge(pf)
        return pf
    finally:
        s.close()


def _spent(pid) -> float:
    s = SessionLocal()
    try:
        return sum(
            float(p.notional) + float(p.entry_fee)
            for p in s.execute(select(PaperPosition).where(PaperPosition.portfolio_id == pid)).scalars()
        )
    finally:
        s.close()


def _run_concurrently(*fns) -> list[BaseException]:
    errors: list[BaseException] = []

    def wrap(fn):
        def run():
            try:
                fn()
            except BaseException as exc:  # noqa: BLE001 -- reported by the test
                errors.append(exc)
        return run

    threads = [threading.Thread(target=wrap(fn)) for fn in fns]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return errors


def test_two_concurrent_opens_debit_cash_twice(pid):
    """Deux ouvertures simultanées : chacune lit la caisse au même moment puis débite sa mise."""
    barrier = threading.Barrier(2)

    def opener(symbol, direction):
        def run():
            s = SessionLocal()
            try:
                pf = s.get(PaperPortfolio, pid)
                assert pf.cash == INITIAL  # both read the same balance before either writes
                barrier.wait(timeout=10)
                assert _open(s, pf, symbol=symbol, direction=direction) is not None
                time.sleep(0.3)  # keep the transaction open: widest window for a lost update
                s.commit()
            finally:
                s.close()
        return run

    errors = _run_concurrently(opener("CONCAPTUSDT", "SHORT"), opener("CONCAAVEUSDT", "SHORT"))
    assert errors == []
    pf = _assert_books_balance(pid)
    assert pf.cash == pytest.approx(INITIAL - _spent(pid), abs=1e-6)


def test_concurrent_open_and_close_keep_both_cash_moves(pid):
    first = _open_committed(pid, symbol="CONCBTCUSDT")
    barrier = threading.Barrier(2)

    def closer():
        s = SessionLocal()
        try:
            pos = s.get(PaperPosition, first)
            s.get(PaperPortfolio, pid).cash  # noqa: B018 -- load the balance before the other side writes
            barrier.wait(timeout=10)
            broker.close_capital_position(s, pos, price=110.0, reason="manual_close")
            time.sleep(0.3)
            s.commit()
        finally:
            s.close()

    def opener():
        s = SessionLocal()
        try:
            pf = s.get(PaperPortfolio, pid)
            barrier.wait(timeout=10)
            assert _open(s, pf, symbol="CONCETHUSDT") is not None
            time.sleep(0.3)
            s.commit()
        finally:
            s.close()

    errors = _run_concurrently(closer, opener)
    assert errors == []
    pf = _assert_books_balance(pid)
    assert pf.realized_pnl > 0  # the close went through and was credited


def test_snapshot_reads_cash_and_positions_from_the_same_state(pid):
    """Le cas de production : la boucle de scan a chargé le compte, un ordre manuel est validé ailleurs,
    puis la boucle écrit son relevé. Avant correction : ancienne caisse + nouvelle position = mise fantôme."""
    _open_committed(pid, symbol="CONCAPTUSDT", direction="SHORT")
    scan = SessionLocal()
    try:
        pf = scan.get(PaperPortfolio, pid)
        stale_cash = pf.cash  # loaded at the start of the scan cycle
        _open_committed(pid, symbol="CONCAAVEUSDT", direction="SHORT")  # manual order, other request
        snap = broker.snapshot_equity(scan, pf, marks={})  # marks default to entry prices
        scan.commit()
        assert snap.cash < stale_cash
        assert snap.cash == pytest.approx(INITIAL - _spent(pid), abs=1e-6)
        # At entry prices the only loss is the entry commissions — no phantom stake.
        assert snap.equity == pytest.approx(INITIAL - _entry_fees(pid), abs=1e-6)
    finally:
        scan.close()


def _entry_fees(pid) -> float:
    s = SessionLocal()
    try:
        return sum(
            float(p.entry_fee)
            for p in s.execute(select(PaperPosition).where(PaperPosition.portfolio_id == pid)).scalars()
        )
    finally:
        s.close()


def test_financing_does_not_overwrite_a_concurrent_open(pid):
    """Le financement de nuit réécrivait ``cash = ancienne valeur − frais`` sans verrou."""
    _open_committed(pid, symbol="EURUSD", price=1.10, notional=3000.0)
    monitor = SessionLocal()  # protection monitor: loads every active portfolio first
    try:
        pf = monitor.get(PaperPortfolio, pid)
        assert pf.cash < INITIAL
        _open_committed(pid, symbol="CONCSOLUSDT")  # committed meanwhile by another request
        applied = apply_daily_financing(
            monitor, pf, as_of=datetime(2026, 10, 27, 3, 0, tzinfo=timezone.utc), force_day=date(2026, 10, 27)
        )
        monitor.commit()
        assert applied, "EURUSD must carry an overnight financing charge"
    finally:
        monitor.close()
    pf = _assert_books_balance(pid)
    charges = sum(a["charge"] for a in applied)
    assert pf.cash == pytest.approx(INITIAL - _spent(pid) - charges, abs=1e-6)


def test_risk_kernel_runs_again_on_the_locked_account(pid, monkeypatch):
    """Les contrôles de risque se font sur le compte verrouillé : un arrêt d'urgence armé entre le
    pré-contrôle et le verrou doit bloquer l'ouverture."""
    real_eval = paper_engine.risk_kernel_evaluate
    calls: list[bool] = []

    def eval_with_concurrent_kill_switch(*args, **kwargs):
        if not calls:
            other = SessionLocal()
            try:
                other.get(PaperPortfolio, pid).kill_switch_armed = True
                other.commit()
            finally:
                other.close()
        decision = real_eval(*args, **kwargs)
        calls.append(decision.accepted)
        return decision

    monkeypatch.setattr(paper_engine, "risk_kernel_evaluate", eval_with_concurrent_kill_switch)
    s = SessionLocal()
    try:
        pf = s.get(PaperPortfolio, pid)
        result = paper_engine.sync_position(
            s, symbol="CONCXRPUSDT", timeframe="1h", source="user_confirmed", user_id="u",
            price=100.0, pipeline=PipelineResult(decision="BUY", direction=Direction.LONG, stages=[]),
            stop_distance=5.0, portfolio=pf, manual_notional=1000.0,
        )
        s.commit()
    finally:
        s.close()
    assert result is None
    assert _spent(pid) == 0.0
    assert calls[-1] is False


def test_snapshot_values_shorts_with_their_unrealized_pnl(pid):
    """Vente à découvert : la vue d'ensemble compte mise + gain latent ; le relevé ne comptait que la mise."""
    pos_id = _open_committed(pid, symbol="CONCAAVEUSDT", direction="SHORT", notional=5000.0)
    s = SessionLocal()
    try:
        pos = s.get(PaperPosition, pos_id)
        mark = pos.entry_price * 0.9  # price fell 10 %: the short gains
        gain = pos.qty * (pos.entry_price - mark)
        pf = s.get(PaperPortfolio, pid)
        snap = broker.snapshot_equity(s, pf, marks={"CONCAAVEUSDT:1h": mark})
        s.commit()
        assert snap.unrealized_pnl == pytest.approx(gain)
        assert snap.positions_value == pytest.approx(pos.notional + gain)
        # same formula as the overview (app/api/paper.py): cash + invested + unrealized
        assert snap.equity == pytest.approx(pf.cash + pos.notional + gain)
    finally:
        s.close()
