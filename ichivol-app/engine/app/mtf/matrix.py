"""MTF-1 — matrice de tendance multi-horizons (calcul pur, aucune I/O).

Étude : docs/ETUDE-ORDERFLOW-MTF-2026-10-02.md §4–§5.

Une ligne par horizon (1h, 4h, 1d, 1w, + l'horizon de décision s'il n'en fait pas partie) :
- ``direction`` = sortie d'``ichimoku_agent`` sur les **bougies closes** de l'horizon, la même règle que
  l'étape Direction du pipeline ;
- ``state`` = CONFIRMED / LATE / STALE / UNAVAILABLE (``screener/timing.py``) ;
- ``provisional_direction`` = même calcul en incluant la bougie en formation, **affiché à part, jamais
  utilisé** (peut changer jusqu'à la clôture) ;
- contexte volume / volatilité (RVOL, ATR, ADX) de la dernière bougie close.

Observe-only : ne vote pas, ne change ni décision, ni confidence, ni paper (``used_by_decision=False``).
Aucun score : on publie un décompte d'accords et d'oppositions par rapport à l'horizon de décision.
Le pipeline garde sa propre règle ``mtf_aligned`` (``market_data.timeframes.HIGHER_TIMEFRAME``, inchangée).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from typing import Any, Mapping, Sequence

from app.agents import ichimoku_agent, rvol_agent
from app.agents.types import Direction
from app.indicators.ichimoku import Candle, IchimokuParams
from app.indicators.registry import REGISTRY
from app.indicators.rvol import RvolParams
from app.market_data.quality import closed_candles
from app.market_data.timeframes import HIGHER_TIMEFRAME
from app.screener.timing import compute_signal_timing

MTF_VERSION = "mtf-matrix-v1"
MTF_HORIZONS: tuple[str, ...] = ("1h", "4h", "1d", "1w")
# Table propre à la matrice : ``TF_SECONDS`` n'a pas de 1w (ajouter la clé élargirait les timeframes
# acceptés par plusieurs routes). Les bougies 1w Binance ouvrent le lundi 00:00 UTC (timing.py l'ancre).
HORIZON_SECONDS: dict[str, int] = {"15m": 900, "1h": 3600, "4h": 14400, "1d": 86400, "1w": 604800}
METHOD = "Ichimoku 9/26/52 — direction de la dernière bougie close"

FR_DIRECTION = {"LONG": "haussier", "SHORT": "baissier", "NEUTRAL": "neutre"}
FR_TREND = {"LONG": "haussière", "SHORT": "baissière", "NEUTRAL": "neutre"}  # « tendance » (féminin)
FR_UNAVAILABLE = {
    "insufficient_history": "historique insuffisant",
    "provider_no_timeframe": "non servi par la source",
    "provider_credit_budget": "non demandé, budget de crédits",
    "provider_error": "erreur de la source",
    "no_data": "aucune donnée",
    "unsupported_timeframe": "horizon non pris en charge",
}
FR_STATE = {"CONFIRMED": "confirmé", "LATE": "en retard", "STALE": "périmé", "UNAVAILABLE": "indisponible"}


class HorizonState(str, Enum):
    CONFIRMED = "CONFIRMED"
    LATE = "LATE"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class Relation(str, Enum):
    SELF = "self"
    ALIGNED = "aligned"
    OPPOSED = "opposed"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class HorizonReading:
    timeframe: str
    role: str  # decision | parent | context
    state: HorizonState
    direction: str | None = None  # LONG | SHORT | NEUTRAL
    score: float | None = None
    method: str = METHOD
    bar_open: int | None = None
    bar_close: int | None = None
    lag_bars: int | None = None
    reasons: list[str] = field(default_factory=list)
    unavailable_reason: str | None = None
    provisional_direction: str | None = None
    provisional_bar_open: int | None = None
    rvol: float | None = None
    rvol_level: str | None = None
    atr: float | None = None
    atr_regime: str | None = None
    adx: float | None = None
    adx_strength: str | None = None
    relation: Relation = Relation.UNKNOWN

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["state"] = self.state.value
        out["relation"] = self.relation.value
        return out


@dataclass(frozen=True)
class MtfSummary:
    decision_tf: str
    decision_direction: str | None
    parent_tf: str | None
    parent_relation: str
    aligned: list[str]
    opposed: list[str]
    neutral: list[str]
    unknown: list[str]
    n_available: int
    n_horizons: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MtfMatrix:
    symbol: str
    decision_tf: str
    computed_at: int
    horizons: list[HorizonReading]
    summary: MtfSummary
    venue: str | None = None
    version: str = MTF_VERSION

    def horizon(self, tf: str) -> HorizonReading | None:
        return next((h for h in self.horizons if h.timeframe == tf), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "symbol": self.symbol,
            "venue": self.venue,
            "decision_tf": self.decision_tf,
            "computed_at": self.computed_at,
            "method": METHOD,
            "horizons": [h.to_dict() for h in self.horizons],
            "summary": self.summary.to_dict(),
            "observe_only": True,
            "used_by_decision": False,
        }


def horizons_for(decision_tf: str) -> list[str]:
    """Horizons affichés, du plus court au plus long ; l'horizon de décision est toujours inclus."""
    tfs = set(MTF_HORIZONS) | ({decision_tf} if decision_tf in HORIZON_SECONDS else set())
    return sorted(tfs, key=lambda t: HORIZON_SECONDS[t])


def _enum(v: Any) -> Any:
    return getattr(v, "value", v)


def _unavailable(tf: str, role: str, reason: str, **kw: Any) -> HorizonReading:
    return HorizonReading(timeframe=tf, role=role, state=HorizonState.UNAVAILABLE, unavailable_reason=reason, **kw)


def read_horizon(
    candles: Sequence[Candle] | None,
    timeframe: str,
    *,
    now: int,
    role: str = "context",
    include_provisional: bool = True,
    unavailable_reason: str | None = None,
    ichi_params: IchimokuParams = IchimokuParams(),
    rvol_params: RvolParams = RvolParams(),
) -> HorizonReading:
    """Lecture d'un horizon à l'instant ``now``. ``candles`` = série brute du provider (la bougie en
    formation éventuelle est retirée ici, jamais utilisée pour ``direction``)."""
    tf_s = HORIZON_SECONDS.get(timeframe)
    if tf_s is None:
        return _unavailable(timeframe, role, "unsupported_timeframe")
    if not candles:
        return _unavailable(timeframe, role, unavailable_reason or "no_data")
    raw = [c for c in candles if c.time <= now]  # rien après l'instant de lecture (replay as_of)
    closed = closed_candles(raw, tf_s, now)
    if len(closed) < 2:
        return _unavailable(timeframe, role, "insufficient_history")
    out = ichimoku_agent.analyze(closed, ichi_params)[-1]
    last = closed[-1]
    timing = compute_signal_timing(closed, tf_s, now, raw[-1].close, timeframe, True)
    times = dict(bar_open=int(last.time), bar_close=int(last.time) + tf_s, lag_bars=int(timing.lag_bars))
    score = out.metadata.get("score")
    if score is None or out.metadata.get("cloud_top") is None:
        # Ichimoku incomplet : le nuage demande 52 + 26 bougies closes. L'agent renvoie alors un score
        # partiel (NEUTRAL) qu'on ne présente pas comme une tendance (ex. 1w d'un actif listé récemment).
        return _unavailable(timeframe, role, "insufficient_history", **times)
    if timing.stale:
        state = HorizonState.STALE
    elif timing.data_late:
        state = HorizonState.LATE
    else:
        state = HorizonState.CONFIRMED

    provisional_direction = provisional_open = None
    if include_provisional and len(raw) > len(closed) and raw[-1].time + tf_s > now:
        prov = ichimoku_agent.analyze(raw, ichi_params)[-1]
        provisional_direction, provisional_open = _enum(prov.direction), int(raw[-1].time)

    rv = rvol_agent.analyze(closed, rvol_params)[-1].metadata
    ctx = REGISTRY.compute_many(["atr", "adx"], closed)
    atr_s, adx_s = ctx["atr"][-1], ctx["adx"][-1]
    return HorizonReading(
        timeframe=timeframe,
        role=role,
        state=state,
        direction=_enum(out.direction),
        score=float(score),
        reasons=list(out.reasons),
        provisional_direction=provisional_direction,
        provisional_bar_open=provisional_open,
        rvol=rv.get("rvol"),
        rvol_level=_enum(rv.get("anomaly_level")),
        atr=getattr(atr_s, "atr", None),
        atr_regime=_enum(getattr(atr_s, "regime", None)),
        adx=getattr(adx_s, "adx", None),
        adx_strength=_enum(getattr(adx_s, "strength", None)),
        **times,
    )


def _relation(decision: HorizonReading, other: HorizonReading) -> Relation:
    if other.timeframe == decision.timeframe:
        return Relation.SELF
    usable = (HorizonState.CONFIRMED, HorizonState.LATE)
    if decision.state not in usable or other.state not in usable:
        return Relation.UNKNOWN
    if Direction.NEUTRAL.value in (decision.direction, other.direction):
        return Relation.NEUTRAL
    return Relation.ALIGNED if decision.direction == other.direction else Relation.OPPOSED


def compute_mtf_matrix(
    series: Mapping[str, Sequence[Candle] | None],
    *,
    symbol: str,
    decision_tf: str,
    now: int,
    venue: str | None = None,
    unavailable_reasons: Mapping[str, str] | None = None,
    include_provisional: bool = True,
    ichi_params: IchimokuParams = IchimokuParams(),
) -> MtfMatrix:
    """Matrice complète. ``series[tf]`` = bougies brutes de l'horizon (absent / None = indisponible,
    avec la raison de ``unavailable_reasons[tf]``)."""
    reasons = dict(unavailable_reasons or {})
    parent_tf = HIGHER_TIMEFRAME.get(decision_tf)
    readings = []
    for tf in horizons_for(decision_tf):
        role = "decision" if tf == decision_tf else "parent" if tf == parent_tf else "context"
        readings.append(
            read_horizon(
                series.get(tf), tf, now=now, role=role, include_provisional=include_provisional,
                unavailable_reason=reasons.get(tf), ichi_params=ichi_params,
            )
        )
    decision = next((r for r in readings if r.timeframe == decision_tf), None)
    if decision is None:
        decision = _unavailable(decision_tf, "decision", "unsupported_timeframe")
    readings = [replace(r, relation=_relation(decision, r)) for r in readings]
    others = [r for r in readings if r.relation != Relation.SELF]
    by = {rel: [r.timeframe for r in others if r.relation == rel] for rel in Relation}
    parent = next((r for r in readings if r.timeframe == parent_tf), None)
    summary = MtfSummary(
        decision_tf=decision_tf,
        decision_direction=decision.direction if decision.state != HorizonState.UNAVAILABLE else None,
        parent_tf=parent_tf,
        parent_relation=(parent.relation.value if parent is not None else Relation.UNKNOWN.value),
        aligned=by[Relation.ALIGNED],
        opposed=by[Relation.OPPOSED],
        neutral=by[Relation.NEUTRAL],
        unknown=by[Relation.UNKNOWN],
        n_available=sum(1 for r in readings if r.state != HorizonState.UNAVAILABLE),
        n_horizons=len(readings),
    )
    return MtfMatrix(symbol=symbol.upper(), decision_tf=decision_tf, computed_at=int(now), horizons=readings,
                     summary=summary, venue=venue)


# --- restitution en phrase (déterministe) ----------------------------------------------------------

_STAGE_FR = {
    "direction": "Direction",
    "participation": "Participation",
    "structure": "Structure",
    "location": "Emplacement",
    "regime": "Régime",
}
_STATUS_FR = {"fail": "en échec", "watch": "en surveillance", "pending": "non calculée"}
_DECISION_FR = {
    "BUY": "entrée confirmée par le pipeline",
    "SELL": "signal de vente du pipeline",
    "WATCH": "entrée non confirmée",
    "NO_TRADE": "pas de trade",
}


def _fmt_utc(ts: int | None) -> str:
    from datetime import datetime, timezone

    if ts is None:
        return "?"
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%d/%m %H:%M UTC")


def _fmt_num(v: float | None, digits: int = 2) -> str:
    return "?" if v is None else f"{v:.{digits}f}".replace(".", ",")


def _horizon_phrase(r: HorizonReading) -> str:
    if r.state == HorizonState.UNAVAILABLE:
        reason = FR_UNAVAILABLE.get(r.unavailable_reason or "", r.unavailable_reason or "?")
        return f"{r.timeframe} indisponible ({reason})"
    text = f"{r.timeframe} {FR_DIRECTION.get(r.direction or '', r.direction or '?')}"
    if r.state != HorizonState.CONFIRMED:
        text += f" ({FR_STATE[r.state.value]})"
    return text


def describe(matrix: MtfMatrix, pipeline: Mapping[str, Any] | None = None) -> str:
    """Phrase du panneau. La partie décision reprend les étapes et codes **réels** du pipeline : le
    panneau ne peut pas contredire le moteur. Exemple : « Tendance 1h haussière (bougie close 14:00 UTC),
    contexte 4h baissier, 1d baissier, 1w haussier ; RVOL 1h 0,62×, ATR normal : entrée non confirmée
    (Structure en surveillance : mtf_opposed ; Participation en échec : rvol_low). »"""
    d = matrix.horizon(matrix.decision_tf)
    if d is None or d.state == HorizonState.UNAVAILABLE:
        head = f"Tendance {matrix.decision_tf} indisponible"
    else:
        head = (
            f"Tendance {matrix.decision_tf} {FR_TREND.get(d.direction or '', '?')}"
            f" (bougie close {_fmt_utc(d.bar_close)}"
            + (f", {FR_STATE[d.state.value]}" if d.state != HorizonState.CONFIRMED else "")
            + ")"
        )
    others = [_horizon_phrase(r) for r in matrix.horizons if r.timeframe != matrix.decision_tf]
    text = head + (", contexte " + ", ".join(others) if others else "")
    if d is not None and d.state != HorizonState.UNAVAILABLE:
        text += f" ; RVOL {matrix.decision_tf} {_fmt_num(d.rvol)}×"
        if d.atr_regime:
            text += f", ATR {d.atr_regime.lower()}"
    if pipeline:
        decision = str(pipeline.get("decision") or "")
        blocking = [
            f"{_STAGE_FR.get(str(s.get('id')), s.get('id'))} {_STATUS_FR[str(s.get('status'))]}"
            + (f" : {', '.join(s.get('codes') or [])}" if s.get("codes") else "")
            for s in (pipeline.get("stages") or [])
            if str(s.get("status")) in ("fail", "watch") and str(s.get("id")) != "direction"
        ]
        text += f" : {_DECISION_FR.get(decision, decision or '?')}"
        if blocking and decision != "BUY":
            text += " (" + " ; ".join(blocking) + ")"
    return text + "."


def portfolio_reading(
    pipeline: Mapping[str, Any] | None,
    *,
    timeframe: str,
    profile: Mapping[str, Any] | None,
    open_long_on_tf: bool | None = None,
) -> str:
    """Ce que le portefeuille de référence fait de ce signal (séparé du signal analytique).

    Règle réelle (``paper/engine.py``, ``exit_mode=direction``) : un lot long automatique se ferme sur
    stop / objectif, ou quand la **direction Ichimoku** de la dernière bougie close n'est plus LONG
    (SHORT **ou** NEUTRAL) ; un WATCH / NO_TRADE seul ne le ferme pas. ``allow_short=False`` : un SELL
    n'ouvre jamais de short."""
    if not pipeline:
        return "Lecture portefeuille indisponible (pipeline non calculé)."
    prof = profile or {}
    decision = str(pipeline.get("decision") or "")
    direction = str(pipeline.get("direction") or "")
    auto_tfs = tuple(prof.get("auto_timeframes") or ("1h",))
    allow_short = bool(prof.get("allow_short", False))
    auto = timeframe in auto_tfs
    parts: list[str] = []
    if decision == "BUY":
        parts.append(
            "Achat : ouverture longue possible si les règles de risque l'autorisent"
            if auto
            else f"Achat : pas d'ouverture automatique en {timeframe} (auto : {', '.join(auto_tfs)} seulement)"
        )
    elif decision == "SELL" and not allow_short:
        parts.append("Vente : aucune ouverture short (short désactivé)")
    else:
        parts.append("Aucune nouvelle entrée")
    if prof.get("exit_mode") == "direction" and auto:
        if direction == "LONG":
            held = "conservée" if decision != "BUY" else "inchangée"
            parts.append(f"une position longue automatique en {timeframe} serait {held} (direction toujours LONG)")
        else:
            verb = "sera fermée au prochain cycle" if open_long_on_tf else "serait fermée s'il y en a une"
            if open_long_on_tf is False:
                parts.append(f"aucune position longue automatique en {timeframe} à fermer")
            else:
                parts.append(f"une position longue automatique en {timeframe} {verb} (direction {direction})")
    return " ; ".join(parts) + "."
