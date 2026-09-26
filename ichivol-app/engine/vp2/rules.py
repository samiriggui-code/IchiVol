"""Frozen §6 / §1ter Rules factory for VP2."""

from __future__ import annotations

from research_lab.sim import Rules

from vp2 import BAR_SECONDS, TIME_STOP_BARS


def common_rules(interval: str, *, name: str = "vp2_common") -> Rules:
    """Common execution for B1–B8: long-only, levels_only exit, full cash, 1 position.

    Portfolio risk/notional/daily-halt caps are neutralized so §6 sizing applies.
    """
    if interval not in BAR_SECONDS:
        raise ValueError(f"unsupported interval for VP2: {interval}")
    if interval not in TIME_STOP_BARS:
        raise ValueError(f"no time-stop defined for interval: {interval}")
    return Rules(
        name=name,
        risk_pct=1.0,  # unused when full_cash=True
        take_profit_r=2.0,
        max_open=1,
        max_notional_pct=1.0,
        max_symbol_notional_pct=1.0,
        max_open_risk_pct=10.0,  # neutralized
        daily_loss_limit_pct=0.0,  # neutralized
        one_entry_per_signal_run=True,
        allow_short=False,
        liquidity_cap_pct=1.0,  # neutralized (VP size << bar quote volume)
        min_notional=10.0,
        exit_mode="levels_only",
        immediate_fill=False,
        bar_seconds=BAR_SECONDS[interval],
        time_stop_bars=TIME_STOP_BARS[interval],
        full_cash=True,
        force_flat_at_end=True,
    )
