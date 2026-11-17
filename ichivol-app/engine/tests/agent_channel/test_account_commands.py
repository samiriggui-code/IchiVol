"""Outils « compte » du canal agent : le chat lit le compte paper sans demander de symbole (lecture seule)."""

from __future__ import annotations

import json

import pytest

from app.agent_channel.registry import TOOLS, dispatch_command
from app.paper import broker as paper_broker
from tests.paper.test_margin import _open, book, db, session  # noqa: F401 -- fixtures pytest

ACCOUNT_TOOLS = (
    "get_account_overview",
    "list_account_positions",
    "get_account_performance",
    "get_account_breakdown",
)
# Limite appliquée par le serveur du chat à un résultat d'outil (MAX_TOOL_RESULT_CHARS).
TOOL_RESULT_LIMIT = 12_000


@pytest.fixture()
def no_network(monkeypatch):
    """La vue du compte va chercher un cours pour chaque lot ouvert : aucun appel réseau pendant les tests."""
    monkeypatch.setattr("app.paper.marks.resolve_marks", lambda *a, **k: {})


def test_account_tools_are_registered_read_only() -> None:
    for name in ACCOUNT_TOOLS:
        assert TOOLS[name].read_only is True


def test_unknown_account_is_a_command_error_not_a_crash() -> None:
    for name in ("get_account_overview", "list_account_positions", "get_account_breakdown"):
        out = dispatch_command(name, {"portfolio_code": "COMPTE_QUI_N_EXISTE_PAS"})
        assert out == {"ok": False, "cmd": name, "error": "portfolio_not_found"}


def test_bad_arguments_are_refused() -> None:
    assert dispatch_command("list_account_positions", {"status": "PERDANTS"})["ok"] is False
    assert dispatch_command("list_account_positions", {"limit": "beaucoup"})["ok"] is False
    assert dispatch_command("get_account_overview", {"portfolio_code": 12})["ok"] is False


@db
def test_closed_and_open_lots_are_listed_with_their_result(session, book, no_network) -> None:
    lost, _ = _open(session, book, "WTI", 5.0, 100.0, "SHORT")
    session.commit()
    paper_broker.close_capital_position(session, lost, price=lost.stop_price, reason="stop_hit", signal={})
    still_open, _ = _open(session, book, "EURUSD", 0.01, 1.0, "SHORT")
    session.commit()
    assert lost is not None and still_open is not None

    closed = dispatch_command("list_account_positions", {"portfolio_code": book.code})
    assert closed["ok"] is True
    data = closed["data"]
    assert data["status"] == "CLOSED" and data["total"] == 1
    row = data["positions"][0]
    assert row["symbol"] == "WTI" and row["exit_reason"] == "stop_hit"
    assert row["realized_pnl"] < 0
    assert row["decider"] == "eve" and row["decider_label"] == "Ève"
    assert "entry_signal" not in row  # le détail brut du signal ne part pas dans le chat

    opened = dispatch_command("list_account_positions", {"portfolio_code": book.code, "status": "OPEN"})
    assert [p["symbol"] for p in opened["data"]["positions"]] == ["EURUSD"]

    everything = dispatch_command("list_account_positions", {"portfolio_code": book.code, "status": "ALL", "limit": 1})
    assert everything["data"]["total"] == 2 and len(everything["data"]["positions"]) == 1


@db
def test_overview_gives_the_account_without_the_full_curve(session, book, no_network) -> None:
    lost, _ = _open(session, book, "WTI", 5.0, 100.0, "SHORT")
    session.commit()
    paper_broker.close_capital_position(session, lost, price=lost.stop_price, reason="stop_hit", signal={})
    _open(session, book, "EURUSD", 0.01, 1.0, "SHORT")
    session.commit()

    out = dispatch_command("get_account_overview", {"portfolio_code": book.code})
    assert out["ok"] is True
    data = out["data"]
    assert data["portfolio"]["code"] == book.code
    assert data["account"]["initial_cash"] == 50_000.0
    assert data["account"]["realized_pnl"] < 0
    assert data["account"]["open_positions"] == 1
    assert [p["symbol"] for p in data["open_positions"]] == ["EURUSD"]
    assert "recent_refusals" in data["risk"]
    assert "equity_curve" not in data and set(data["equity_curve_summary"]) == {"points", "first", "last", "low", "high"}
    assert len(json.dumps(data, default=str)) < TOOL_RESULT_LIMIT


@db
def test_breakdown_says_who_decided_and_keeps_the_universe_short(session, book) -> None:
    lost, _ = _open(session, book, "WTI", 5.0, 100.0, "SHORT")
    session.commit()
    paper_broker.close_capital_position(session, lost, price=lost.stop_price, reason="stop_hit", signal={})
    session.commit()

    out = dispatch_command("get_account_breakdown", {"portfolio_code": book.code})
    assert out["ok"] is True
    data = out["data"]
    eve = next(d for d in data["by_decider"] if d["decider"] == "eve")
    assert eve["trades"] == 1
    assert data["rules"]["margin"] == {"crypto_max_exposure": 1.0, "other_max_exposure": 1.0}
    assert all(isinstance(s, str) for s in data["universe"]["symbols"])
    assert len(json.dumps(data, default=str)) < TOOL_RESULT_LIMIT


@db
def test_performance_of_the_main_account_answers() -> None:
    out = dispatch_command("get_account_performance", {})
    assert out["ok"] is True
    assert {"num_closed_trades", "win_rate", "max_drawdown", "equity"} <= set(out["data"])
