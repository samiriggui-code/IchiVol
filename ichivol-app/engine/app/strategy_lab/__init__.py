"""Strategy Lab — research layer on top of Grand V2.

Phase 1–5: Event Study, Rules, Backtest, Perf DB, Ablation
Phase 6: Market Regime slices
Phase 7: Walk-forward (fixed ruleset IS/OOS)
Phase 8: Optimization (grid-search IS → OOS via walk-forward-opt)
"""

from app.strategy_lab.ablation import AblationResult, run_ablation
from app.strategy_lab.event_study import EventStudyResult, run_event_study
from app.strategy_lab.optimization import (
    OptimizeReport,
    WalkForwardOptReport,
    run_optimize,
    run_walk_forward_opt,
)
from app.strategy_lab.perf_db import (
    ENGINE_VERSION,
    experiment_dict,
    list_experiments,
    persist_study_result,
    ruleset_complexity,
)
from app.strategy_lab.redundancy import (
    FeatureRedundancyReport,
    run_feature_redundancy_study,
)
from app.strategy_lab.regime_slices import RegimeSliceReport, run_regime_slices
from app.strategy_lab.ruleset import Ruleset, parse_ruleset
from app.strategy_lab.ruleset_backtest import RulesetBacktestResult, run_ruleset_backtest
from app.strategy_lab.run_ruleset import RulesetStudyResult, run_ruleset_event_study
from app.strategy_lab.walk_forward import WalkForwardReport, run_walk_forward

__all__ = [
    "AblationResult",
    "ENGINE_VERSION",
    "EventStudyResult",
    "FeatureRedundancyReport",
    "OptimizeReport",
    "RegimeSliceReport",
    "Ruleset",
    "RulesetBacktestResult",
    "RulesetStudyResult",
    "WalkForwardOptReport",
    "WalkForwardReport",
    "experiment_dict",
    "list_experiments",
    "parse_ruleset",
    "persist_study_result",
    "ruleset_complexity",
    "run_ablation",
    "run_event_study",
    "run_feature_redundancy_study",
    "run_optimize",
    "run_regime_slices",
    "run_ruleset_backtest",
    "run_ruleset_event_study",
    "run_walk_forward",
    "run_walk_forward_opt",
]
