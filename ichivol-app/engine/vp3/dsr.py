"""Deflated Sharpe Ratio (§9.3) — Bailey & López de Prado PSR/DSR.

σ(SR) = écart-type empirique des SR (même échelle par barre) des N essais T10b.
skew / kurtosis = moments d'échantillon des returns de Bi (kurt Pearson, normal=3).
"""

from __future__ import annotations

import math
from statistics import NormalDist

_Z = NormalDist()


def sample_skew_kurtosis(returns: list[float]) -> tuple[float, float]:
    """Pearson skew and kurtosis (normal → kurt=3). Returns (0, 3) if undefined."""
    n = len(returns)
    if n < 3:
        return 0.0, 3.0
    mu = sum(returns) / n
    m2 = sum((x - mu) ** 2 for x in returns) / n
    if m2 <= 0:
        return 0.0, 3.0
    m3 = sum((x - mu) ** 3 for x in returns) / n
    m4 = sum((x - mu) ** 4 for x in returns) / n
    skew = m3 / (m2**1.5)
    kurt = m4 / (m2**2)
    return skew, kurt


def empirical_sr_std(trial_srs: list[float]) -> float:
    """Sample stdev of per-trial Sharpe estimates (same scale as `sr`)."""
    n = len(trial_srs)
    if n < 2:
        return 0.0
    mu = sum(trial_srs) / n
    var = sum((x - mu) ** 2 for x in trial_srs) / (n - 1)
    return math.sqrt(var) if var > 0 else 0.0


def probabilistic_sharpe_ratio(
    sr: float,
    n_obs: int,
    *,
    skew: float = 0.0,
    kurt: float = 3.0,
    sr_benchmark: float = 0.0,
) -> float | None:
    """PSR = Φ( (SR̂ − SR*) / σ̂(SR̂) ) with non-normal correction."""
    if n_obs < 2 or not math.isfinite(sr):
        return None
    denom = 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr * sr
    if denom <= 0:
        return None
    se = math.sqrt(denom / (n_obs - 1))
    if se <= 0:
        return None
    return _Z.cdf((sr - sr_benchmark) / se)


def expected_max_sr(n_trials: int, sr_std: float) -> float:
    """E[max SR] under N independent null trials (Bailey & López de Prado)."""
    if n_trials < 1:
        return 0.0
    if n_trials == 1 or sr_std <= 0:
        return 0.0
    gamma = 0.5772156649
    return sr_std * (
        (1 - gamma) * _Z.inv_cdf(1 - 1.0 / math.e)
        + gamma * _Z.inv_cdf(1 - 1.0 / (n_trials * math.e))
    )


def deflated_sharpe_ratio(
    sr: float,
    n_obs: int,
    *,
    n_trials: int = 1,
    skew: float = 0.0,
    kurt: float = 3.0,
    trial_srs: list[float] | None = None,
    returns: list[float] | None = None,
) -> float | None:
    """DSR = PSR(SR̂, SR* = E[max SR | N trials, σ_emp]).

    If `returns` is given, skew/kurt are overwritten by sample moments.
    If `trial_srs` is given (len≥2), σ(SR) is their sample stdev; for N=1,
    E[max]=0 so DSR equals PSR(sr*=0) regardless of σ.
    """
    if returns is not None:
        skew, kurt = sample_skew_kurtosis(returns)
    if trial_srs is not None:
        sr_std = empirical_sr_std(trial_srs)
        n_trials = max(n_trials, len(trial_srs))
    elif n_trials <= 1:
        sr_std = 0.0
    else:
        raise ValueError(
            "deflated_sharpe_ratio: n_trials>1 requires trial_srs "
            "(empirical σ of per-bar SR across T10b trials)"
        )
    sr_star = expected_max_sr(n_trials, sr_std)
    return probabilistic_sharpe_ratio(
        sr, n_obs, skew=skew, kurt=kurt, sr_benchmark=sr_star
    )
