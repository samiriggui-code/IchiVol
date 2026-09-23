"""IndicatorRegistry — single entry point for deterministic indicator compute.

Wraps existing ``compute_*`` functions without rewriting formulas. Live,
backtest, replay and agent tooling must all go through ``REGISTRY``.

Dependency-aware indicators (``depends_on``) receive
``compute_fn(candles, params, deps)`` where ``deps`` maps dependency id →
state list. Leaf indicators keep ``compute_fn(candles, params)``.

OI / funding (`oi_funding`) stays **outside** this registry: it consumes
external futures streams, not OHLCV candles alone.
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
from app.indicators.ichimoku_analytics import (
    IchimokuAnalyticsParams,
    compute_ichimoku_analytics,
)
from app.indicators.location import LocationParams, compute_location
from app.indicators.obv import ObvParams, compute_obv
from app.indicators.ppo import PpoParams, compute_ppo
from app.indicators.rsi import RsiParams, compute_rsi
from app.indicators.rvol import RvolParams, compute_rvol
from app.indicators.structure import StructureParams, compute_structure
from app.indicators.wyckoff import WyckoffParams, compute_wyckoff

# Leaf: (candles, params) → states ; dependent: (candles, params, deps) → states
ComputeFn = Callable[..., list[Any]]
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


class DependencyCycleError(ValueError):
    """Raised when depends_on forms a cycle."""


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
    depends_on: tuple[str, ...] = ()

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
            if is_dataclass(default) and not isinstance(default, type):
                default = asdict(default)
            type_name = f.type if isinstance(f.type, str) else getattr(f.type, "__name__", str(f.type))
            out.append({"name": f.name, "type": type_name, "default": default})
        return out

    def outputs(self) -> list[str]:
        """State field names — discovered by computing on a 1-candle probe."""
        probe = [
            Candle(time=0, open=1.0, high=1.0, low=1.0, close=1.0, volume=1.0),
        ]
        if self.depends_on:
            # Resolve via the global registry once it is fully built.
            import app.indicators.registry as reg_mod

            states = reg_mod.REGISTRY.compute(self.id, probe)
        else:
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

    def _coerce_params(self, params: dict[str, Any] | Any | None) -> Any:
        if params is None:
            return self.params_cls()
        if is_dataclass(params) and not isinstance(params, type):
            return params
        if isinstance(params, dict):
            return self.build_params(params)
        raise InvalidParamsError(
            f"params must be dict, {self.params_cls.__name__}, or None"
        )

    def compute(
        self,
        candles: Sequence[Candle],
        params: dict[str, Any] | Any | None = None,
        deps: dict[str, list[Any]] | None = None,
    ) -> list[Any]:
        built = self._coerce_params(params)
        if self.depends_on:
            if deps is None:
                raise InvalidParamsError(
                    f"{self.id} requires deps={list(self.depends_on)}; "
                    "use REGISTRY.compute / compute_many"
                )
            return self.compute_fn(candles, built, deps)
        return self.compute_fn(candles, built)

    def own_warmup(self, params: dict[str, Any] | Any | None = None) -> int:
        return int(self.warmup_fn(self._coerce_params(params)))

    def warmup(self, params: dict[str, Any] | Any | None = None) -> int:
        own = self.own_warmup(params)
        if not self.depends_on:
            return own
        import app.indicators.registry as reg_mod

        dep_warmups = [reg_mod.REGISTRY.get(d).warmup() for d in self.depends_on]
        return max([own, *dep_warmups])

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "primary_output": self.primary_output,
            "visualization": self.visualization.value,
            "description": self.description,
            "tags": list(self.tags),
            "depends_on": list(self.depends_on),
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


def _compute_ichimoku_analytics_reg(
    candles: Sequence[Candle],
    params: IchimokuAnalyticsParams,
    deps: dict[str, list[Any]],
) -> list[Any]:
    return compute_ichimoku_analytics(
        candles,
        ichi=deps["ichimoku"],
        atr=deps["atr"],
        params=params,
    )


def _compute_location_reg(
    candles: Sequence[Candle],
    params: LocationParams,
    deps: dict[str, list[Any]],
) -> list[Any]:
    return compute_location(candles, deps["structure"], params)


def _compute_wyckoff_reg(
    candles: Sequence[Candle],
    params: WyckoffParams,
    deps: dict[str, list[Any]],
) -> list[Any]:
    return compute_wyckoff(candles, deps["donchian"], params)


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
        definition = self.get(indicator_id)
        if definition.depends_on:
            params_by_id = {indicator_id: params} if params is not None else None
            return self.compute_many([indicator_id], candles, params_by_id)[indicator_id]
        return definition.compute(candles, params)

    def compute_many(
        self,
        ids: Sequence[str],
        candles: Sequence[Candle],
        params_by_id: dict[str, Any] | None = None,
    ) -> dict[str, list[Any]]:
        """Compute indicators once each, resolving ``depends_on`` topologically.

        ``params_by_id`` maps indicator id → params dataclass or override dict.
        Missing ids use that indicator's default params.
        """
        params_by_id = dict(params_by_id or {})
        order = self._topo_order(ids)
        results: dict[str, list[Any]] = {}
        for iid in order:
            definition = self.get(iid)
            built = definition._coerce_params(params_by_id.get(iid))
            if definition.depends_on:
                missing = [d for d in definition.depends_on if d not in results]
                if missing:
                    raise RuntimeError(f"{iid}: missing deps {missing} after topo sort")
                deps = {d: results[d] for d in definition.depends_on}
                results[iid] = definition.compute_fn(candles, built, deps)
            else:
                results[iid] = definition.compute_fn(candles, built)
        # Return requested ids only (deps used internally stay available if requested).
        return {iid: results[iid] for iid in ids}

    def _topo_order(self, ids: Sequence[str]) -> list[str]:
        """Return dependency-first order covering ``ids`` and their transitive deps."""
        needed: set[str] = set()
        visiting: set[str] = set()

        def _collect(iid: str) -> None:
            if iid in needed:
                return
            if iid in visiting:
                raise DependencyCycleError(
                    f"depends_on cycle involving: {iid}"
                )
            visiting.add(iid)
            definition = self.get(iid)
            for dep in definition.depends_on:
                _collect(dep)
            visiting.remove(iid)
            needed.add(iid)

        for iid in ids:
            _collect(iid)

        # Kahn: edges dep → dependent
        incoming: dict[str, int] = {i: 0 for i in needed}
        children: dict[str, list[str]] = {i: [] for i in needed}
        for iid in needed:
            for dep in self.get(iid).depends_on:
                children[dep].append(iid)
                incoming[iid] += 1

        queue = sorted(i for i, n in incoming.items() if n == 0)
        order: list[str] = []
        while queue:
            node = queue.pop(0)
            order.append(node)
            for child in children[node]:
                incoming[child] -= 1
                if incoming[child] == 0:
                    queue.append(child)
                    queue.sort()
        if len(order) != len(needed):
            cyclic = sorted(needed - set(order))
            raise DependencyCycleError(f"depends_on cycle among: {', '.join(cyclic)}")
        return order

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
    reg.register(
        IndicatorDefinition(
            id="ichimoku_analytics",
            name="Ichimoku Analytics",
            category=IndicatorCategory.TREND,
            params_cls=IchimokuAnalyticsParams,
            compute_fn=_compute_ichimoku_analytics_reg,
            warmup_fn=lambda p: max(int(p.slope_lookback), int(p.retest_max_bars_after_break)),
            primary_output="kijun_slope_state",
            visualization=Visualization.NONE,
            description="Kijun/Kumo research layer (Lab); depends on ichimoku+atr",
            depends_on=("ichimoku", "atr"),
        )
    )
    reg.register(
        IndicatorDefinition(
            id="location",
            name="Location (VP / VWAP)",
            category=IndicatorCategory.LEVELS,
            params_cls=LocationParams,
            compute_fn=_compute_location_reg,
            warmup_fn=lambda p: max(int(p.vwap_window), int(p.volume_profile.lookback)),
            primary_output="poc",
            visualization=Visualization.NONE,
            description="Volume profile + VWAP/AVWAP location; depends on structure",
            depends_on=("structure",),
        )
    )
    reg.register(
        IndicatorDefinition(
            id="wyckoff",
            name="Wyckoff Spring / Upthrust",
            category=IndicatorCategory.STRUCTURE,
            params_cls=WyckoffParams,
            compute_fn=_compute_wyckoff_reg,
            warmup_fn=lambda p: int(p.volume_lookback),
            primary_output="phase",
            visualization=Visualization.NONE,
            description="Wyckoff phase from Donchian + volume climax; depends on donchian",
            depends_on=("donchian",),
        )
    )
    return reg


REGISTRY = _build_registry()

# Re-export for callers that need replace/json helpers in tests
__all__ = [
    "REGISTRY",
    "DependencyCycleError",
    "IndicatorCategory",
    "IndicatorDefinition",
    "IndicatorRegistry",
    "InvalidParamsError",
    "UnknownIndicatorError",
    "Visualization",
    "serialize_state",
]
