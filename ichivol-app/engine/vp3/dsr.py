"""Deflated Sharpe Ratio (§9.3) — Bailey & López de Prado PSR/DSR scaffold.

N = T10b hypothesis counter (§10). Early VP3 runs pass N explicitly (default 1).
"""

from __future__ import annotations

import math
from statistics import NormalDist

_Z = NormalDist()


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
    # Variance of SR estimator (Lo / Bailey)
    denom = 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr * sr
    if denom <= 0:
        return None
    se = math.sqrt(denom / (n_obs - 1))
    if se <= 0:
        return None
    return _Z.cdf((sr - sr_benchmark) / se)


def expected_max_sr(n_trials: int, sr_std: float = 1.0) -> float:
    """E[max SR] under N independent null trials ≈ sr_std * ((1-γ)Z⁻¹(1-1/e) + γ Z⁻¹(1-1/(N e)))."""
    if n_trials < 1:
        return 0.0
    # Euler-Mascheroni
    gamma = 0.5772156649
    if n_trials == 1:
        return 0.0
    return sr_std * ((1 - gamma) * _Z.inv_cdf(1 - 1.0 / math.e) + gamma * _Z.inv_cdf(1 - 1.0 / (n_trials * math.e)))


def deflated_sharpe_ratio(
    sr: float,
    n_obs: int,
    *,
    n_trials: int = 1,
    skew: float = 0.0,
    kurt: float = 3.0,
) -> float | None:
    """DSR = PSR(SR̂, SR* = E[max SR | N trials])."""
    sr_star = expected_max_sr(n_trials)
    return probabilistic_sharpe_ratio(sr, n_obs, skew=skew, kurt=kurt, sr_benchmark=sr_star)
