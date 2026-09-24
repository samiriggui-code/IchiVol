"""Market microstructure research package (Binance-first).

Candidates live here until Strategy Lab / T9g promote them — never auto-wired
into the live decision pipeline.
"""

from app.microstructure.trade_cvd import (
    AggressorTrade,
    CvdCompareReport,
    compare_kline_vs_trade_cvd,
    compute_trade_cvd,
)

__all__ = [
    "AggressorTrade",
    "CvdCompareReport",
    "compare_kline_vs_trade_cvd",
    "compute_trade_cvd",
]
