from __future__ import annotations
import statistics
from collections import Counter


def max_drawdown(curve):
    peak, mdd = None, 0.0
    for _, eq, _ in curve:
        peak = eq if peak is None or eq > peak else peak
        mdd = min(mdd, eq / peak - 1.0)
    return mdd


def summarize(res) -> dict:
    tr = res.trades
    n = len(tr)
    net = sum(t.net for t in tr)
    gross = sum(t.gross for t in tr)
    comm = sum(t.commission for t in tr)
    fric = sum(t.friction_cost for t in tr)
    fin = sum(t.financing for t in tr)
    wins = [t.net for t in tr if t.net > 0]
    losses = [t.net for t in tr if t.net <= 0]
    nets = sorted((t.net for t in tr), reverse=True)
    unreal = sum(o["unrealized"] for o in res.open_at_end)
    eq_end = res.equity[-1][1] if res.equity else res.initial
    exp = [g / e if e > 0 else 0 for _, e, g in res.equity]
    hold_h = [(t.exit_time - t.entry_time) / 3600 for t in tr]
    traded = sum(t.notional for t in tr)
    avg_eq = statistics.mean(e for _, e, _ in res.equity) if res.equity else res.initial
    span_days = max(1e-9, (res.window[1] - res.window[0]) / 86400)
    top1 = nets[0] if nets else 0.0
    top3 = sum(nets[:3])
    return {
        "variant": res.rules.name, "cost": res.cost.name, "n_symbols": len(res.symbols),
        "window": [res.window[0], res.window[1]],
        "trades": n, "signals_seen": res.signals_seen,
        "gross_raw": round(gross, 2), "commission": round(comm, 2), "spread_slippage_in_fills": round(fric, 2),
        "financing": round(fin, 2), "net_realized": round(net, 2),
        "net_check_gross_minus_costs": round(gross - comm - fric - fin, 2),
        "unrealized_open_at_end": round(unreal, 2), "equity_end": round(eq_end, 2),
        "return_pct": round((eq_end / res.initial - 1) * 100, 2),
        "expectancy_net": round(net / n, 3) if n else None,
        "win_rate": round(len(wins) / n, 3) if n else None,
        "avg_win": round(statistics.mean(wins), 2) if wins else None,
        "avg_loss": round(statistics.mean(losses), 2) if losses else None,
        "profit_factor": round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) else None,
        "max_drawdown_pct": round(max_drawdown(res.equity) * 100, 2),
        "exposure_mean_pct": round(statistics.mean(exp) * 100, 1) if exp else 0,
        "exposure_max_pct": round(max(exp) * 100, 1) if exp else 0,
        "avg_hold_h": round(statistics.mean(hold_h), 2) if hold_h else None,
        "turnover_x_per_month": round(traded / avg_eq / (span_days / 30), 2),
        "top1_share_of_net": round(top1 / net, 2) if net > 0 else None,
        "top3_share_of_net": round(top3 / net, 2) if net > 0 else None,
        "net_without_top1": round(net - top1, 2) if n else None,
        "net_without_top3": round(net - top3, 2) if n else None,
        "exit_reasons": dict(Counter(t.exit_reason for t in tr)),
        "longs": sum(1 for t in tr if t.direction == "LONG"), "shorts": sum(1 for t in tr if t.direction == "SHORT"),
        "rejections": dict(res.rejections), "open_positions_at_end": len(res.open_at_end),
        "ledger_reconcile_diff": res.ledger_diff,
    }
