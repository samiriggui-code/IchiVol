"""AG-FS0 — FactSheet : déterminisme, troncature, absences explicites, plafond, format FR."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.agents.analyst_cards import build_analyst_cards_from_candles
from app.agents.factsheet import (
    MAX_FACTS,
    SCHEMA,
    assemble,
    display_value,
    facts_from_calendar,
    facts_from_cards,
    facts_from_paper,
    facts_from_pipeline,
)
from tests.agents.test_analyst_cards import _make_tf_candles

NOW = 1_800_000_000


def _ids(facts):
    return [f["id"] for f in facts]


def _by_id(facts):
    return {f["id"]: f for f in facts}


# --- format -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        (1.529047, "1,529"),
        (83703.349, "83703,35"),
        (-0.00002585, "-0,000026"),
        (0.93, "0,93"),
        (12, "12"),
        (True, "oui"),
        (False, "non"),
        ("BEARISH", "BEARISH"),
        (None, None),
        (float("nan"), None),
    ],
)
def test_display_value_fr(value, shown):
    assert display_value(value) == shown


# --- fiches -----------------------------------------------------------------------------------


def _cards(n=220, as_of=None):
    candles = _make_tf_candles(n, "1h")
    return build_analyst_cards_from_candles(candles, symbol="BTCUSDT", timeframe="1h", as_of=as_of, now=NOW * 10)


def test_card_facts_have_provenance_and_stable_ids():
    facts = facts_from_cards(_cards())
    assert facts
    for f in facts:
        assert f["id"].startswith(f["engine"] + ".")
        assert f["timeframe"] == "1h" and f["as_of"] is not None and f["known_at"] is not None
        assert f["source"] == "engine" and f["validation_status"] == "NON_VALIDE"
        assert f["status"] in ("ok", "unavailable")
        assert (f["status"] == "ok") == (f["value"] is not None)
    assert _ids(facts) == _ids(facts_from_cards(_cards()))  # stables


def test_state_not_duplicated_when_equal_to_a_field():
    ids = set(_ids(facts_from_cards(_cards())))
    # rvol.state == anomaly_level et atr.state == regime : pas de doublon
    assert "rvol.anomaly_level" in ids and "rvol.state" not in ids
    assert "atr.regime" in ids and "atr.state" not in ids


@pytest.mark.parametrize("cut", [120, 160, 219])
def test_card_facts_truncation_invariant(cut):
    """Faits à as_of = T identiques, que la série s'arrête à T ou continue."""
    full = _make_tf_candles(220, "1h")
    t_cut = full[cut].time
    a = facts_from_cards(build_analyst_cards_from_candles(full, symbol="BTCUSDT", timeframe="1h", as_of=t_cut,
                                                          now=NOW * 10))
    b = facts_from_cards(build_analyst_cards_from_candles(full[: cut + 1], symbol="BTCUSDT", timeframe="1h",
                                                          as_of=t_cut, now=NOW * 10))
    assert a == b


# --- absences explicites ----------------------------------------------------------------------


def test_pipeline_unavailable_is_a_fact_not_an_omission():
    facts = facts_from_pipeline(None, timeframe="1h", as_of=NOW, reason="pipeline_error")
    by = _by_id(facts)
    assert by["pipeline.decision"]["status"] == "unavailable"
    assert by["pipeline.decision"]["reason"] == "pipeline_error"
    assert by["price.live"]["value"] is None


def test_pipeline_facts_non_valide():
    detail = {
        "price": 100.5,
        "direction": "LONG",
        "pipeline": {"decision": "BUY", "direction": "LONG",
                     "stages": [{"id": "direction", "status": "pass"}, {"id": "regime", "status": "fail"}]},
    }
    by = _by_id(facts_from_pipeline(detail, timeframe="1h", as_of=NOW))
    assert by["pipeline.decision"]["display"] == "BUY"
    assert by["pipeline.stage.regime.status"]["value"] == "fail"
    assert all(f["validation_status"] == "NON_VALIDE" for f in by.values())


def test_paper_no_position_and_lock():
    by = _by_id(facts_from_paper(None, {"entries_blocked": False, "kill_switch_armed": False,
                                        "daily_loss_locked": False}, timeframe="1h", as_of=NOW))
    assert by["paper.position.open"]["value"] is False and by["paper.position.open"]["status"] == "ok"
    assert "paper.position.entry_price" not in by
    assert by["paper.lock.entries_blocked"]["display"] == "non"


def test_paper_unavailable():
    facts = facts_from_paper(None, None, timeframe="1h", as_of=NOW, reason="paper_error")
    assert facts[0]["status"] == "unavailable" and facts[0]["reason"] == "paper_error"


@dataclass(frozen=True)
class _Ev:
    title: str
    country: str
    date: str
    impact: str


def test_calendar_next_high_event():
    events = [
        _Ev("CPI m/m", "USD", "2027-01-15T13:30:00Z", "High"),
        _Ev("Old", "USD", "2020-01-01T00:00:00Z", "High"),
        _Ev("PMI", "EUR", "2027-01-15T09:00:00Z", "Medium"),
    ]
    now = 1_800_000_000  # 2027-01-15T08:00:00Z
    by = _by_id(facts_from_calendar(events, now=now, timeframe="1h"))
    assert by["calendar.next_high.title"]["value"] == "CPI m/m"
    assert by["calendar.next_high.minutes_to"]["value"] == 330
    assert by["calendar.next_high.time_utc"]["value"] == "2027-01-15 13:30 UTC"


def test_calendar_unavailable_vs_no_event():
    down = facts_from_calendar(None, now=NOW, timeframe="1h", reason="calendar_error")
    assert down[0]["status"] == "unavailable"
    none_upcoming = facts_from_calendar([], now=NOW, timeframe="1h")
    assert none_upcoming[0]["status"] == "ok" and none_upcoming[0]["value"] is None


# --- assemblage -------------------------------------------------------------------------------


def test_assemble_deterministic_id_ignores_generated_at():
    groups = [facts_from_pipeline(None, timeframe="1h", as_of=NOW), facts_from_cards(_cards())]
    a = assemble(symbol="btcusdt", timeframe="1h", as_of=NOW, fact_groups=groups, engine_version="t",
                 generated_at="2026-01-01T00:00:00Z")
    b = assemble(symbol="BTCUSDT", timeframe="1h", as_of=NOW, fact_groups=groups, engine_version="t",
                 generated_at="2027-01-01T00:00:00Z")
    assert a["schema"] == SCHEMA and a["factsheet_id"] == b["factsheet_id"]
    assert {m["id"] for m in a["missing"]} == {f["id"] for f in a["facts"] if f["status"] != "ok"}


def test_assemble_caps_and_keeps_group_priority():
    many = [
        {"id": f"x.{i}", "status": "ok", "value": i} for i in range(MAX_FACTS + 10)
    ]
    first = facts_from_pipeline(None, timeframe="1h", as_of=NOW)
    out = assemble(symbol="X", timeframe="1h", as_of=NOW, fact_groups=[first, many], engine_version="t")
    assert len(out["facts"]) == MAX_FACTS
    assert out["truncated"] == len(first) + len(many) - MAX_FACTS
    assert _ids(out["facts"])[: len(first)] == _ids(first)  # le groupe prioritaire n'est jamais coupé


def test_factsheet_module_has_no_paper_write_or_screener_route():
    import ast
    from pathlib import Path

    import app.agents.factsheet as mod

    tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))
    names = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert not names & {"sync_position", "sync_auto_watchlist", "open_user_confirmed", "close_manually"}
    assert "/screener" not in Path(mod.__file__).read_text(encoding="utf-8")
