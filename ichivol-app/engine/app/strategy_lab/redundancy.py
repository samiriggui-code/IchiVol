"""T10c — feature×feature redundancy study (observation-only).

Pairwise boolean-signal overlap / φ on Lab ``CONDITION_REGISTRY`` keys.
Never alters decision, confidence, FeatureStatus, fills, or gates.
No auto-reject.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from app.agents.types import Direction
from app.indicators.ichimoku import Candle
from app.indicators.registry import REGISTRY
from app.strategy_lab.conditions import CONDITION_REGISTRY
from app.strategy_lab.features import FeatureBar, build_feature_series

_DISCLAIMER = (
    "Feature redundancy study — observation only; does not alter decision, "
    "confidence, FeatureStatus, fills, or gates; no auto-reject."
)


@dataclass(frozen=True)
class FeatureMeta:
    key: str
    indicator_id: str
    family: str | None
    status: str | None
    n_true: int
    rate: float

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "indicator_id": self.indicator_id,
            "family": self.family,
            "status": self.status,
            "n_true": self.n_true,
            "rate": self.rate,
        }


@dataclass(frozen=True)
class PairRedundancy:
    a: str
    b: str
    n_a: int
    n_b: int
    n_both: int
    n_either: int
    jaccard: float | None
    p_b_given_a: float | None
    p_a_given_b: float | None
    phi: float | None
    same_family: bool
    same_status: bool

    def to_dict(self) -> dict:
        return {
            "a": self.a,
            "b": self.b,
            "n_a": self.n_a,
            "n_b": self.n_b,
            "n_both": self.n_both,
            "n_either": self.n_either,
            "jaccard": self.jaccard,
            "p_b_given_a": self.p_b_given_a,
            "p_a_given_b": self.p_a_given_b,
            "phi": self.phi,
            "same_family": self.same_family,
            "same_status": self.same_status,
        }


@dataclass(frozen=True)
class FeatureRedundancyReport:
    symbol: str
    timeframe: str
    n_bars: int
    direction: str
    keys: list[str]
    features: list[FeatureMeta] = field(default_factory=list)
    pairs: list[PairRedundancy] = field(default_factory=list)
    top_redundant: list[PairRedundancy] = field(default_factory=list)
    skipped_pairs: int = 0
    disclaimer: str = _DISCLAIMER

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "n_bars": self.n_bars,
            "direction": self.direction,
            "keys": list(self.keys),
            "features": [f.to_dict() for f in self.features],
            "pairs": [p.to_dict() for p in self.pairs],
            "top_redundant": [p.to_dict() for p in self.top_redundant],
            "skipped_pairs": self.skipped_pairs,
            "disclaimer": self.disclaimer,
        }


def boolean_condition_keys() -> list[str]:
    """CONDITION_REGISTRY keys with ``value_type is bool``, sorted."""
    return sorted(k for k, spec in CONDITION_REGISTRY.items() if spec.value_type is bool)


def feature_boolean_series(
    bars: Sequence[FeatureBar],
    key: str,
    *,
    direction: Direction,
    expected: bool = True,
) -> list[bool]:
    spec = CONDITION_REGISTRY.get(key)
    if spec is None:
        raise ValueError(f"unknown condition key: {key!r}")
    if spec.value_type is not bool:
        raise ValueError(f"condition {key!r} is not boolean (got {spec.value_type})")
    return [bool(spec.holds(bar, expected, direction)) for bar in bars]


def pairwise_overlap(a: Sequence[bool], b: Sequence[bool]) -> dict:
    if len(a) != len(b):
        raise ValueError("series length mismatch")
    n = len(a)
    n_a = sum(1 for x in a if x)
    n_b = sum(1 for x in b if x)
    n_both = sum(1 for x, y in zip(a, b) if x and y)
    n_either = sum(1 for x, y in zip(a, b) if x or y)
    jaccard = (n_both / n_either) if n_either else None
    p_b_given_a = (n_both / n_a) if n_a else None
    p_a_given_b = (n_both / n_b) if n_b else None
    phi = _phi_coefficient(a, b, n=n, n_a=n_a, n_b=n_b, n_both=n_both)
    return {
        "n_a": n_a,
        "n_b": n_b,
        "n_both": n_both,
        "n_either": n_either,
        "jaccard": jaccard,
        "p_b_given_a": p_b_given_a,
        "p_a_given_b": p_a_given_b,
        "phi": phi,
    }


def _phi_coefficient(
    a: Sequence[bool],
    b: Sequence[bool],
    *,
    n: int,
    n_a: int,
    n_b: int,
    n_both: int,
) -> float | None:
    """φ / Matthews correlation for two binary series."""
    if n == 0:
        return None
    # Prefer stdlib correlation when both series have variance.
    xa = [1.0 if x else 0.0 for x in a]
    xb = [1.0 if x else 0.0 for x in b]
    if len(set(xa)) < 2 or len(set(xb)) < 2:
        return None
    try:
        return float(statistics.correlation(xa, xb))
    except statistics.StatisticsError:
        return None


def _feature_meta(
    key: str,
    series: Sequence[bool],
) -> FeatureMeta:
    spec = CONDITION_REGISTRY[key]
    ind_id = spec.indicator_id
    family: str | None = None
    status: str | None = None
    if ind_id != "derived" and ind_id in REGISTRY:
        defn = REGISTRY.get(ind_id)
        family = defn.family
        status = defn.status.value if defn.status is not None else None
    n_true = sum(1 for x in series if x)
    n = len(series)
    return FeatureMeta(
        key=key,
        indicator_id=ind_id,
        family=family,
        status=status,
        n_true=n_true,
        rate=(n_true / n) if n else 0.0,
    )


def run_feature_redundancy_study(
    candles: Sequence[Candle],
    *,
    symbol: str,
    timeframe: str,
    direction: Direction = Direction.LONG,
    keys: Sequence[str] | None = None,
    expected: bool = True,
    min_true: int = 5,
    top_n: int = 20,
) -> FeatureRedundancyReport:
    """Build FeatureBar once, then pairwise bool overlap / φ (observation)."""
    if not candles:
        return FeatureRedundancyReport(
            symbol=symbol,
            timeframe=timeframe,
            n_bars=0,
            direction=direction.value,
            keys=[],
        )
    key_list = list(keys) if keys is not None else boolean_condition_keys()
    unknown = [k for k in key_list if k not in CONDITION_REGISTRY]
    if unknown:
        raise ValueError(f"unknown condition keys: {unknown}")
    non_bool = [k for k in key_list if CONDITION_REGISTRY[k].value_type is not bool]
    if non_bool:
        raise ValueError(f"non-boolean condition keys: {non_bool}")

    series = build_feature_series(candles)
    bool_by_key: dict[str, list[bool]] = {
        k: feature_boolean_series(series.bars, k, direction=direction, expected=expected)
        for k in key_list
    }
    features = [_feature_meta(k, bool_by_key[k]) for k in key_list]
    meta_by_key = {f.key: f for f in features}

    pairs: list[PairRedundancy] = []
    skipped = 0
    for i, ka in enumerate(key_list):
        for kb in key_list[i + 1 :]:
            sa, sb = bool_by_key[ka], bool_by_key[kb]
            n_a = sum(1 for x in sa if x)
            n_b = sum(1 for x in sb if x)
            if n_a < min_true or n_b < min_true:
                skipped += 1
                continue
            stats = pairwise_overlap(sa, sb)
            ma, mb = meta_by_key[ka], meta_by_key[kb]
            pairs.append(
                PairRedundancy(
                    a=ka,
                    b=kb,
                    n_a=stats["n_a"],
                    n_b=stats["n_b"],
                    n_both=stats["n_both"],
                    n_either=stats["n_either"],
                    jaccard=stats["jaccard"],
                    p_b_given_a=stats["p_b_given_a"],
                    p_a_given_b=stats["p_a_given_b"],
                    phi=stats["phi"],
                    same_family=bool(ma.family and ma.family == mb.family),
                    same_status=bool(ma.status and ma.status == mb.status),
                )
            )

    def _rank(p: PairRedundancy) -> float:
        if p.phi is not None and math.isfinite(p.phi):
            return abs(p.phi)
        if p.jaccard is not None:
            return p.jaccard
        return 0.0

    ranked = sorted(pairs, key=_rank, reverse=True)
    top = ranked[: max(0, top_n)]

    return FeatureRedundancyReport(
        symbol=symbol,
        timeframe=timeframe,
        n_bars=len(series.bars),
        direction=direction.value,
        keys=key_list,
        features=features,
        pairs=pairs,
        top_redundant=top,
        skipped_pairs=skipped,
    )


__all__ = [
    "FeatureMeta",
    "FeatureRedundancyReport",
    "PairRedundancy",
    "boolean_condition_keys",
    "feature_boolean_series",
    "pairwise_overlap",
    "run_feature_redundancy_study",
]
