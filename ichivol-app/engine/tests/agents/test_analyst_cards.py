"""AG-S1 — fiches analystes : anti-lookahead, RS-01, imports, idempotence."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.agents.analyst_cards import (
    DECISION_ROLE_BY_FEATURE,
    STAGE_BY_FEATURE,
    STAGES,
    build_analyst_cards_from_candles,
    stage_for_feature,
)
from app.agents.analyst_snapshot import upsert_analyst_snapshot
from app.db.models import AnalystSnapshot, Base
from tests.indicators.test_ichimoku_lookahead import _make_candles

N = 220
TRUNCATION_POINTS = [80, 120, 160, N - 1]


def test_truncation_cards_identical_at_as_of():
    candles = _make_candles(N, seed=41)
    full = build_analyst_cards_from_candles(
        candles,
        symbol="BTCUSDT",
        timeframe="1h",
        as_of=candles[TRUNCATION_POINTS[0] - 1].time,
        now=candles[-1].time + 3600,
    )
    assert full

    for t in TRUNCATION_POINTS:
        as_of = candles[t - 1].time
        from_full = build_analyst_cards_from_candles(
            candles,
            symbol="BTCUSDT",
            timeframe="1h",
            as_of=as_of,
            now=candles[-1].time + 3600,
        )
        from_trunc = build_analyst_cards_from_candles(
            candles[:t],
            symbol="BTCUSDT",
            timeframe="1h",
            as_of=as_of,
            now=as_of + 3600,
        )
        assert len(from_full) == len(from_trunc)
        for a, b in zip(from_full, from_trunc, strict=True):
            assert a["feature"] == b["feature"]
            assert a["as_of"] == b["as_of"] == as_of
            assert a["state"] == b["state"]
            assert a["value"] == b["value"]
            assert a["text"] == b["text"]
            assert a["used_by_decision"] is False


def test_decision_role_matches_rs01_table():
    """Table RS-01 — rôles paper documentés (observe-only sur les fiches)."""
    expected = {
        "ichimoku": "D+S",
        "mtf_direction": "W",
        "rvol": "F",
        "atr": "F+T+S",
        "adx": "F",
        "donchian": "F",
        "structure": "I",
        "fvg": "aucun",
        "impulse": "aucun",
        "location": "F",
        "oi_funding": "aucun",
        "cvd": "aucun",
        "liquidity": "aucun",
        "confluence": "aucun",
        "cycle": "aucun",
    }
    assert DECISION_ROLE_BY_FEATURE == expected

    candles = _make_candles(120, seed=7)
    cards = build_analyst_cards_from_candles(
        candles,
        symbol="BTCUSDT",
        timeframe="1h",
        now=candles[-1].time + 3600,
    )
    by_feat = {c["feature"]: c for c in cards}
    for feat, role in expected.items():
        if feat in ("liquidity", "confluence"):
            continue  # absents tant que CI-LIQ-CONF n'est pas mergé
        assert feat in by_feat
        assert by_feat[feat]["decision_role"] == role
        assert by_feat[feat]["used_by_decision"] is False
        assert by_feat[feat]["validation_status"] == "NON_VALIDE"
        assert by_feat[feat]["stage"] == STAGE_BY_FEATURE[feat]


def test_stage_table_frozen():
    """Table figée feature → stage (AG-S1 / préparation AG-S3, non codé)."""
    expected = {
        "ichimoku": "DIR",
        "mtf_direction": "DIR",
        "rvol": "PART",
        "cvd": "PART",
        "oi_funding": "PART",
        "structure": "STRUCT",
        "fvg": "STRUCT",
        "impulse": "STRUCT",
        "liquidity": "STRUCT",
        "location": "LOC",
        "confluence": "LOC",
        "atr": "REGIME",
        "adx": "REGIME",
        "donchian": "REGIME",
        "cycle": "REGIME",
    }
    assert STAGE_BY_FEATURE == expected
    assert STAGES == ("DIR", "PART", "STRUCT", "LOC", "REGIME")
    for feat, stage in expected.items():
        assert stage_for_feature(feat) == stage

    candles = _make_candles(120, seed=11)
    cards = build_analyst_cards_from_candles(
        candles,
        symbol="BTCUSDT",
        timeframe="1h",
        now=candles[-1].time + 3600,
    )
    for c in cards:
        assert c["stage"] in STAGES
        assert c["stage"] == STAGE_BY_FEATURE[c["feature"]]

    only_dir = build_analyst_cards_from_candles(
        candles,
        symbol="BTCUSDT",
        timeframe="1h",
        now=candles[-1].time + 3600,
        stage="DIR",
    )
    assert only_dir
    assert all(c["stage"] == "DIR" for c in only_dir)
    assert {c["feature"] for c in only_dir} <= {"ichimoku", "mtf_direction"}


def test_snapshot_idempotent_two_triggers_one_row(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    # Redirect SessionLocal used by upsert.
    import app.agents.analyst_snapshot as snap_mod
    import app.db.session as db_session

    monkeypatch.setattr(db_session, "SessionLocal", Session)
    monkeypatch.setattr(snap_mod, "SessionLocal", Session)

    cards = [{"feature": "ichimoku", "state": "LONG", "used_by_decision": False}]
    row1, created1 = upsert_analyst_snapshot(
        session_id="asia:2026-03-10",
        symbol="BTCUSDT",
        timeframe="1h",
        as_of=1_700_000_000,
        cards=cards,
    )
    row2, created2 = upsert_analyst_snapshot(
        session_id="asia:2026-03-10",
        symbol="BTCUSDT",
        timeframe="1h",
        as_of=1_700_000_999,
        cards=[{"feature": "ichimoku", "state": "SHORT"}],
    )
    assert created1 is True
    assert created2 is False
    assert row1["id"] == row2["id"]
    assert row2["as_of"] == 1_700_000_000  # first write wins

    with Session() as db:
        n = len(db.execute(select(AnalystSnapshot)).scalars().all())
    assert n == 1


def _forbidden_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name == "app.paper" or name.startswith("app.paper."):
                    bad.append(name)
                if name == "app.screener" or name.startswith("app.screener."):
                    bad.append(name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mod = node.module
            if mod == "app.paper" or mod.startswith("app.paper."):
                bad.append(mod)
            if mod == "app.screener" or mod.startswith("app.screener."):
                bad.append(mod)
            if mod == "app" and any(
                a.name in {"paper", "screener"} for a in node.names
            ):
                bad.append(f"app.{next(a.name for a in node.names)}")
    return bad


def test_no_paper_or_screener_imports_in_ags_modules():
    root = Path(__file__).resolve().parents[2] / "app"
    targets = [
        root / "agents" / "analyst_cards.py",
        root / "agents" / "analyst_snapshot.py",
        root / "sessions" / "calendar.py",
        root / "sessions" / "__init__.py",
        root / "api" / "sessions.py",
        root / "api" / "analyst_agents.py",
    ]
    for path in targets:
        assert path.is_file(), path
        bad = _forbidden_imports(path)
        assert bad == [], f"{path.name} imports forbidden modules: {bad}"


def test_no_screener_string_call_in_analyst_cards():
    src = (
        Path(__file__).resolve().parents[2] / "app" / "agents" / "analyst_cards.py"
    ).read_text(encoding="utf-8")
    assert "/screener" not in src
    assert "scan_symbol" not in src
