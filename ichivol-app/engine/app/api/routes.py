"""HTTP surface for the engine, mounted under `settings.engine_api_prefix`
(default `/api/engine`).

T1g: domain routers are composed here in the **original route order** so
path-precedence (e.g. `/backtest/evidence` before `/backtest/{symbol}`) is
unchanged. Endpoint bodies were moved, not rewritten.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api import agent as agent_routes
from app.api import backtest as backtest_routes
from app.api import backtest_overlay as backtest_overlay_routes
from app.api import chart_objects as chart_objects_routes
from app.api import context as context_routes
from app.api import cycle as cycle_routes
from app.api import decisions as decisions_routes
from app.api import market as market_routes
from app.api import paper as paper_routes
from app.api import paper_orders as paper_orders_routes
from app.api import rulesets as rulesets_routes
from app.api import strategy_lab as strategy_lab_routes
from app.api import strategy_lab_research as strategy_lab_research_routes
from app.api import strategy_lab_wf as strategy_lab_wf_routes
from app.api.common import _line_dict, _zone_dict  # noqa: F401 — re-export for tests
from app.correlation.engine import compute_correlation_matrix  # noqa: F401 — monkeypatch target
from app.screener.service import scan_symbol  # noqa: F401 — monkeypatch target

router = APIRouter()

# Original order of routes formerly defined in this module (see T1g golden).
# T2a: chart_objects appended at the end of engine routes (before /health on main).
# T4a: backtest-overlay after strategy-lab (additions only in route_order golden).
# T-CYCLE: cycle observe-only after correlations (additive; never touches pipeline).
for _sub in (
    market_routes.router_head,
    context_routes.router,
    market_routes.router_screener,
    decisions_routes.router,
    backtest_routes.router_evidence,
    rulesets_routes.router,
    strategy_lab_routes.router,
    backtest_overlay_routes.router,
    strategy_lab_wf_routes.router,
    # UI Lab Research — T5b/T6/T7/Researcher HTTP (observation only; additive).
    strategy_lab_research_routes.router,
    backtest_routes.router_symbol,
    market_routes.router_correlations,
    cycle_routes.router,
    paper_routes.router_before_shadow,
    backtest_routes.router_shadow,
    paper_orders_routes.router_after_shadow,
    agent_routes.router,
    chart_objects_routes.router,
):
    router.include_router(_sub)
