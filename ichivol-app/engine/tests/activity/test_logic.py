from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.activity.logic import (
    MIN_TRADES_PER_PAIR,
    SnapshotLite,
    cluster_runs,
    humanize_journal_event,
    summarize_run,
)
from app.backtest.evidence import seconds_until_due

T0 = datetime(2026, 9, 20, 9, 0, tzinfo=timezone.utc)


def _row(minutes: float, symbol="BTCUSDT", experiment="PIPELINE", trades=6, sharpe=1.0, pf=2.0):
    return SnapshotLite(
        computed_at=T0 + timedelta(minutes=minutes),
        symbol=symbol,
        timeframe="1h",
        experiment=experiment,
        num_trades=trades,
        sharpe=sharpe,
        profit_factor=pf,
        expectancy=0.001,
        win_rate=0.4,
    )


def test_rows_close_in_time_form_one_run_and_a_long_gap_starts_another():
    rows = [_row(0), _row(3), _row(9), _row(24 * 60), _row(24 * 60 + 5)]
    runs = cluster_runs(rows)
    assert [len(r) for r in runs] == [3, 2]


def test_cluster_runs_sorts_input_first():
    runs = cluster_runs([_row(24 * 60), _row(0), _row(2)])
    assert [len(r) for r in runs] == [2, 1]
    assert runs[0][0].computed_at < runs[1][0].computed_at


def test_small_samples_are_flagged_and_infinite_pf_is_ignored():
    run = [
        _row(0, "BTCUSDT", "PIPELINE", trades=6, pf=float("inf")),
        _row(1, "ETHUSDT", "PIPELINE", trades=8, pf=3.0),
        _row(2, "BTCUSDT", "ICHIMOKU_RVOL", trades=64, pf=1.2),
    ]
    summary = summarize_run(run)
    assert summary["experiments"]["PIPELINE"]["small_sample"] is True
    assert summary["experiments"]["PIPELINE"]["profit_factor_median"] == 3.0
    assert summary["experiments"]["ICHIMOKU_RVOL"]["small_sample"] is False
    assert summary["n_pairs"] == 2
    assert MIN_TRADES_PER_PAIR == 30


def test_pipeline_vs_ichimoku_counts_pairs_where_pipeline_wins_on_sharpe():
    run = [
        _row(0, "BTCUSDT", "PIPELINE", sharpe=2.0),
        _row(0, "BTCUSDT", "ICHIMOKU_ONLY", sharpe=1.0),
        _row(1, "ETHUSDT", "PIPELINE", sharpe=0.5),
        _row(1, "ETHUSDT", "ICHIMOKU_ONLY", sharpe=1.5),
        _row(2, "SOLUSDT", "PIPELINE", sharpe=None),
        _row(2, "SOLUSDT", "ICHIMOKU_ONLY", sharpe=1.0),
    ]
    assert summarize_run(run)["pipeline_vs_ichimoku"] == {"beats": 1, "compared": 2}


def test_opened_event_is_readable():
    item = humanize_journal_event(
        "OPENED",
        {"symbol": "DOGEUSDT", "direction": "LONG", "entry": 0.0909, "stop": 0.0894,
         "take_profit": 0.0939, "risk_pct": 0.01},
        symbol="DOGEUSDT",
        direction="LONG",
    )
    assert item["kind"] == "paper_opened"
    assert item["title"] == "Achat automatique DOGEUSDT"
    assert "risque 1 %" in item["detail"]


def test_closed_event_uses_the_position_symbol_and_translates_the_reason():
    item = humanize_journal_event(
        "CLOSED",
        {"reason": "pipeline_downgraded", "pnl_pct": -0.0062},
        symbol="ADAUSDT",
        direction="LONG",
    )
    assert item["symbol"] == "ADAUSDT"
    assert item["tone"] == "bad"
    assert "repassé en attente" in item["detail"]
    assert "-0.62 %" in item["detail"]


def test_blocked_and_shadow_close_explain_what_the_filter_did():
    blocked = humanize_journal_event(
        "SHADOW_BLOCKED",
        {"symbol": "PEPEUSDT", "block_source": "context", "reason": "rsi_overbought_block_long"},
        symbol=None,
        direction=None,
    )
    assert blocked["detail"] == "filtre contexte : RSI en surachat, achat refusé"

    lost = humanize_journal_event(
        "SHADOW_CLOSE",
        {"symbol": "XRPUSDT", "exit_reason": "stop_hit", "pnl_r": -1.02},
        symbol=None,
        direction=None,
    )
    assert "aurait perdu" in lost["detail"]
    assert lost["tone"] == "good"  # the refused trade would have lost: the filter helped

    won = humanize_journal_event(
        "SHADOW_CLOSE",
        {"symbol": "XRPUSDT", "exit_reason": "take_profit_hit", "pnl_r": 2.0},
        symbol=None,
        direction=None,
    )
    assert won["tone"] == "bad"  # a winner was refused: the filter cost us


def test_shadow_open_is_skipped_because_blocked_already_says_it():
    assert humanize_journal_event("SHADOW_OPEN", {}, symbol="X", direction=None) is None


def test_scheduler_waits_out_the_interval_instead_of_rerunning_on_every_restart():
    now = T0
    assert seconds_until_due(None, 86400, now) == 0.0
    assert seconds_until_due(now - timedelta(hours=2), 86400, now) == 86400 - 7200
    assert seconds_until_due(now - timedelta(days=3), 86400, now) == 0.0
