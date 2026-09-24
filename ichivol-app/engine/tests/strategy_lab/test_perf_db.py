"""Performance DB tests — skip if Postgres unreachable."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.db.models import StrategyLabExperiment
from app.db.session import SessionLocal, engine
from app.indicators.ichimoku import Candle
from app.strategy_lab.catalog import get_builtin_ruleset
from app.strategy_lab.perf_db import (
    ENGINE_VERSION,
    experiment_dict,
    list_experiments,
    save_experiment,
)
from app.strategy_lab.run_ruleset import study_ruleset_on_candles

try:
    with engine.connect():
        pass
    DB_AVAILABLE = True
except OperationalError:
    DB_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not DB_AVAILABLE, reason="ichivol_engine_dev Postgres not reachable"
)

SYMBOL = "PERFDBTEST"


def _cleanup(session):
    session.query(StrategyLabExperiment).filter(
        StrategyLabExperiment.symbol == SYMBOL
    ).delete(synchronize_session=False)
    session.commit()


@pytest.fixture(autouse=True)
def _session():
    session = SessionLocal()
    try:
        _cleanup(session)
    except ProgrammingError:
        session.rollback()
        pytest.skip("strategy_lab_experiments table missing — run alembic upgrade")
    yield session
    try:
        _cleanup(session)
    except ProgrammingError:
        session.rollback()
    session.close()


def _candles(n: int = 100) -> list[Candle]:
    out = []
    for i in range(n):
        base = 100 + i * 0.3
        out.append(
            Candle(
                time=1_700_000_000 + i * 3600,
                open=base,
                high=base + 2,
                low=base - 1,
                close=base + 1,
                volume=100 + (200 if i % 17 == 0 else 0),
            )
        )
    return out


def test_save_and_list_experiment(_session):
    rs = get_builtin_ruleset("IV_ICHIMOKU_ONLY_LONG_001")
    study = study_ruleset_on_candles(
        _candles(), rs, symbol=SYMBOL, timeframe="1h", with_backtest=True
    )
    row = save_experiment(
        _session, study, parameters={"limit": 100, "source": "test"}
    )
    assert row.id
    assert row.ruleset_id == rs.id
    assert row.engine_version == ENGINE_VERSION
    assert row.symbol == SYMBOL

    rows = list_experiments(_session, symbol=SYMBOL, ruleset_id=rs.id, limit=10)
    assert len(rows) >= 1
    payload = experiment_dict(rows[0])
    assert payload["experiment_id"] == row.id
    assert "event_study" in payload
    assert payload["stop_rule"].endswith("*ATR")
    assert "complexity" in payload
    assert payload["complexity"]["score"] >= 1
    assert payload["hypothesis_id"] is None
