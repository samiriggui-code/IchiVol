"""T12e — ADN IchiVol matrix A→F (Lab observation only).

Layers (rév.58):
  A Ichimoku · B +RVOL · C Structure+RVOL (parallèle) · D Ichi+Struct+RVOL
  · E D+Location · F E+Régime
+ IchiVol catalogue actuel + références T12c

Paramètres = snapshot « screener live » (défauts alignés ``resolve.ts`` /
``RvolParams``) — **pas** les seul defaults hardcodés 1.5 de l'ablation
historique (réserve Claude T12b).

Aucun changement live (decision / screener / paper / brokerage).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

from app.agents.types import Direction
from app.indicators.atr import AtrParams
from app.indicators.ichimoku import Candle, IchimokuParams
from app.indicators.rvol import RvolParams
from app.strategy_lab.ablation import ABLATION_LADDERS, build_cumulative_rulesets
from app.strategy_lab.ablation_oos import (
    AblationOosReport,
    run_ablation_oos_study_on_candles,
)
from app.strategy_lab.catalog import get_builtin_ruleset
from app.strategy_lab.reference_baselines import (
    ReferenceBaselinesReport,
    run_reference_baselines_on_candles,
)
from app.strategy_lab.ruleset import Ruleset, parse_ruleset
from app.strategy_lab.run_ruleset import study_ruleset_on_candles
from app.strategy_lab.walk_forward import (
    WalkForwardReport,
    run_walk_forward_on_candles,
    walk_forward_dict,
)

Verdict = Literal["KEEP", "RESEARCH", "REJECT"]

# Alignés sur server/src/settings/resolve.ts DEFAULT_VOLUME + DEFAULT_ICHIMOKU
# et app/indicators/rvol.RvolParams / atr.AtrParams.
DEFAULT_LIVE_RVOL_SIGNIFICANT = 1.5
DEFAULT_LIVE_RVOL_LOW = 0.7
DEFAULT_LIVE_RVOL_STRONG = 2.0
DEFAULT_LIVE_RVOL_ANOMALY = 3.0
DEFAULT_LIVE_RVOL_LEN = 20
DEFAULT_LIVE_ATR_DEAD = 0.15
DEFAULT_LIVE_ATR_EXTREME = 0.90
DEFAULT_LIVE_ATR_STOP_MULT = 1.5

ICHIVOL_CURRENT_ID = "IV_ICHIMOKU_RVOL_LONG_001"
ADN_BASE_ID = "IV_ADN_T12E"
ADN_LADDER_NAME = "adn_ichivol"

_DISCLAIMER = (
    "T12e ADN IchiVol — observation Lab only; no live gate / FeatureStatus change. "
    "KEEP = T9g-fix review_candidate (not a promotion — Claude + user, T10e)."
)


@dataclass(frozen=True)
class LiveScreenerSettings:
    """Frozen snapshot of screener thresholds used by T12e studies.

    **DÉCISION CURSOR — à relire par Claude** : hors DB user settings, on gèle
    les défauts production (``resolve.ts``). Un appelant peut injecter un
    snapshot réel (API settings) via ``from_mapping``.
    """

    rvol_len: int = DEFAULT_LIVE_RVOL_LEN
    rvol_low: float = DEFAULT_LIVE_RVOL_LOW
    rvol_significant: float = DEFAULT_LIVE_RVOL_SIGNIFICANT
    rvol_strong: float = DEFAULT_LIVE_RVOL_STRONG
    rvol_anomaly: float = DEFAULT_LIVE_RVOL_ANOMALY
    atr_dead_percentile: float = DEFAULT_LIVE_ATR_DEAD
    atr_extreme_percentile: float = DEFAULT_LIVE_ATR_EXTREME
    atr_stop_multiplier: float = DEFAULT_LIVE_ATR_STOP_MULT
    ichi_tenkan: int = 9
    ichi_kijun: int = 26
    ichi_senkou_b: int = 52
    ichi_displacement: int = 26
    source: str = "production_defaults"

    def to_dict(self) -> dict[str, Any]:
        return {
            "rvol_len": self.rvol_len,
            "rvol_low": self.rvol_low,
            "rvol_significant": self.rvol_significant,
            "rvol_strong": self.rvol_strong,
            "rvol_anomaly": self.rvol_anomaly,
            "atr_dead_percentile": self.atr_dead_percentile,
            "atr_extreme_percentile": self.atr_extreme_percentile,
            "atr_stop_multiplier": self.atr_stop_multiplier,
            "ichi_tenkan": self.ichi_tenkan,
            "ichi_kijun": self.ichi_kijun,
            "ichi_senkou_b": self.ichi_senkou_b,
            "ichi_displacement": self.ichi_displacement,
            "source": self.source,
        }

    def rvol_params(self) -> RvolParams:
        return RvolParams(
            primary_window=self.rvol_len,
            low_threshold=self.rvol_low,
            significant_threshold=self.rvol_significant,
            strong_threshold=self.rvol_strong,
            anomaly_threshold=self.rvol_anomaly,
        )

    def atr_params(self) -> AtrParams:
        return AtrParams(
            dead_percentile=self.atr_dead_percentile,
            extreme_percentile=self.atr_extreme_percentile,
            stop_multiplier=self.atr_stop_multiplier,
        )

    def ichi_params(self) -> IchimokuParams:
        return IchimokuParams(
            tenkan=self.ichi_tenkan,
            kijun=self.ichi_kijun,
            senkou_b=self.ichi_senkou_b,
            displacement=self.ichi_displacement,
        )

    @classmethod
    def production_defaults(cls) -> LiveScreenerSettings:
        return cls()

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any], *, source: str = "injected") -> LiveScreenerSettings:
        """Map UI/settings keys (camel or snake) → snapshot."""
        def _f(*keys: str, default: float) -> float:
            for k in keys:
                if k in raw and raw[k] is not None:
                    return float(raw[k])
            return float(default)

        def _i(*keys: str, default: int) -> int:
            for k in keys:
                if k in raw and raw[k] is not None:
                    return int(raw[k])
            return int(default)

        return cls(
            rvol_len=_i("rvol_len", "rvolLen", default=DEFAULT_LIVE_RVOL_LEN),
            rvol_low=_f("rvol_low", "rvolLow", default=DEFAULT_LIVE_RVOL_LOW),
            rvol_significant=_f(
                "rvol_significant", "rvolSignificant", "rvolConfirm",
                default=DEFAULT_LIVE_RVOL_SIGNIFICANT,
            ),
            rvol_strong=_f("rvol_strong", "rvolStrong", default=DEFAULT_LIVE_RVOL_STRONG),
            rvol_anomaly=_f(
                "rvol_anomaly", "rvolAnomaly", default=DEFAULT_LIVE_RVOL_ANOMALY
            ),
            atr_dead_percentile=_f(
                "atr_dead_percentile", "atrDeadPercentile", default=DEFAULT_LIVE_ATR_DEAD
            ),
            atr_extreme_percentile=_f(
                "atr_extreme_percentile",
                "atrExtremePercentile",
                default=DEFAULT_LIVE_ATR_EXTREME,
            ),
            atr_stop_multiplier=_f(
                "atr_stop_multiplier",
                "atrStopMultiplier",
                default=DEFAULT_LIVE_ATR_STOP_MULT,
            ),
            ichi_tenkan=_i("ichi_tenkan", "tenkan", default=9),
            ichi_kijun=_i("ichi_kijun", "kijun", default=26),
            ichi_senkou_b=_i("ichi_senkou_b", "senkouB", default=52),
            ichi_displacement=_i("ichi_displacement", "displacement", default=26),
            source=source,
        )


def _ichi_conditions() -> dict[str, bool | int | float | str]:
    return {
        "price_above_kumo": True,
        "tenkan_above_kijun": True,
        "tk_cross_age_max": 3,
    }


def adn_cumulative_delta_layers(
    settings: LiveScreenerSettings | None = None,
) -> tuple[tuple[str, dict[str, bool | int | float | str]], ...]:
    """A→B→D→E→F as cumulative deltas for ``run_ablation_oos_study`` additive mode.

    C (Structure+RVOL alone) is **not** on this ladder — see ``adn_model_c_ruleset``.
    """
    s = settings or LiveScreenerSettings.production_defaults()
    rvol_min = float(s.rvol_significant)
    return (
        ("A_ICHIMOKU", _ichi_conditions()),
        ("B_RVOL", {"rvol_min": rvol_min}),
        ("D_STRUCTURE", {"bos_bullish": True}),
        ("E_LOCATION", {"location_stage_pass": "pass"}),
        ("F_REGIME", {"regime_stage_pass": "pass"}),
    )


def adn_model_c_conditions(
    settings: LiveScreenerSettings | None = None,
) -> dict[str, bool | int | float | str]:
    """C = Structure + RVOL (parallèle, sans Ichimoku)."""
    s = settings or LiveScreenerSettings.production_defaults()
    return {"bos_bullish": True, "rvol_min": float(s.rvol_significant)}


def adn_model_c_ruleset(
    settings: LiveScreenerSettings | None = None,
    *,
    stop_atr: float = 1.0,
    target_atr: float = 2.0,
) -> Ruleset:
    return parse_ruleset(
        {
            "id": f"{ADN_BASE_ID}__C_STRUCT_RVOL",
            "version": "1",
            "direction": "LONG",
            "description": "T12e ADN C — Structure+RVOL (parallèle)",
            "conditions": adn_model_c_conditions(settings),
            "entry": "next_open",
            "stop_atr": stop_atr,
            "target_atr": target_atr,
            "meta": {"t12e": True, "adn_layer": "C", "ablation_mode": "parallel"},
        }
    )


def adn_absolute_models(
    settings: LiveScreenerSettings | None = None,
    *,
    stop_atr: float = 1.0,
    target_atr: float = 2.0,
) -> dict[str, Ruleset]:
    """Named absolute models A–F (+ catalogue courant) for the study matrix."""
    s = settings or LiveScreenerSettings.production_defaults()
    cum = build_cumulative_rulesets(
        adn_cumulative_delta_layers(s),
        base_id=ADN_BASE_ID,
        direction=Direction.LONG,
        stop_atr=stop_atr,
        target_atr=target_atr,
    )
    # Labels on cum: A, B, D, E, F
    by_label = {rs.meta.get("ablation_label"): rs for rs in cum}
    out: dict[str, Ruleset] = {
        "A": by_label["A_ICHIMOKU"],
        "B": by_label["B_RVOL"],
        "C": adn_model_c_ruleset(s, stop_atr=stop_atr, target_atr=target_atr),
        "D": by_label["D_STRUCTURE"],
        "E": by_label["E_LOCATION"],
        "F": by_label["F_REGIME"],
        "ICHIVOL_CURRENT": get_builtin_ruleset(ICHIVOL_CURRENT_ID),
    }
    return out


def map_t9g_to_verdict(recommendation: str) -> Verdict:
    if recommendation == "review_candidate":
        return "KEEP"
    if recommendation == "inconclusive":
        return "RESEARCH"
    if recommendation == "reject":
        return "REJECT"
    return "RESEARCH"


@dataclass(frozen=True)
class AdnLayerRow:
    model: str
    symbol: str
    timeframe: str
    n_bars: int
    recommendation: str | None
    verdict: Verdict
    oos_expectancy_delta: float | None = None
    adverse_oos_expectancy_delta: float | None = None
    oos_trades: int | None = None
    n_folds: int | None = None
    lineage_trial_count: int | None = None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "n_bars": self.n_bars,
            "recommendation": self.recommendation,
            "verdict": self.verdict,
            "oos_expectancy_delta": self.oos_expectancy_delta,
            "adverse_oos_expectancy_delta": self.adverse_oos_expectancy_delta,
            "oos_trades": self.oos_trades,
            "n_folds": self.n_folds,
            "lineage_trial_count": self.lineage_trial_count,
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class AdnMatrixReport:
    settings: LiveScreenerSettings
    symbol: str
    timeframe: str
    n_bars: int
    ablation_oos: AblationOosReport | None
    model_c_wf: WalkForwardReport | None
    model_c_verdict: Verdict
    references: ReferenceBaselinesReport | None
    rows: tuple[AdnLayerRow, ...]
    coverage_note: str | None = None
    disclaimer: str = _DISCLAIMER
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "settings": self.settings.to_dict(),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "n_bars": self.n_bars,
            "ablation_oos": self.ablation_oos.to_dict() if self.ablation_oos else None,
            "model_c_wf": walk_forward_dict(self.model_c_wf) if self.model_c_wf else None,
            "model_c_verdict": self.model_c_verdict,
            "references": self.references.to_dict() if self.references else None,
            "rows": [r.to_dict() for r in self.rows],
            "coverage_note": self.coverage_note,
            "disclaimer": self.disclaimer,
            "notes": list(self.notes),
        }


def _verdict_from_wf(wf: WalkForwardReport, *, min_oos_trades: int) -> Verdict:
    """Standalone model (C) — no baseline delta; use OOS trade count + expectancy sign."""
    summary = wf.oos_summary or {}
    trades = int(summary.get("total_oos_trades") or 0)
    exp = summary.get("mean_oos_expectancy")
    if trades < min_oos_trades or exp is None:
        return "RESEARCH"
    if float(exp) > 0:
        return "KEEP"
    return "REJECT"


def run_adn_matrix_on_candles(
    candles: Sequence[Candle],
    *,
    symbol: str,
    timeframe: str,
    settings: LiveScreenerSettings | None = None,
    train_bars: int = 100,
    test_bars: int = 40,
    step_bars: int | None = None,
    warmup_bars: int = 52,
    min_oos_trades: int = 30,
    stop_atr: float = 1.0,
    target_atr: float = 2.0,
    hypothesis_id: str | None = None,
    coverage_note: str | None = None,
    with_references: bool = True,
) -> AdnMatrixReport:
    """Run ADN A→F ablation OOS + parallel C + T12c refs on one series."""
    s = settings or LiveScreenerSettings.production_defaults()
    layers = adn_cumulative_delta_layers(s)
    hid = hypothesis_id or f"t12e_adn_{symbol}_{timeframe}"

    ablation = run_ablation_oos_study_on_candles(
        candles,
        symbol=symbol,
        timeframe=timeframe,
        compare_mode="additive",
        layers=layers,
        direction=Direction.LONG,
        stop_atr=stop_atr,
        target_atr=target_atr,
        train_bars=train_bars,
        test_bars=test_bars,
        step_bars=step_bars,
        warmup_bars=warmup_bars,
        min_oos_trades=min_oos_trades,
        hypothesis_id=hid,
    )

    c_rs = adn_model_c_ruleset(s, stop_atr=stop_atr, target_atr=target_atr)
    c_wf = run_walk_forward_on_candles(
        candles,
        c_rs,
        symbol=symbol,
        timeframe=timeframe,
        mode="rolling",
        train_bars=train_bars,
        test_bars=test_bars,
        step_bars=step_bars if step_bars is not None else test_bars,
        warmup_bars=warmup_bars,
    )
    c_verdict = _verdict_from_wf(c_wf, min_oos_trades=min_oos_trades)

    refs: ReferenceBaselinesReport | None = None
    if with_references:
        refs = run_reference_baselines_on_candles(
            candles,
            symbol=symbol,
            timeframe=timeframe,
            stop_atr=stop_atr,
            target_atr=target_atr,
        )

    rows: list[AdnLayerRow] = []
    # Model A = baseline of first ablation step — no additive candidate; score via study trades
    a_rs = adn_absolute_models(s, stop_atr=stop_atr, target_atr=target_atr)["A"]
    a_study = study_ruleset_on_candles(
        candles,
        a_rs,
        symbol=symbol,
        timeframe=timeframe,
        with_backtest=True,
    )
    a_exp = None
    a_trades = None
    if a_study.backtest is not None:
        a_exp = a_study.backtest.metrics.expectancy
        a_trades = int(a_study.backtest.metrics.num_trades)
    rows.append(
        AdnLayerRow(
            model="A",
            symbol=symbol,
            timeframe=timeframe,
            n_bars=len(candles),
            recommendation=None,
            verdict="RESEARCH" if (a_trades or 0) < min_oos_trades else (
                "KEEP" if (a_exp or 0) > 0 else "REJECT"
            ),
            oos_expectancy_delta=None,
            oos_trades=a_trades,
            notes=("baseline ADN (Ichimoku seul) — verdict IS backtest, pas delta OOS",),
        )
    )

    label_to_model = {
        "B_RVOL": "B",
        "D_STRUCTURE": "D",
        "E_LOCATION": "E",
        "F_REGIME": "F",
    }
    for cand in ablation.candidates:
        model = label_to_model.get(cand.label, cand.label)
        rows.append(
            AdnLayerRow(
                model=model,
                symbol=symbol,
                timeframe=timeframe,
                n_bars=len(candles),
                recommendation=cand.recommendation,
                verdict=map_t9g_to_verdict(cand.recommendation),
                oos_expectancy_delta=cand.oos_expectancy_delta,
                adverse_oos_expectancy_delta=cand.adverse_oos_expectancy_delta,
                oos_trades=min(
                    cand.oos_total_trades_baseline, cand.oos_total_trades_variant
                ),
                n_folds=cand.n_folds,
                lineage_trial_count=ablation.lineage_trial_count,
                notes=tuple(cand.reasons),
            )
        )

    rows.append(
        AdnLayerRow(
            model="C",
            symbol=symbol,
            timeframe=timeframe,
            n_bars=len(candles),
            recommendation=None,
            verdict=c_verdict,
            oos_trades=int(c_wf.oos_summary.get("total_oos_trades") or 0),
            n_folds=int(c_wf.oos_summary.get("n_folds") or len(c_wf.folds)),
            notes=("parallèle Structure+RVOL — WF OOS expectancy sign",),
        )
    )

    notes = (
        "Ladder cumulative A→B→D→E→F ; C parallèle hors ladder.",
        f"rvol_min = settings.rvol_significant={s.rvol_significant} (source={s.source}).",
        "Verdict KEEP = review_candidate T9g-fix ; pas de promotion auto.",
    )

    return AdnMatrixReport(
        settings=s,
        symbol=symbol,
        timeframe=timeframe,
        n_bars=len(candles),
        ablation_oos=ablation,
        model_c_wf=c_wf,
        model_c_verdict=c_verdict,
        references=refs,
        rows=tuple(rows),
        coverage_note=coverage_note,
        notes=notes,
    )


# Register ladder for HTTP / agent callers that pass ladder="adn_ichivol"
ABLATION_LADDERS[ADN_LADDER_NAME] = adn_cumulative_delta_layers()
