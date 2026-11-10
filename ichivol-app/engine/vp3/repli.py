"""VP-BR — entrée sur repli (Kijun), LONG. Pré-enregistrement :
docs/REPLI-KIJUN-PREENREGISTREMENT-2026-11-10.md (règle figée avant tout run, N T10b = 51).

La règle est un ruleset du Strategy Lab : mêmes features, même évaluation causale que le Lab.
"""

from __future__ import annotations

from app.indicators.ichimoku import Candle
from app.strategy_lab.evaluator import matches_mask
from app.strategy_lab.features import build_feature_series
from app.strategy_lab.ruleset import parse_ruleset

from vp3 import WARMUP_BARS

# Copie de docs/repli-artifacts/rulesets.json (entrée LONG) ; tests/vp3/test_repli.py vérifie l'égalité.
BR_RULESET: dict = {
    "id": "REPLI-KIJUN-LONG-1h",
    "version": "1",
    "direction": "LONG",
    "timeframe": "1h",
    "conditions": {"price_above_kumo": True, "tenkan_above_kijun": True, "kijun_bounce": True, "rvol_max": 2.5},
    "entry": "next_open",
    "stop_atr": 1.5,
    "target_atr": 3.0,
}


def br_mask(candles: list[Candle]) -> list[bool]:
    """BUY à la clôture des barres qui remplissent la règle (après warm-up)."""
    mask = matches_mask(build_feature_series(candles), parse_ruleset(BR_RULESET))
    if len(mask) != len(candles):
        raise ValueError("feature series not aligned with candles")
    return [hit and i >= WARMUP_BARS for i, hit in enumerate(mask)]
