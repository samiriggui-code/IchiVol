"""Catalogued Synthetic Market Lab scenarios (mission brief §12). Each pairs
a fabricated candle series with the GroundTruth only the generator knows --
the pipeline under test in app/synthetic/validation.py sees just the candles.

Five scenarios to start (brief step 10: "3 à 5 scénarios contrôlés"), chosen
to cover the cases the CDC's own acceptance criteria already care about most:
a clean trend in each direction, a trend the pipeline must NOT confirm
(unconfirmed volume), a fake-out it must not treat as real, and a range
where no directional conviction should emerge at all.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.indicators.ichimoku import Candle
from app.synthetic.generator import GeneratorParams, Regime, false_breakout_windows, generate_market
from app.synthetic.ground_truth import GroundTruth

SCENARIO_A_BULLISH_TREND = "bullish_trend"
SCENARIO_B_BEARISH_TREND = "bearish_trend"
SCENARIO_D_FALSE_BREAKOUT = "false_breakout"
SCENARIO_E_LOW_VOLUME_BULLISH = "low_volume_bullish"
SCENARIO_G_RANGE = "range"


@dataclass(frozen=True)
class Scenario:
    name: str
    candles: list[Candle]
    ground_truth: GroundTruth


def _params(seed: int) -> GeneratorParams:
    return GeneratorParams(n=300, base_price=100.0, base_volume=100.0, seed=seed)


def bullish_trend(seed: int = 1) -> Scenario:
    candles = generate_market(Regime.BULLISH_TREND, _params(seed))
    truth = GroundTruth(
        scenario=SCENARIO_A_BULLISH_TREND,
        expected_context="bullish",
        eval_window=(250, 299),
        acceptable_decisions=("BUY", "WATCH"),
        forbidden_decisions=("SELL", "NO_TRADE"),
        notes="Tendance haussière propre, volume corrélé au mouvement -- le "
        "pipeline doit rester orienté LONG (BUY quand la participation "
        "confirme, WATCH sinon) et ne jamais basculer côté vente.",
    )
    return Scenario(SCENARIO_A_BULLISH_TREND, candles, truth)


def bearish_trend(seed: int = 2) -> Scenario:
    candles = generate_market(Regime.BEARISH_TREND, _params(seed))
    truth = GroundTruth(
        scenario=SCENARIO_B_BEARISH_TREND,
        expected_context="bearish",
        eval_window=(250, 299),
        acceptable_decisions=("SELL", "WATCH"),
        forbidden_decisions=("BUY", "NO_TRADE"),
        notes="Tendance baissière propre, volume qui s'accélère à la baisse "
        "-- le pipeline doit rester orienté SHORT et ne jamais basculer "
        "côté achat.",
    )
    return Scenario(SCENARIO_B_BEARISH_TREND, candles, truth)


def false_breakout(seed: int = 4) -> Scenario:
    candles = generate_market(Regime.FALSE_BREAKOUT, _params(seed))
    _, breakout_end = false_breakout_windows(300)
    truth = GroundTruth(
        scenario=SCENARIO_D_FALSE_BREAKOUT,
        expected_context="false_breakout",
        eval_window=(breakout_end, breakout_end + 15),
        acceptable_decisions=("WATCH", "NO_TRADE"),
        forbidden_decisions=("BUY", "SELL"),
        notes="Cassure de résistance sur volume faible puis retour sous la "
        "range -- une vraie porte Participation doit empêcher un BUY "
        "confirmé pendant/juste après la cassure (brief §12, scénario D).",
    )
    return Scenario(SCENARIO_D_FALSE_BREAKOUT, candles, truth)


def low_volume_bullish(seed: int = 5) -> Scenario:
    candles = generate_market(Regime.LOW_VOLUME_BULLISH, _params(seed))
    truth = GroundTruth(
        scenario=SCENARIO_E_LOW_VOLUME_BULLISH,
        expected_context="bullish_unconfirmed",
        eval_window=(250, 299),
        acceptable_decisions=("WATCH", "NO_TRADE"),
        forbidden_decisions=("BUY", "SELL"),
        notes="Ichimoku bullish net mais volume qui ne confirme jamais -- un "
        "signal directionnel fort ne doit pas suffire seul à un BUY "
        "actionnable (brief §10, §12 scénario E).",
    )
    return Scenario(SCENARIO_E_LOW_VOLUME_BULLISH, candles, truth)


def range_market(seed: int = 7) -> Scenario:
    candles = generate_market(Regime.RANGE, _params(seed))
    truth = GroundTruth(
        scenario=SCENARIO_G_RANGE,
        expected_context="neutral",
        eval_window=(250, 299),
        acceptable_decisions=("WATCH", "NO_TRADE"),
        forbidden_decisions=("BUY", "SELL"),
        notes="Oscillation sans tendance -- aucune conviction directionnelle "
        "durable ne doit émerger (brief §12, scénario G).",
    )
    return Scenario(SCENARIO_G_RANGE, candles, truth)


ALL_SCENARIOS = (bullish_trend, bearish_trend, false_breakout, low_volume_bullish, range_market)
