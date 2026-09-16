"""Registry + dispatcher for the agent command channel (READ v1). Maps a
command name to its handler, a short description, and whether it's
read-only -- the allowlist itself, not just documentation of one: an
unknown `cmd` is refused before any handler runs (see `dispatch_command`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.agent_channel.commands import (
    CommandError,
    cmd_calculate_ichimoku,
    cmd_calculate_rvol,
    cmd_compare_timeframes,
    cmd_detect_signal,
    cmd_get_calendar,
    cmd_get_correlations,
    cmd_get_news,
    cmd_get_symbol_context,
    cmd_list_tools,
    cmd_run_backtest,
    cmd_scan_market,
)

Handler = Callable[[dict], dict]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    read_only: bool
    args: dict[str, str]
    handler: Handler


TOOLS: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in (
        ToolSpec(
            "scan_market", "Screener multi-actifs (payload identique à GET /screener).", True,
            {"timeframe": "str, défaut '1h'", "force": "bool, défaut false -- ignore le cache"},
            cmd_scan_market,
        ),
        ToolSpec(
            "get_symbol_context",
            "Détail complet d'une décision (payload identique à GET /decisions/{symbol}).", True,
            {
                "symbol": "str, requis",
                "timeframe": "str, défaut '1h'",
                "limit": "int, défaut 300",
                "persist": "bool, défaut false",
            },
            cmd_get_symbol_context,
        ),
        ToolSpec(
            "detect_signal",
            "Verdict pipeline condensé (decision/direction/stages/risk), sans le détail combiner legacy.",
            True,
            {"symbol": "str, requis", "timeframe": "str, défaut '1h'"},
            cmd_detect_signal,
        ),
        ToolSpec(
            "compare_timeframes",
            "Rejoue un symbole sur plusieurs timeframes et renvoie chaque résumé côte à côte.",
            True,
            {"symbol": "str, requis", "timeframes": "list[str], défaut ['15m','1h','4h','1d']"},
            cmd_compare_timeframes,
        ),
        ToolSpec(
            "run_backtest", "Comparatif ICHIMOKU_ONLY/RVOL/PIPELINE (payload identique à GET /backtest/{symbol}).",
            True,
            {
                "symbol": "str, requis", "timeframe": "str, défaut '1h'", "limit": "int, défaut 1000",
                "rvol_low": "float, optionnel", "rvol_significant": "float, optionnel",
                "rvol_strong": "float, optionnel", "rvol_anomaly": "float, optionnel",
                "atr_dead_percentile": "float, optionnel", "atr_extreme_percentile": "float, optionnel",
                "atr_stop_multiplier": "float, optionnel",
            },
            cmd_run_backtest,
        ),
        ToolSpec(
            "get_correlations", "Matrice de corrélations (payload identique à GET /correlations).", True,
            {
                "symbols": "list[str] ou str CSV, optionnel -- défaut watchlist",
                "timeframe": "str, défaut '1h'", "limit": "int, défaut 300",
                "method": "'log_returns' | 'price', défaut 'log_returns'",
            },
            cmd_get_correlations,
        ),
        ToolSpec(
            "calculate_ichimoku", "État Ichimoku brut (tenkan/kijun/cloud/score) -- pas de décision.", True,
            {"symbol": "str, requis", "timeframe": "str, défaut '1h'", "limit": "int, défaut 300"},
            cmd_calculate_ichimoku,
        ),
        ToolSpec(
            "calculate_rvol", "État RVOL brut (rvol/anomaly_level/confirmed) -- pas de décision.", True,
            {"symbol": "str, requis", "timeframe": "str, défaut '1h'", "limit": "int, défaut 300"},
            cmd_calculate_rvol,
        ),
        ToolSpec(
            "get_news",
            "Titres d'actualité crypto (payload identique à GET /context/news) -- contexte seul, ne vote jamais.",
            True,
            {"limit": "int, défaut 20", "sources": "list[str] ou str CSV, optionnel -- défaut tous"},
            cmd_get_news,
        ),
        ToolSpec(
            "get_calendar",
            "Calendrier macro de la semaine (payload identique à GET /context/calendar) -- contexte seul, ne vote jamais.",
            True,
            {"limit": "int, optionnel -- défaut tout"},
            cmd_get_calendar,
        ),
        ToolSpec(
            "list_tools", "Liste ce même registre (identique à GET /agent/tools).", True, {}, cmd_list_tools,
        ),
    )
}


def list_tool_specs() -> list[dict]:
    return [
        {"name": t.name, "description": t.description, "read_only": t.read_only, "args": t.args}
        for t in TOOLS.values()
    ]


def dispatch_command(cmd: str, args: dict | None = None) -> dict:
    """Runs one allowlisted command. Never raises for a client-caused
    failure (unknown command, bad args, CommandError from the handler) --
    always returns a structured `{ok, cmd, data|error}` dict, so
    `POST /agent/batch` can isolate one bad command from the rest exactly
    like `POST /decisions/batch` already isolates one bad symbol."""
    args = args or {}
    spec = TOOLS.get(cmd)
    if spec is None:
        return {"ok": False, "cmd": cmd, "error": f"unknown_command: {cmd!r} not in the v1 allowlist"}
    try:
        data = spec.handler(dict(args))
    except CommandError as exc:
        return {"ok": False, "cmd": cmd, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001 -- one command's crash must not sink a batch/the process
        return {"ok": False, "cmd": cmd, "error": f"internal_error: {exc}"}
    return {"ok": True, "cmd": cmd, "data": data}
