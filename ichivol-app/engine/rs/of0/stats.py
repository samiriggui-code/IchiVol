"""OLS, Spearman et bootstrap par jour (RS-07 §5–§6). Stdlib seulement."""

from __future__ import annotations

import math
import random
from typing import Sequence


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Gauss avec pivot partiel ; `a` symétrique définie positive attendue."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            raise ValueError("matrice singulière")
        m[col], m[piv] = m[piv], m[col]
        for r in range(col + 1, n):
            f = m[r][col] / m[col][col]
            if f:
                for c in range(col, n + 1):
                    m[r][c] -= f * m[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (m[r][n] - sum(m[r][c] * x[c] for c in range(r + 1, n))) / m[r][r]
    return x


def ols(x_rows: Sequence[Sequence[float]], y: Sequence[float]) -> tuple[list[float], float, list[float]]:
    """(coefficients [const, β…] sur variables standardisées, R², résidus)."""
    n, k = len(y), len(x_rows[0])
    means = [sum(r[j] for r in x_rows) / n for j in range(k)]
    sds = [math.sqrt(sum((r[j] - means[j]) ** 2 for r in x_rows) / n) or 1.0 for j in range(k)]
    z = [[1.0] + [(r[j] - means[j]) / sds[j] for j in range(k)] for r in x_rows]
    p = k + 1
    xtx = [[0.0] * p for _ in range(p)]
    xty = [0.0] * p
    for row, yi in zip(z, y):
        for i in range(p):
            ri = row[i]
            xty[i] += ri * yi
            xi = xtx[i]
            for j in range(i, p):
                xi[j] += ri * row[j]
    for i in range(p):
        for j in range(i):
            xtx[i][j] = xtx[j][i]
    beta = _solve(xtx, xty)
    fitted = [sum(bj * rj for bj, rj in zip(beta, row)) for row in z]
    resid = [yi - fi for yi, fi in zip(y, fitted)]
    ybar = sum(y) / n
    sst = sum((yi - ybar) ** 2 for yi in y)
    sse = sum(e * e for e in resid)
    return beta, (1.0 - sse / sst) if sst > 0 else 0.0, resid


def ranks(xs: Sequence[float]) -> list[float]:
    """Rangs moyens (égalités → moyenne)."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def pearson(a: Sequence[float], b: Sequence[float]) -> float | None:
    n = len(a)
    if n < 3:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    sab = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    saa = sum((x - ma) ** 2 for x in a)
    sbb = sum((y - mb) ** 2 for y in b)
    return sab / math.sqrt(saa * sbb) if saa > 0 and sbb > 0 else None


def spearman(a: Sequence[float], b: Sequence[float]) -> float | None:
    return pearson(ranks(a), ranks(b))


def day_block_bootstrap_ic(
    ra: Sequence[float], rb: Sequence[float], days: Sequence[int], *, n: int, seed: int, alpha: float
) -> tuple[float, float]:
    """IC percentile (1 − alpha) de la corrélation des rangs, tirage de jours entiers.

    Les rangs sont ceux de l'échantillon complet (corrélation de Pearson sur les
    rangs par tirage) : approximation standard du Spearman rééchantillonné, qui
    évite de reclasser 30 000 points × 10 000 tirages.
    """
    acc: dict[int, list[float]] = {}
    for x, y, d in zip(ra, rb, days):
        s = acc.setdefault(d, [0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        s[0] += 1
        s[1] += x
        s[2] += y
        s[3] += x * y
        s[4] += x * x
        s[5] += y * y
    blocks = list(acc.values())
    k = len(blocks)
    rng = random.Random(seed)
    vals: list[float] = []
    for _ in range(n):
        t = [0.0] * 6
        for _j in range(k):
            s = blocks[rng.randrange(k)]
            for q in range(6):
                t[q] += s[q]
        m = t[0]
        cov = t[3] / m - (t[1] / m) * (t[2] / m)
        va = t[4] / m - (t[1] / m) ** 2
        vb = t[5] / m - (t[2] / m) ** 2
        if va > 0 and vb > 0:
            vals.append(cov / math.sqrt(va * vb))
    vals.sort()
    lo = vals[int((alpha / 2) * len(vals))]
    hi = vals[min(len(vals) - 1, int((1 - alpha / 2) * len(vals)))]
    return lo, hi
