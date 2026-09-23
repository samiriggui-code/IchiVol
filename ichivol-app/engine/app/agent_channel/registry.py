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
    cmd_delete_chart_object,
    cmd_detect_signal,
    cmd_draw_channel,
    cmd_draw_entry,
    cmd_draw_horizontal_line,
    cmd_draw_marker,
    cmd_draw_ray,
    cmd_draw_rectangle,
    cmd_draw_stop,
    cmd_draw_target,
    cmd_draw_text,
    cmd_draw_trend_line,
    cmd_draw_zone,
    cmd_get_calendar,
    cmd_get_chart_objects,
    cmd_get_correlations,
    cmd_get_event_context,
    cmd_get_family_weights,
    cmd_list_family_weight_profiles,
    cmd_compare_family_weights,
    cmd_run_family_weights_study,
    cmd_filter_backtest_overlay,
    cmd_get_news,
    cmd_get_structure,
    cmd_get_symbol_context,
    cmd_list_tools,
    cmd_list_rulesets,
    cmd_list_strategy_lab_experiments,
    cmd_run_ablation,
    cmd_run_backtest,
    cmd_run_event_study,
    cmd_run_anomaly_regime_study,
    cmd_calibrate_anomaly_thresholds,
    cmd_run_regime_slices,
    cmd_run_ruleset_event_study,
    cmd_run_walk_forward,
    cmd_run_walk_forward_opt,
    cmd_run_optimize,
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
            "run_event_study",
            "Event Study Strategy Lab Phase 1 (payload identique à GET /event-study/{symbol}).",
            True,
            {
                "symbol": "str, requis",
                "timeframe": "str, défaut '1h'",
                "limit": "int, défaut 1000",
                "variant": "str, défaut 'PIPELINE'",
                "horizons": "list[int] ou CSV, défaut [1,3,5,10]",
                "r_multiple": "float, défaut 1.0",
                "include_events": "bool, défaut false",
            },
            cmd_run_event_study,
        ),
        ToolSpec(
            "run_anomaly_regime_study",
            "Event Study PIPELINE stratifié NORMAL vs UNKNOWN_EVENT (Event Intelligence PHASE 6) — mesure empirique, ne vote jamais.",
            True,
            {
                "symbol": "str, requis",
                "timeframe": "str, défaut '1h'",
                "limit": "int, défaut 1000",
                "horizons": "list[int] ou CSV, défaut [1,3,5,10]",
                "r_multiple": "float, défaut 1.0",
                "min_signals": "int, défaut 5",
            },
            cmd_run_anomaly_regime_study,
        ),
        ToolSpec(
            "calibrate_anomaly_thresholds",
            "Suggère des seuils d'anomalie (p99 causal) sans les appliquer — Event Intelligence PHASE 6.",
            True,
            {
                "symbol": "str, requis",
                "timeframe": "str, défaut '1h'",
                "limit": "int, défaut 1000",
            },
            cmd_calibrate_anomaly_thresholds,
        ),
        ToolSpec(
            "list_rulesets",
            "Liste les rulesets built-in Strategy Lab Phase 2.",
            True,
            {},
            cmd_list_rulesets,
        ),
        ToolSpec(
            "run_ruleset_event_study",
            "Évalue un ruleset (id ou JSON) puis Event Study + backtest (POST /ruleset/event-study).",
            True,
            {
                "symbol": "str, requis",
                "ruleset_id": "str, built-in si pas de ruleset",
                "ruleset": "object, optionnel — JSON inline",
                "timeframe": "str, défaut '1h'",
                "limit": "int, défaut 1000",
                "horizons": "list[int] ou CSV",
                "include_events": "bool, défaut false",
                "with_backtest": "bool, défaut true",
                "persist": "bool, défaut false — sauve dans Performance DB",
            },
            cmd_run_ruleset_event_study,
        ),
        ToolSpec(
            "list_strategy_lab_experiments",
            "Liste les expériences Strategy Lab persistées (Performance DB).",
            True,
            {
                "symbol": "str, optionnel",
                "timeframe": "str, optionnel",
                "ruleset_id": "str, optionnel",
                "limit": "int, défaut 50",
            },
            cmd_list_strategy_lab_experiments,
        ),
        ToolSpec(
            "run_ablation",
            "Ablation Strategy Lab Phase 5 (escalier A→E ou leave-one-out) sur une fenêtre OHLCV.",
            True,
            {
                "symbol": "str, requis",
                "timeframe": "str, défaut '1h'",
                "limit": "int, défaut 1000",
                "mode": "'cumulative' | 'leave_one_out'",
                "direction": "LONG|SHORT",
                "persist": "bool, défaut false",
                "layers": "list[{label,conditions}], optionnel",
            },
            cmd_run_ablation,
        ),
        ToolSpec(
            "run_regime_slices",
            "Découpe perf ruleset par régime (TRENDING/RANGING/VOL/BULL…) — Phase 6.",
            True,
            {
                "symbol": "str, requis",
                "ruleset_id": "str, optionnel",
                "ruleset": "object, optionnel",
                "timeframe": "str, défaut '1h'",
                "limit": "int, défaut 1000",
                "persist": "bool, défaut false",
            },
            cmd_run_regime_slices,
        ),
        ToolSpec(
            "run_walk_forward",
            "Walk-forward IS/OOS sur ruleset fixe (rolling|expanding) — Phase 7, pas d'optimizer.",
            True,
            {
                "symbol": "str, requis",
                "ruleset_id": "str, optionnel",
                "ruleset": "object, optionnel",
                "timeframe": "str, défaut '1h'",
                "limit": "int, défaut 1000",
                "mode": "'rolling' | 'expanding'",
                "train_bars": "int, défaut 400",
                "test_bars": "int, défaut 100",
                "step_bars": "int, optionnel (=test_bars)",
                "warmup_bars": "int, défaut 52",
                "include_train": "bool, défaut true",
                "persist": "bool, défaut false",
            },
            cmd_run_walk_forward,
        ),
        ToolSpec(
            "run_optimize",
            "Grid-search params sur une fenêtre (IS only) — Phase 8; préférer walk-forward-opt.",
            True,
            {
                "symbol": "str, requis",
                "ruleset_id": "str, optionnel",
                "ruleset": "object, optionnel",
                "grid": "object {param: [values]}, optionnel",
                "objective": "'expectancy'|'profit_factor'|'sharpe'",
                "min_trades": "int, défaut 5",
                "timeframe": "str, défaut '1h'",
                "limit": "int, défaut 1000",
                "persist_best": "bool, défaut false",
            },
            cmd_run_optimize,
        ),
        ToolSpec(
            "run_walk_forward_opt",
            "Walk-forward + grid-search IS → mesure OOS (anti-overfit) — Phase 8.",
            True,
            {
                "symbol": "str, requis",
                "ruleset_id": "str, optionnel",
                "ruleset": "object, optionnel",
                "grid": "object {param: [values]}, optionnel",
                "objective": "'expectancy'|'profit_factor'|'sharpe'",
                "min_trades": "int, défaut 5",
                "mode": "'rolling' | 'expanding'",
                "train_bars": "int, défaut 400",
                "test_bars": "int, défaut 100",
                "timeframe": "str, défaut '1h'",
                "limit": "int, défaut 1000",
                "persist": "bool, défaut false",
            },
            cmd_run_walk_forward_opt,
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
            "get_event_context",
            "Event Intelligence PHASE 7 — anomalie + news/calendrier causals (EVENT≠SIGNAL). Pour Claude explainer.",
            True,
            {
                "symbol": "str, requis",
                "timeframe": "str, défaut '1h'",
                "limit": "int, défaut 300",
                "include_news": "bool, défaut true",
                "include_macro": "bool, défaut true",
            },
            cmd_get_event_context,
        ),
        ToolSpec(
            "get_family_weights",
            "T5a — observation poids familles (direction/participation/structure/location/regime). Ne change pas decision/confidence.",
            True,
            {
                "symbol": "str, requis",
                "timeframe": "str, défaut '1h'",
                "limit": "int, défaut 300",
            },
            cmd_get_family_weights,
        ),
        ToolSpec(
            "list_family_weight_profiles",
            "T5b — catalogue des profils de poids familles (observation / Lab only).",
            True,
            {},
            cmd_list_family_weight_profiles,
        ),
        ToolSpec(
            "compare_family_weights",
            "T5b — compare tous les profils de poids sur le pipeline live (observation).",
            True,
            {
                "symbol": "str, requis",
                "timeframe": "str, défaut '1h'",
                "limit": "int, défaut 300",
            },
            cmd_compare_family_weights,
        ),
        ToolSpec(
            "run_family_weights_study",
            "T5b — étude historique weighted_support × forward returns par profil (observation, pas de fills).",
            True,
            {
                "symbol": "str, requis",
                "timeframe": "str, défaut '1h'",
                "limit": "int, défaut 500",
                "step": "int, défaut 1",
                "sample_limit": "int, défaut 20",
            },
            cmd_run_family_weights_study,
        ),
        ToolSpec(
            "filter_backtest_overlay",
            "T4b — overlay backtest filtré (outcome/exit_reason/direction/why_entered_key) pour Claude. Read-only.",
            True,
            {
                "symbol": "str, requis",
                "ruleset_id": "str, built-in si pas de ruleset",
                "ruleset": "object, optionnel — DSL inline",
                "timeframe": "str, défaut '1h'",
                "limit": "int, défaut 300",
                "outcome": "all|win|loss, défaut all",
                "exit_reason": "stop|target|signal|eod|max_hold, optionnel",
                "direction": "LONG|SHORT, optionnel",
                "why_entered_key": "str, feuille WHY passée à l'entrée, optionnel",
                "regime_label": "TRENDING|RANGING|HIGH_VOLATILITY|…, optionnel (T4d)",
                "include_rejected": "bool, défaut true",
            },
            cmd_filter_backtest_overlay,
        ),
        ToolSpec(
            "list_tools", "Liste ce même registre (identique à GET /agent/tools).", True, {}, cmd_list_tools,
        ),
        ToolSpec(
            "get_structure",
            "Market Structure (zones/trendlines/breakouts) — payload identique à GET /structure/{symbol}.",
            True,
            {
                "symbol": "str, requis",
                "timeframe": "str, défaut '1h'",
                "limit": "int, défaut 300",
                "include_pytrendline": "bool, défaut false",
            },
            cmd_get_structure,
        ),
        ToolSpec(
            "get_chart_objects",
            "Overlays ChartObject (ENGINE + USER/CLAUDE persistés) — payload GET /chart-objects/{symbol}.",
            True,
            {
                "symbol": "str, requis",
                "timeframe": "str, défaut '1h'",
                "limit": "int, défaut 300",
                "sources": "str CSV ou list, défaut 'engine' (passer user,claude pour le store)",
                "include_pytrendline": "bool, défaut false",
            },
            cmd_get_chart_objects,
        ),
        ToolSpec(
            "draw_horizontal_line",
            "Persiste une ligne horizontale (source claude|user) sur le chart.",
            False,
            {
                "symbol": "str, requis",
                "timeframe": "str, défaut '1h'",
                "price": "float, ou points=[{time,price}]",
                "time": "int unix, avec price",
                "as_of": "int unix, optionnel",
                "source": "str, ignoré — agent force claude",
                "label": "str, optionnel",
                "side": "str, optionnel",
            },
            cmd_draw_horizontal_line,
        ),
        ToolSpec(
            "draw_trend_line",
            "Persiste une trendline (2 points time/price).",
            False,
            {
                "symbol": "str, requis",
                "timeframe": "str, défaut '1h'",
                "points": "list[{time,price}], requis (2)",
                "as_of": "int, optionnel",
                "source": "str, ignoré — agent force claude",
                "label": "str, optionnel",
                "side": "str, optionnel",
            },
            cmd_draw_trend_line,
        ),
        ToolSpec(
            "draw_ray",
            "Persiste un rayon (2 points).",
            False,
            {
                "symbol": "str, requis",
                "timeframe": "str, défaut '1h'",
                "points": "list[{time,price}], requis (2)",
                "as_of": "int, optionnel",
                "source": "str, ignoré — agent force claude",
            },
            cmd_draw_ray,
        ),
        ToolSpec(
            "draw_zone",
            "Persiste une zone prix (price_low < price_high).",
            False,
            {
                "symbol": "str, requis",
                "timeframe": "str, défaut '1h'",
                "price_low": "float, requis",
                "price_high": "float, requis",
                "as_of": "int, requis si points vides",
                "points": "list[{time,price}], optionnel (0 ou 2)",
                "source": "str, ignoré — agent force claude",
                "side": "str, optionnel",
                "label": "str, optionnel",
            },
            cmd_draw_zone,
        ),
        ToolSpec(
            "draw_rectangle",
            "Persiste un rectangle (2 points + price_low/high).",
            False,
            {
                "symbol": "str, requis",
                "timeframe": "str, défaut '1h'",
                "points": "list[{time,price}], requis (2)",
                "price_low": "float, requis",
                "price_high": "float, requis",
                "source": "str, ignoré — agent force claude",
            },
            cmd_draw_rectangle,
        ),
        ToolSpec(
            "draw_channel",
            "Persiste un canal (4 points = deux segments).",
            False,
            {
                "symbol": "str, requis",
                "timeframe": "str, défaut '1h'",
                "points": "list[{time,price}], requis (4)",
                "source": "str, ignoré — agent force claude",
            },
            cmd_draw_channel,
        ),
        ToolSpec(
            "draw_marker",
            "Persiste un marqueur (1 point).",
            False,
            {
                "symbol": "str, requis",
                "timeframe": "str, défaut '1h'",
                "price": "float, ou points",
                "time": "int unix, avec price",
                "as_of": "int, optionnel",
                "source": "str, ignoré — agent force claude",
                "label": "str, optionnel",
            },
            cmd_draw_marker,
        ),
        ToolSpec(
            "draw_text",
            "Persiste une annotation texte (1 point + label).",
            False,
            {
                "symbol": "str, requis",
                "timeframe": "str, défaut '1h'",
                "label": "str, requis",
                "price": "float, ou points",
                "time": "int unix, avec price",
                "source": "str, ignoré — agent force claude",
            },
            cmd_draw_text,
        ),
        ToolSpec(
            "draw_entry",
            "Persiste un marqueur d'entrée (1 point).",
            False,
            {
                "symbol": "str, requis",
                "timeframe": "str, défaut '1h'",
                "price": "float, ou points",
                "time": "int unix, avec price",
                "source": "str, ignoré — agent force claude",
                "side": "str, optionnel LONG|SHORT",
            },
            cmd_draw_entry,
        ),
        ToolSpec(
            "draw_stop",
            "Persiste un niveau de stop (1 point).",
            False,
            {
                "symbol": "str, requis",
                "timeframe": "str, défaut '1h'",
                "price": "float, ou points",
                "time": "int unix, avec price",
                "source": "str, ignoré — agent force claude",
            },
            cmd_draw_stop,
        ),
        ToolSpec(
            "draw_target",
            "Persiste un niveau de target (1 point).",
            False,
            {
                "symbol": "str, requis",
                "timeframe": "str, défaut '1h'",
                "price": "float, ou points",
                "time": "int unix, avec price",
                "source": "str, ignoré — agent force claude",
            },
            cmd_draw_target,
        ),
        ToolSpec(
            "delete_chart_object",
            "Soft-delete un overlay USER/CLAUDE par id déterministe.",
            False,
            {
                "id": "str, requis — ChartObject.id (source=claude only)",
            },
            cmd_delete_chart_object,
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
