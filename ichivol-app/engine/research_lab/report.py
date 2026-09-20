import json, statistics
from research_lab.build import build
from research_lab.metrics import summarize
from research_lab.run import WINDOWS, subset
from research_lab.sim import ADVERSE_COST, BASE_COST, simulate
from research_lab.universe import A_UNIVERSE
from research_lab.variants import RULES_A, RULES_B, RULES_C, RULES_E, with_breakout_persistence
from datetime import datetime, timezone

data = build(); dA = subset(data, A_UNIVERSE); dC = with_breakout_persistence(dA)
setups = {"A": (RULES_A, dA), "B": (RULES_B, data), "C": (RULES_C, dC), "E": (RULES_E, dA)}
d = lambda s: datetime.fromtimestamp(s, timezone.utc).strftime("%Y-%m-%d")
rows = []
for w in ("DEV", "V1", "V2", "V3", "VAL"):
    for k, (rules, dd) in setups.items():
        rb = simulate(dd, rules, BASE_COST, WINDOWS[w]); ra = simulate(dd, rules, ADVERSE_COST, WINDOWS[w])
        sb, sa = summarize(rb), summarize(ra)
        wins = sorted((t.net for t in rb.trades if t.net > 0), reverse=True)
        top3_of_wins = sum(wins[:3]) / sum(wins) if wins else None
        top5pct = sum(wins[: max(1, int(0.05 * len(rb.trades)))]) / sum(wins) if wins else None
        nets = sorted((t.net for t in rb.trades), reverse=True)
        rows.append({
            "window": w, "period": f"{d(WINDOWS[w][0])}..{d(WINDOWS[w][1])}", "id": k, "trades": sb["trades"], "signals": sb["signals_seen"],
            "gross": sb["gross_raw"], "commission": sb["commission"], "spread_slip": sb["spread_slippage_in_fills"], "net": sb["net_realized"],
            "ret_pct": sb["return_pct"], "exp": sb["expectancy_net"], "wr": sb["win_rate"], "avg_win": sb["avg_win"], "avg_loss": sb["avg_loss"],
            "dd": sb["max_drawdown_pct"], "expo_mean": sb["exposure_mean_pct"], "expo_max": sb["exposure_max_pct"], "hold_h": sb["avg_hold_h"],
            "turnover": sb["turnover_x_per_month"], "top3_share_of_wins": round(top3_of_wins, 2) if top3_of_wins else None,
            "top5pct_share_of_wins": round(top5pct, 2) if top5pct else None,
            "net_wo_top3": round(sum(nets[3:]), 2), "adverse_net": sa["net_realized"], "adverse_dd": sa["max_drawdown_pct"],
            "exits": sb["exit_reasons"], "rej": sb["rejections"], "longs": sb["longs"], "shorts": sb["shorts"],
        })
json.dump(rows, open("research_lab/results_report.json", "w"), indent=1)
for r in rows:
    print(r["window"], r["id"], "n", r["trades"], "gross", r["gross"], "fees", round(r["commission"] + r["spread_slip"], 0), "net", r["net"], "dd", r["dd"], "expo", r["expo_mean"], r["expo_max"], "hold", r["hold_h"], "exp", r["exp"], "wr", r["wr"], "top3w", r["top3_share_of_wins"], "adv", r["adverse_net"])
