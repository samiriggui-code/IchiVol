"""T10b — hypothesis lineage counter + display-only complexity."""

from __future__ import annotations

import pytest

from app.strategy_lab.perf_db import ruleset_complexity


def test_ruleset_complexity_flat_entry_only():
    cx = ruleset_complexity(
        {
            "id": "X",
            "conditions": {"tk_cross_bullish": True, "rvol_min": 1.5},
            "stop_atr": 1.0,
            "target_atr": 2.0,
        }
    )
    assert cx["entry_leaves"] == 2
    assert cx["exit_leaves"] == 0
    assert cx["exit_extras"] == 0
    assert cx["score"] == 2
    assert "no auto-reject" in cx["note"]


def test_ruleset_complexity_all_any_and_exit_extras():
    cx = ruleset_complexity(
        {
            "conditions": {
                "all": {"price_above_kumo": True, "rvol_min": 2.0},
                "any": {"bos_bullish": True, "tk_cross_bullish": True},
            },
            "exit": {
                "max_hold_bars": 48,
                "conditions": {"tk_cross_bearish": True},
                "trail": {"breakeven_at_r": 1.0},
                "partial_tp": [
                    {"r_multiple": 1.0, "fraction": 0.5},
                    {"r_multiple": 2.0, "fraction": 0.5},
                ],
                "reinforce": {
                    "conditions": {"rvol_min": 3.0},
                    "add_fraction": 0.5,
                    "max_adds": 1,
                },
            },
        }
    )
    # entry: 2 all + 2 any = 4
    # exit leaves: 1 signal + 1 reinforce = 2
    # extras: max_hold + trail + 2 partial + reinforce flag = 5
    assert cx["entry_leaves"] == 4
    assert cx["exit_leaves"] == 2
    assert cx["exit_extras"] == 5
    assert cx["score"] == 11


def test_ruleset_complexity_empty():
    assert ruleset_complexity(None)["score"] == 0
    assert ruleset_complexity({})["score"] == 0


def _db_ready() -> bool:
    try:
        from sqlalchemy.exc import OperationalError, ProgrammingError

        from app.db.session import engine

        with engine.connect():
            pass
        return True
    except Exception:
        # Local Cursor DSN may reject "schema=" ; CI Postgres is the truth.
        return False


def test_hypothesis_lineage_count_and_complexity_payload():
    if not _db_ready():
        pytest.skip("ichivol_engine_dev Postgres not reachable")

    from sqlalchemy.exc import ProgrammingError

    from app.db.models import StrategyLabExperiment
    from app.db.session import SessionLocal
    from app.indicators.ichimoku import Candle
    from app.strategy_lab.catalog import get_builtin_ruleset
    from app.strategy_lab.perf_db import (
        experiment_dict,
        lineage_count_for,
        list_experiments,
        save_experiment,
    )
    from app.strategy_lab.run_ruleset import study_ruleset_on_candles

    session = SessionLocal()
    symbol = "T10BTEST"
    try:
        try:
            session.query(StrategyLabExperiment).filter(
                StrategyLabExperiment.symbol == symbol
            ).delete(synchronize_session=False)
            session.commit()
        except ProgrammingError:
            session.rollback()
            pytest.skip("strategy_lab_experiments missing — run alembic upgrade")

        rs = get_builtin_ruleset("IV_ICHIMOKU_ONLY_LONG_001")
        candles = []
        for i in range(80):
            base = 100 + i * 0.3
            candles.append(
                Candle(
                    time=1_700_000_000 + i * 3600,
                    open=base,
                    high=base + 2,
                    low=base - 1,
                    close=base + 1,
                    volume=100,
                )
            )
        study = study_ruleset_on_candles(
            candles, rs, symbol=symbol, timeframe="1h", with_backtest=True
        )

        row1 = save_experiment(
            session,
            study,
            parameters={"source": "t10b"},
            hypothesis_id="h_t10b_demo",
        )
        row2 = save_experiment(
            session,
            study,
            parameters={"source": "t10b", "hypothesis_id": "h_t10b_demo"},
        )
        assert row1.hypothesis_id == "h_t10b_demo"
        assert row2.hypothesis_id == "h_t10b_demo"
        assert lineage_count_for(session, row1) == 2
        assert lineage_count_for(session, row2) == 2

        payload = experiment_dict(row1, lineage_count=lineage_count_for(session, row1))
        assert payload["hypothesis_id"] == "h_t10b_demo"
        assert payload["lineage_count"] == 2
        assert payload["complexity"]["score"] >= 1
        assert "no auto-reject" in payload["complexity"]["note"]

        # Untagged row: fallback counts all trials for ruleset+symbol+tf
        # (tagged + untagged) — total essais on that ruleset window.
        row3 = save_experiment(session, study, parameters={"source": "t10b-null"})
        assert row3.hypothesis_id is None
        assert lineage_count_for(session, row3) == 3

        listed = list_experiments(session, symbol=symbol, hypothesis_id="h_t10b_demo")
        assert len(listed) == 2
    finally:
        try:
            session.query(StrategyLabExperiment).filter(
                StrategyLabExperiment.symbol == symbol
            ).delete(synchronize_session=False)
            session.commit()
        except ProgrammingError:
            session.rollback()
        session.close()
