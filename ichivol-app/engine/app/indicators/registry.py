"""IndicatorRegistry — single entry point for deterministic indicator compute.

Wraps existing ``compute_*`` functions without rewriting formulas. Live,
backtest, replay and agent tooling must all go through ``REGISTRY``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, is_dataclass
from enum import Enum
from typing import Any, Callable, Sequence

from app.indicators.adx import AdxParams, compute_adx
from app.indicators.atr import AtrParams, compute_atr
from app.indicators.best_cloud import BestCloudParams, compute_best_cloud
from app.indicators.cmf import CmfParams, compute_cmf
from app.indicators.cvd import CvdParams, compute_cvd
from app.indicators.donchian import DonchianParams, compute_donchian
from app.indicators.ichimoku import Candle, IchimokuParams, compute_ichimoku
from app.indicators.obv import ObvParams, compute_obv
from app.indicators.ppo import PpoParams, compute_ppo
from app.indicators.rsi import RsiParams, compute_rsi
from app.indicators.rvol import RvolParams, compute_rvol
from app.indicators.structure import StructureParams, compute_structure

ComputeFn = Callable[[Sequence[Candle], Any], list[Any]]
WarmupFn = Callable[[Any], int]


class IndicatorCategory(str, Enum):
    TREND = "TREND"
    MOMENTUM = "MOMENTUM"
    VOLUME = "VOLUME"
    VOLATILITY = "VOLATILITY"
    STRUCTURE = "STRUCTURE"
    LEVELS = "LEVELS"
    STATISTICAL = "STATISTICAL"


class Visualization(str, Enum):
    OVERLAY = "OVERLAY"
    PANE = "PANE"
    NONE = "NONE"


class UnknownIndicatorError(KeyError):
    """Raised when an indicator id is not registered."""


class InvalidParamsError(ValueError):
    """Raised when params overrides are unknown or fail validation."""


@dataclass(frozen=True)
class IndicatorDefinition:
    id: str
    name: str
    category: IndicatorCategory
    params_cls: type
    compute_fn: ComputeFn
    warmup_fn: WarmupFn
    primary_output: str
    visualization: Visualization
    description: str = ""
    tags: tuple[str, ...] = ()

    def parameters(self) -> list[dict[str, Any]]:
        """Describe Params dataclass fields (name, type, default)."""
        from dataclasses import MISSING

        out: list[dict[str, Any]] = []
        for f in fields(self.params_cls):
            if f.default is not MISSING:
                default: Any = f.default
            elif f.default_factory is not MISSING:  # type: ignore[comparison-overlap]
                default = f.default_factory()  # type: ignore[misc]
            else:
                default = None
            type_name = f.type if isinstance(f.type, str) else getattr(f.type, "__name__", str(f.type))
            out.append({"name": f.name, "type": type_name, "default": default})
        return out

    def outputs(self) -> list[str]:
        """State field names — discovered by computing on a 1-candle probe."""
        probe = [
            Candle(time=0, open=1.0, high=1.0, low=1.0, close=1.0, volume=1.0),
        ]
        states = self.compute_fn(probe, self.params_cls())
        if not states:
            return []
        return [f.name for f in fields(states[0])]

    def build_params(self, overrides: dict[str, Any] | None = None) -> Any:
        overrides = dict(overrides or {})
        known = {f.name for f in fields(self.params_cls)}
        unknown = sorted(set(overrides) - known)
        if unknown:
            raise InvalidParamsError(
                f"unknown params for {self.id}: {', '.join(unknown)}"
            )
        try:
            return self.params_cls(**overrides)
        except TypeError as exc:
            raise InvalidParamsError(str(exc)) from exc
        except ValueError as exc:
            raise InvalidParamsError(str(exc)) from exc

    def compute(
        self,
        candles: Sequence[Candle],
        params: dict[str, Any] | Any | None = None,
    ) -> list[Any]:
        if params is None:
            built = self.params_cls()
        elif is_dataclass(params) and not isinstance(params, type):
            built = params
        elif isinstance(params, dict):
            built = self.build_params(params)
        else:
            raise InvalidParamsError(
                f"params must be dict, {self.params_cls.__name__}, or None"
            )
        return self.compute_fn(candles, built)

    def warmup(self, params: dict[str, Any] | Any | None = None) -> int:
        if params is None:
            built = self.params_cls()
        elif is_dataclass(params) and not isinstance(params, type):
            built = params
        elif isinstance(params, dict):
            built = self.build_params(params)
        else:
            raise InvalidParamsError(
                f"params must be dict, {self.params_cls.__name__}, or None"
            )
        return int(self.warmup_fn(built))

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "primary_output": self.primary_output,
            "visualization": self.visualization.value,
            "description": self.description,
            "tags": list(self.tags),
            "parameters": self.parameters(),
            "outputs": self.outputs(),
            "warmup_default": self.warmup(),
        }


def serialize_state(state: Any) -> dict[str, Any]:
    """Dataclass state → JSON-friendly dict (enums → .value)."""
    raw = asdict(state) if is_dataclass(state) and not isinstance(state, type) else dict(state)
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if isinstance(value, Enum):
            out[key] = value.value
        else:
            out[key] = value
    return out


class IndicatorRegistry:
    def __init__(self) -> None:
        self._defs: dict[str, IndicatorDefinition] = {}

    def register(self, definition: IndicatorDefinition) -> IndicatorDefinition:
        if definition.id in self._defs:
            raise ValueError(f"duplicate indicator id: {definition.id}")
        self._defs[definition.id] = definition
        return definition

    def get(self, indicator_id: str) -> IndicatorDefinition:
        try:
            return self._defs[indicator_id]
        except KeyError as exc:
            raise UnknownIndicatorError(indicator_id) from exc

    def __contains__(self, indicator_id: object) -> bool:
        return isinstance(indicator_id, str) and indicator_id in self._defs

    def ids(self) -> list[str]:
        return sorted(self._defs)

    def all(self) -> list[IndicatorDefinition]:
        return [self._defs[i] for i in self.ids()]

    def by_category(self, category: IndicatorCategory) -> list[IndicatorDefinition]:
        return [d for d in self.all() if d.category == category]

    def compute(
        self,
        indicator_id: str,
        candles: Sequence[Candle],
        params: dict[str, Any] | Any | None = None,
    ) -> list[Any]:
        return self.get(indicator_id).compute(candles, params)

    def catalog(self) -> list[dict[str, Any]]:
        return [d.describe() for d in self.all()]


def _build_registry() -> IndicatorRegistry:
    reg = IndicatorRegistry()

    reg.register(
        IndicatorDefinition(
            id="ichimoku",
            name="Ichimoku Kinko Hyo",
            category=IndicatorCategory.TREND,
            params_cls=IchimokuParams,
            compute_fn=compute_ichimoku,
            warmup_fn=lambda p: int(p.senkou_b) + int(p.displacement),
            primary_output="price_vs_kumo",
            visualization=Visualization.OVERLAY,
            description="Ichimoku cloud / TK / Chikou-causal structure",
        )
    )
    reg.register(
        IndicatorDefinition(
            id="rvol",
            name="Relative Volume",
            category=IndicatorCategory.VOLUME,
            params_cls=RvolParams,
            compute_fn=compute_rvol,
            warmup_fn=lambda p: int(p.primary_window),
            primary_output="rvol",
            visualization=Visualization.PANE,
            description="Relative volume participation",
        )
    )
    reg.register(
        IndicatorDefinition(
            id="atr",
            name="Average True Range",
            category=IndicatorCategory.VOLATILITY,
            params_cls=AtrParams,
            compute_fn=compute_atr,
            warmup_fn=lambda p: int(p.period),
            primary_output="atr",
            visualization=Visualization.PANE,
            description="ATR volatility + regime",
        )
    )
    reg.register(
        IndicatorDefinition(
            id="adx",
            name="Average Directional Index",
            category=IndicatorCategory.TREND,
            params_cls=AdxParams,
            compute_fn=compute_adx,
            warmup_fn=lambda p: 2 * int(p.period),
            primary_output="adx",
            visualization=Visualization.PANE,
            description="ADX trend strength",
        )
    )
    reg.register(
        IndicatorDefinition(
            id="rsi",
            name="Relative Strength Index",
            category=IndicatorCategory.MOMENTUM,
            params_cls=RsiParams,
            compute_fn=compute_rsi,
            warmup_fn=lambda p: int(p.period) + 1,
            primary_output="rsi",
            visualization=Visualization.PANE,
            description="RSI momentum",
        )
    )
    reg.register(
        IndicatorDefinition(
            id="cmf",
            name="Chaikin Money Flow",
            category=IndicatorCategory.VOLUME,
            params_cls=CmfParams,
            compute_fn=compute_cmf,
            warmup_fn=lambda p: int(p.period),
            primary_output="cmf",
            visualization=Visualization.PANE,
            description="Chaikin Money Flow",
        )
    )
    reg.register(
        IndicatorDefinition(
            id="obv",
            name="On-Balance Volume",
            category=IndicatorCategory.VOLUME,
            params_cls=ObvParams,
            compute_fn=compute_obv,
            warmup_fn=lambda p: int(p.slope_lookback) + 1,
            primary_output="obv",
            visualization=Visualization.PANE,
            description="On-Balance Volume",
        )
    )
    reg.register(
        IndicatorDefinition(
            id="cvd",
            name="Cumulative Volume Delta (approx)",
            category=IndicatorCategory.VOLUME,
            params_cls=CvdParams,
            compute_fn=compute_cvd,
            warmup_fn=lambda p: int(p.window),
            primary_output="cumulative",
            visualization=Visualization.PANE,
            description="OHLCV-approximated cumulative volume delta",
        )
    )
    reg.register(
        IndicatorDefinition(
            id="donchian",
            name="Donchian Channel",
            category=IndicatorCategory.LEVELS,
            params_cls=DonchianParams,
            compute_fn=compute_donchian,
            warmup_fn=lambda p: int(p.period),
            primary_output="upper",
            visualization=Visualization.OVERLAY,
            description="Donchian high/low channel",
        )
    )
    reg.register(
        IndicatorDefinition(
            id="ppo",
            name="Price Percent Oscillator",
            category=IndicatorCategory.MOMENTUM,
            params_cls=PpoParams,
            compute_fn=compute_ppo,
            warmup_fn=lambda p: int(p.slow) + int(p.signal),
            primary_output="ppo",
            visualization=Visualization.PANE,
            description="PPO momentum (experimental Lab feature)",
            tags=("experimental",),
        )
    )
    reg.register(
        IndicatorDefinition(
            id="best_cloud",
            name="BEST Cloud",
            category=IndicatorCategory.TREND,
            params_cls=BestCloudParams,
            compute_fn=compute_best_cloud,
            warmup_fn=lambda p: int(p.slow_period),
            primary_output="cross",
            visualization=Visualization.OVERLAY,
            description="Two-MA cloud confirmation (experimental)",
            tags=("experimental",),
        )
    )
    reg.register(
        IndicatorDefinition(
            id="structure",
            name="Price Structure",
            category=IndicatorCategory.STRUCTURE,
            params_cls=StructureParams,
            compute_fn=compute_structure,
            warmup_fn=lambda p: 2 * int(p.swing_lookback) + 1,
            primary_output="bias",
            visualization=Visualization.NONE,
            description="Swing HH/HL bias + BOS (live pipeline)",
        )
    )
    return reg


REGISTRY = _build_registry()

# Re-export for callers that need replace/json helpers in tests
__all__ = [
    "REGISTRY",
    "IndicatorCategory",
    "IndicatorDefinition",
    "IndicatorRegistry",
    "InvalidParamsError",
    "UnknownIndicatorError",
    "Visualization",
    "serialize_state",
]
