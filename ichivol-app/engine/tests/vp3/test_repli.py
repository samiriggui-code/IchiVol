"""VP-BR — entrée sur repli : règle figée, causale, exécution commune VP2."""

from __future__ import annotations

import json
import random
from pathlib import Path

from app.indicators.ichimoku import Candle
from vp2 import TIME_STOP_BARS
from vp3 import WARMUP_BARS
from vp3.entries import entry_mask
from vp3.repli import BR_RULESET, br_mask
from vp3.repli_run import apply_adverse
from vp3.rules import strategy_rules

H = 3600
T0 = 1_700_000_000 - 1_700_000_000 % H
DOC = Path(__file__).resolve().parents[4] / "docs" / "repli-artifacts" / "rulesets.json"


def _walk(n: int, seed: int = 11) -> list[Candle]:
    """Marche aléatoire à dérive haussière : assez de tendance et de replis pour toucher la Kijun."""
    rng = random.Random(seed)
    out, px = [], 100.0
    for i in range(n):
        op = px
        px = max(1.0, px * (1 + rng.gauss(0.0006, 0.006)))
        hi, lo = max(op, px) * (1 + abs(rng.gauss(0, 0.002))), min(op, px) * (1 - abs(rng.gauss(0, 0.002)))
        out.append(Candle(time=T0 + i * H, open=op, high=hi, low=lo, close=px, volume=1000.0 * rng.uniform(0.5, 1.5)))
    return out


def test_ruleset_is_the_preregistered_one():
    registered = next(r for r in json.loads(DOC.read_text(encoding="utf-8")) if r["id"] == BR_RULESET["id"])
    registered.pop("description")
    assert registered == BR_RULESET


def test_mask_fires_after_warmup_only_and_is_the_harness_entry():
    candles = _walk(1500)
    mask = br_mask(candles)
    assert len(mask) == len(candles) and sum(mask) > 0
    assert not any(mask[:WARMUP_BARS])
    assert entry_mask("BR", candles) == mask


def test_mask_is_causal():
    candles = _walk(1500)
    full = br_mask(candles)
    for cut in (700, 1100, 1499):
        assert br_mask(candles[:cut]) == full[:cut]


def test_br_uses_the_common_execution():
    rules = strategy_rules("BR", "1h")
    assert rules.exit_mode == "levels_only" and rules.take_profit_r == 2.0
    assert rules.time_stop_bars == TIME_STOP_BARS["1h"] and rules.allow_short is False


def test_edge_in_base_only_is_not_conclusive():
    base = {"hypotheses": [{"symbol": "BTCUSDT", "verdict": "EDGE", "verdict_final": "EDGE"},
                           {"symbol": "ETHUSDT", "verdict": "PAS D'EDGE", "verdict_final": "PAS D'EDGE"}]}
    adverse = {"hypotheses": [{"symbol": "BTCUSDT", "verdict": "PAS D'EDGE", "verdict_final": "PAS D'EDGE"},
                              {"symbol": "ETHUSDT", "verdict": "PAS D'EDGE", "verdict_final": "PAS D'EDGE"}]}
    apply_adverse(base, adverse)
    assert base["hypotheses"][0]["verdict_final"] == adverse["hypotheses"][0]["verdict_final"] == "NON CONCLUANT"
    assert base["hypotheses"][1]["verdict_final"] == "PAS D'EDGE"
