"""VP3 Rules: B1–B8 use VP2 common; B0 = hold until window end."""

from __future__ import annotations

from research_lab.sim import Rules

from vp2.rules import common_rules


def strategy_rules(strategy: str, interval: str) -> Rules:
    if strategy == "B0":
        base = common_rules(interval, name="vp3_B0")
        return Rules(
            name=base.name,
            risk_pct=base.risk_pct,
            take_profit_r=base.take_profit_r,
            max_open=base.max_open,
            max_notional_pct=base.max_notional_pct,
            max_symbol_notional_pct=base.max_symbol_notional_pct,
            max_open_risk_pct=base.max_open_risk_pct,
            daily_loss_limit_pct=0.0,
            one_entry_per_signal_run=True,
            allow_short=False,
            liquidity_cap_pct=base.liquidity_cap_pct,
            min_notional=base.min_notional,
            exit_mode="hold",
            immediate_fill=False,
            bar_seconds=base.bar_seconds,
            time_stop_bars=None,
            full_cash=True,
            force_flat_at_end=True,
        )
    if strategy in ("B1", "B2", "B5", "B6", "B7"):
        return common_rules(interval, name=f"vp3_{strategy}")
    raise ValueError(f"unknown strategy: {strategy}")
