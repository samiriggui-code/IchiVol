"""AG-S1 — fiches analystes : anti-lookahead, RS-01, imports, idempotence."""

from __future__ import annotations

import ast
import random
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
from app.indicators.ichimoku import Candle
from app.market_data.timeframes import TF_SECONDS
from tests.indicators.test_ichimoku_lookahead import _make_candles

N = 220
TRUNCATION_POINTS = [80, 120, 160, N - 1]

# Epoch aligned to a 4h / 1d boundary (2023-11-14 00:00 UTC).
_TF_START = 1_700_000_000


def _make_tf_candles(n: int, tf: str, seed: int = 42) -> list[Candle]:
    """OHLCV with real TF spacing (seconds), for MTF close-time tests."""
    step = TF_SECONDS[tf]
    rng = random.Random(seed)
    price = 100.0
    candles: list[Candle] = []
    for i in range(n):
        drift = rng.uniform(-1.5, 1.5)
        open_ = price
        close = max(1.0, price + drift)
        high = max(open_, close) + rng.uniform(0, 1.0)
        low = min(open_, close) - rng.uniform(0, 1.0)
        volume = rng.uniform(10, 1000)
        candles.append(
            Candle(
                time=_TF_START + i * step,
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=volume,
            )
        )
        price = close
    return candles


def _aggregate_htf(ltf: list[Candle], ltf_tf: str, htf_tf: str) -> list[Candle]:
    """Aggregate LTF bars into HTF OHLCV (aligned opens)."""
    ltf_dur = TF_SECONDS[ltf_tf]
    htf_dur = TF_SECONDS[htf_tf]
    assert htf_dur % ltf_dur == 0
    ratio = htf_dur // ltf_dur
    out: list[Candle] = []
    for i in range(0, len(ltf) - ratio + 1, ratio):
        chunk = ltf[i : i + ratio]
        if len(chunk) < ratio:
            break
        out.append(
            Candle(
                time=chunk[0].time,
                open=chunk[0].open,
                high=max(c.high for c in chunk),
                low=min(c.low for c in chunk),
                close=chunk[-1].close,
                volume=sum(c.volume for c in chunk),
            )
        )
    return out


def _assert_cards_identical(from_full: list[dict], from_trunc: list[dict], as_of: int) -> None:
    assert len(from_full) == len(from_trunc)
    for a, b in zip(from_full, from_trunc, strict=True):
        assert a["feature"] == b["feature"]
        assert a["as_of"] == b["as_of"] == as_of
        assert a["state"] == b["state"]
        assert a["value"] == b["value"]
        assert a["text"] == b["text"]
        assert a["known_at"] == b["known_at"]
        assert a["used_by_decision"] is False


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
        _assert_cards_identical(from_full, from_trunc, as_of)


def test_truncation_cards_identical_at_as_of_1h_to_4h():
    """1h → 4h MTF : troncature au milieu d'une bougie 4h (anti-lookahead)."""
    h1 = _make_tf_candles(N, "1h", seed=41)
    h4 = _aggregate_htf(h1, "1h", "4h")
    assert len(h4) >= 40

    # Points de troncature au milieu d'une 4h : index 1h = 4k+2 (ex. 13:00 dans 12–16).
    mid_htf_points = [82, 122, 162]  # 80+2, 120+2, 160+2 → open mid-4h
    for t in mid_htf_points:
        as_of = h1[t - 1].time
        # Sanity : as_of tombe au milieu d'une 4h (offset 1h or 2h into the bucket).
        assert (as_of - _TF_START) % TF_SECONDS["4h"] in {
            TF_SECONDS["1h"],
            2 * TF_SECONDS["1h"],
            3 * TF_SECONDS["1h"],
        }
        from_full = build_analyst_cards_from_candles(
            h1,
            symbol="BTCUSDT",
            timeframe="1h",
            as_of=as_of,
            now=h1[-1].time + TF_SECONDS["1h"],
            htf_candles=h4,
        )
        from_trunc = build_analyst_cards_from_candles(
            h1[:t],
            symbol="BTCUSDT",
            timeframe="1h",
            as_of=as_of,
            now=as_of + TF_SECONDS["1h"],
            htf_candles=h4,
        )
        _assert_cards_identical(from_full, from_trunc, as_of)
        mtf = next(c for c in from_full if c["feature"] == "mtf_direction")
        # Forming 4h (open <= as_of but not closed) must be excluded.
        forming_open = as_of - ((as_of - _TF_START) % TF_SECONDS["4h"])
        if mtf["state"] != "UNKNOWN":
            assert mtf["value"]["htf_as_of"] < forming_open
            assert mtf["known_at"] == mtf["value"]["htf_as_of"] + TF_SECONDS["4h"]
            assert mtf["known_at"] <= as_of + TF_SECONDS["1h"]
        else:
            assert mtf["value"].get("htf_as_of") != forming_open


def test_truncation_cards_identical_at_as_of_4h_to_1d():
    """4h → 1d MTF : troncature au milieu d'une bougie 1d."""
    h4 = _make_tf_candles(N, "4h", seed=43)
    d1 = _aggregate_htf(h4, "4h", "1d")
    assert len(d1) >= 20

    # Mid-day 4h bars: index within day = 2 or 3 (08:00 / 12:00 UTC).
    mid_day_points = [50, 98, 146]  # 48+2, 96+2, 144+2
    for t in mid_day_points:
        as_of = h4[t - 1].time
        offset_in_day = (as_of - _TF_START) % TF_SECONDS["1d"]
        assert offset_in_day in {
            TF_SECONDS["4h"],
            2 * TF_SECONDS["4h"],
            3 * TF_SECONDS["4h"],
            4 * TF_SECONDS["4h"],
            5 * TF_SECONDS["4h"],
        }
        from_full = build_analyst_cards_from_candles(
            h4,
            symbol="BTCUSDT",
            timeframe="4h",
            as_of=as_of,
            now=h4[-1].time + TF_SECONDS["4h"],
            htf_candles=d1,
        )
        from_trunc = build_analyst_cards_from_candles(
            h4[:t],
            symbol="BTCUSDT",
            timeframe="4h",
            as_of=as_of,
            now=as_of + TF_SECONDS["4h"],
            htf_candles=d1,
        )
        _assert_cards_identical(from_full, from_trunc, as_of)
        mtf = next(c for c in from_full if c["feature"] == "mtf_direction")
        forming_open = as_of - ((as_of - _TF_START) % TF_SECONDS["1d"])
        if mtf["state"] != "UNKNOWN":
            assert mtf["value"]["htf_as_of"] < forming_open
            assert mtf["known_at"] == mtf["value"]["htf_as_of"] + TF_SECONDS["1d"]


def test_mtf_excludes_forming_4h_at_1300():
    """À 13:00 (bougie 1h), la fiche MTF ne voit pas la 4h de 12:00 (encore ouverte)."""
    # Build enough 1h history ending through 14:00 so ichimoku has fuel.
    h1 = _make_tf_candles(200, "1h", seed=55)
    h4 = _aggregate_htf(h1, "1h", "4h")

    # Find a 13:00 bar: open time offset 13h from day start = 13 * 3600.
    as_of = None
    for c in h1:
        if (c.time - _TF_START) % TF_SECONDS["1d"] == 13 * 3600:
            as_of = c.time
            break
    assert as_of is not None

    forming_4h_open = as_of - ((as_of - _TF_START) % TF_SECONDS["4h"])
    assert (forming_4h_open - _TF_START) % TF_SECONDS["1d"] == 12 * 3600
    assert forming_4h_open in {c.time for c in h4}

    cards = build_analyst_cards_from_candles(
        h1,
        symbol="BTCUSDT",
        timeframe="1h",
        as_of=as_of,
        now=as_of + TF_SECONDS["1h"],
        htf_candles=h4,
    )
    mtf = next(c for c in cards if c["feature"] == "mtf_direction")
    # Decision instant = 13:00 + 1h = 14:00 ; 4h 12:00 closes at 16:00 → excluded.
    assert mtf["value"].get("htf_as_of") != forming_4h_open
    if mtf["state"] != "UNKNOWN":
        assert mtf["value"]["htf_as_of"] < forming_4h_open
        assert mtf["known_at"] == mtf["value"]["htf_as_of"] + TF_SECONDS["4h"]
        assert mtf["known_at"] <= as_of + TF_SECONDS["1h"]
        assert mtf["known_at"] == forming_4h_open  # previous 4h (08:00) closes at 12:00


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


def _call_func_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _string_constants_in_call(node: ast.Call) -> list[str]:
    out: list[str] = []
    for arg in list(node.args) + [kw.value for kw in node.keywords]:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            out.append(arg.value)
        elif isinstance(arg, ast.JoinedStr):  # f-string pieces
            for v in arg.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    out.append(v.value)
    return out


def test_no_screener_string_call_in_analyst_cards():
    """AST : aucun appel http / fetch / get avec URL /screener, ni scan_symbol.

    Les docstrings peuvent mentionner « /screener » (interdiction documentée) —
    on ne scanne pas le texte brut du fichier.
    """
    path = (
        Path(__file__).resolve().parents[2] / "app" / "agents" / "analyst_cards.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    httpish = {
        "get",
        "post",
        "put",
        "patch",
        "delete",
        "request",
        "fetch",
        "urlopen",
        "scan_symbol",
    }
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_func_name(node)
        if name == "scan_symbol":
            offenders.append(f"scan_symbol@{node.lineno}")
            continue
        if name in httpish:
            for s in _string_constants_in_call(node):
                if "/screener" in s:
                    offenders.append(f"{name}({s!r})@{node.lineno}")
        else:
            # Any call that passes a /screener URL string (e.g. custom helpers).
            for s in _string_constants_in_call(node):
                if "/screener" in s:
                    offenders.append(f"{name or '?'}({s!r})@{node.lineno}")
    assert offenders == [], f"screener call/URL in analyst_cards: {offenders}"
