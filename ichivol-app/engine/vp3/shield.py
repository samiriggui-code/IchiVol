"""VP-S1 Bouclier — critères S1–S5 (amendement VP0-2026-09-27 Questions M/N).

Aucun run ici : pure évaluation à partir de métriques / returns déjà calculés.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Sequence

from vp3 import N_T10B_SHIELD
from vp3.bootstrap import DEFAULT_BOOT_N, DEFAULT_SEED, BootstrapCI, paired_block_delta_ci
from vp3.metrics import N_YEAR


@dataclass(frozen=True)
class ShieldScore:
    """Agrégats par symbole × TF pour Bi ∈ {BM, BN} ou B0."""

    strategy: str
    cagr_agg: float | None
    dd_pire: float  # pire maxDD de pli (≤ 0)
    calmar: float | None
    n_trades: int
    fold_max_dds: tuple[float, ...]
    bar_returns: tuple[float, ...]
    bar_times: tuple[int, ...]


@dataclass(frozen=True)
class ShieldCriteria:
    s1: bool
    s2: bool
    s3: bool
    s4: bool
    s5: bool | None  # None si adverse non fourni
    delta_maxdd: BootstrapCI
    delta_sharpe: BootstrapCI | None
    dsr_i: float | None  # reporté, non bloquant (N=48)
    n_t10b: int
    verdict: str  # BOUCLIER VALIDÉ | PAS VALIDÉ | NON CONCLUANT


def cagr_from_bar_returns(returns: Sequence[float], *, interval: str) -> float | None:
    """CAGR_agg = ∏(1+r)^(N_year / n) − 1 (§8.1 / amendement M/N)."""
    if not returns:
        return None
    n_year = N_YEAR[interval]
    prod = 1.0
    for r in returns:
        prod *= 1.0 + r
    n = len(returns)
    if prod <= 0 or n <= 0:
        return None
    return prod ** (n_year / n) - 1.0


def dd_pire_from_folds(fold_max_dds: Sequence[float]) -> float:
    """Pire maxDD de pli (plus négatif)."""
    if not fold_max_dds:
        return 0.0
    return min(fold_max_dds)


def calmar_ratio(cagr_agg: float | None, dd_pire: float) -> float | None:
    if cagr_agg is None:
        return None
    abs_dd = abs(dd_pire)
    if abs_dd <= 0:
        return None
    return cagr_agg / abs_dd


def check_s1(dd_bi: float, dd_b0: float) -> bool:
    """DD_pire(Bi) ≤ 0.5 × DD_pire(B0) en valeur absolue."""
    return abs(dd_bi) <= 0.5 * abs(dd_b0) + 1e-15


def check_s2(cagr_bi: float | None, cagr_b0: float | None) -> bool:
    """CAGR_agg(Bi) > 0 et ≥ ½ B0 (si B0 ≤ 0 : seulement > 0)."""
    if cagr_bi is None or cagr_bi <= 0:
        return False
    if cagr_b0 is None or cagr_b0 <= 0:
        return True
    return cagr_bi >= 0.5 * cagr_b0 - 1e-15


def check_s3(calmar_bi: float | None, calmar_b0: float | None) -> bool:
    if calmar_bi is None or calmar_b0 is None:
        return False
    return calmar_bi > calmar_b0


def check_s4(delta_maxdd: BootstrapCI) -> bool:
    """IC 95 % Δ maxDD (Bi − B0) exclut 0 en faveur de Bi (Δ > 0)."""
    return bool(delta_maxdd.excludes_zero and delta_maxdd.mean > 0)


def score_from_wf_parts(
    *,
    strategy: str,
    interval: str,
    fold_max_dds: Sequence[float],
    bar_returns: Sequence[float],
    bar_times: Sequence[int],
    n_trades: int,
) -> ShieldScore:
    cagr = cagr_from_bar_returns(bar_returns, interval=interval)
    dd = dd_pire_from_folds(fold_max_dds)
    return ShieldScore(
        strategy=strategy,
        cagr_agg=cagr,
        dd_pire=dd,
        calmar=calmar_ratio(cagr, dd),
        n_trades=n_trades,
        fold_max_dds=tuple(fold_max_dds),
        bar_returns=tuple(bar_returns),
        bar_times=tuple(bar_times),
    )


def evaluate_shield(
    bi: ShieldScore,
    b0: ShieldScore,
    *,
    interval: str,
    n_boot: int = DEFAULT_BOOT_N,
    seed: int = DEFAULT_SEED,
    adverse_s1_s4: tuple[bool, bool, bool, bool] | None = None,
    dsr_i: float | None = None,
    min_trades_bm: int = 40,
) -> ShieldCriteria:
    """Juge Bi vs B0. Si adverse_s1_s4 fourni → S5 ; sinon S5=None."""
    s1 = check_s1(bi.dd_pire, b0.dd_pire)
    s2 = check_s2(bi.cagr_agg, b0.cagr_agg)
    s3 = check_s3(bi.calmar, b0.calmar)

    d_mdd = paired_block_delta_ci(
        list(bi.bar_returns),
        list(b0.bar_returns),
        interval=interval,
        n_boot=n_boot,
        seed=seed,
        metric="maxdd",
        times_a=list(bi.bar_times) if bi.bar_times else None,
        times_b=list(b0.bar_times) if b0.bar_times else None,
    )
    d_sr = paired_block_delta_ci(
        list(bi.bar_returns),
        list(b0.bar_returns),
        interval=interval,
        n_boot=n_boot,
        seed=seed,
        metric="sharpe",
        times_a=list(bi.bar_times) if bi.bar_times else None,
        times_b=list(b0.bar_times) if b0.bar_times else None,
    )
    s4 = check_s4(d_mdd)

    s5: bool | None
    if adverse_s1_s4 is None:
        s5 = None
    else:
        s5 = all(adverse_s1_s4)

    if bi.strategy == "BM" and bi.n_trades < min_trades_bm:
        verd = "NON CONCLUANT"
    elif s1 and s2 and s3 and s4 and (s5 is True):
        verd = "BOUCLIER VALIDÉ"
    elif s1 and s2 and s3 and s4 and s5 is False:
        verd = "NON CONCLUANT"
    elif s1 and s2 and s3 and s4 and s5 is None:
        # Base seule (étape partielle) — pas encore VALIDÉ sans S5
        verd = "PAS VALIDÉ"
    else:
        verd = "PAS VALIDÉ"

    return ShieldCriteria(
        s1=s1,
        s2=s2,
        s3=s3,
        s4=s4,
        s5=s5,
        delta_maxdd=d_mdd,
        delta_sharpe=d_sr,
        dsr_i=dsr_i,
        n_t10b=N_T10B_SHIELD,
        verdict=verd,
    )


def criteria_to_dict(c: ShieldCriteria) -> dict[str, Any]:
    d = asdict(c)
    d["delta_maxdd"] = asdict(c.delta_maxdd)
    d["delta_sharpe"] = asdict(c.delta_sharpe) if c.delta_sharpe is not None else None
    return d
