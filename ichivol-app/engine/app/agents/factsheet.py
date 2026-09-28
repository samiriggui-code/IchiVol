"""AG-FS0 — FactSheet : les faits moteur d'un (symbole, timeframe), avec provenance.

Spec : docs/AG-FS0-FACTSHEET-SPEC.md. Déterministe, aucun LLM, lecture seule.
Le LLM (Eve) ne cite que ces faits ; le validateur serveur rejette tout chiffre
qui n'y figure pas. Une donnée absente est un fait (status != ok), jamais omise.

Sources réutilisées sans recalcul : fiches AG-S1 (``build_analyst_cards``),
décision du pipeline (``scan_symbol`` → ``detail_dict``, barres closes),
état paper du portefeuille de référence, prochain événement macro « High ».
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Sequence

logger = logging.getLogger(__name__)

SCHEMA = "ichivol.factsheet.v1"
MAX_FACTS = 60
_VALIDATION_NA = "N/A"


def display_value(value: Any) -> str | None:
    """Forme exacte que le LLM a le droit de citer (format FR, décimales du moteur)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "oui" if value else "non"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value != value:  # NaN
            return None
        mag = abs(value)
        decimals = 2 if mag >= 100 else 4 if mag >= 1 else 6
        text = f"{value:.{decimals}f}".rstrip("0").rstrip(".")
        return text.replace(".", ",") if text not in ("-0", "") else "0"
    return str(value)


def _fact(
    fid: str,
    *,
    engine: str,
    field: str,
    value: Any,
    timeframe: str,
    as_of: int | None,
    known_at: int | None,
    source: str,
    validation_status: str,
    decision_role: str,
    status: str | None = None,
    reason: str | None = None,
    unit: str | None = None,
) -> dict[str, Any]:
    if isinstance(value, float) and value != value:
        value = None
    st = status or ("ok" if value is not None else "unavailable")
    out: dict[str, Any] = {
        "id": fid,
        "engine": engine,
        "field": field,
        "value": value,
        "display": display_value(value),
        "unit": unit,
        "timeframe": timeframe,
        "as_of": as_of,
        "known_at": known_at,
        "source": source,
        "status": st,
        "validation_status": validation_status,
        "decision_role": decision_role,
    }
    if st != "ok":
        out["reason"] = reason or "value_missing"
    return out


def _scalar(v: Any) -> bool:
    return v is None or isinstance(v, (bool, int, float, str))


# Champs retenus par fiche (budget ≤ 60 faits). Chemins "a.b" = un niveau d'imbrication.
# Fiche absente de la table → ses 4 premiers champs scalaires (ordre alphabétique).
CARD_FIELDS: dict[str, tuple[str, ...]] = {
    "ichimoku": ("direction", "price_vs_kumo", "tk_cross", "score"),
    "mtf_direction": ("direction", "higher_tf"),
    "rvol": ("rvol", "anomaly_level", "percentile"),
    "cvd": ("bias", "delta", "rolling_delta"),
    "oi_funding": ("oi_trend", "funding_rate", "funding_bias"),
    "structure": ("bias", "bos", "last_swing_high", "last_swing_low"),
    "fvg": ("active_count",),
    "impulse": ("fibonacci.displacement_atr", "fibonacci.confluence"),
    "location": ("node_type", "poc", "vah", "val", "vwap"),
    "atr": ("atr", "regime", "percentile"),
    "adx": ("adx", "strength"),
    "donchian": ("upper", "lower", "breakout"),
    "cycle": ("regime",),
}
_DEFAULT_CARD_FIELDS = 4


def _card_field_paths(feature: str, value: dict[str, Any]) -> list[str]:
    if feature in CARD_FIELDS:
        return list(CARD_FIELDS[feature])
    return [k for k in sorted(value) if _scalar(value[k])][:_DEFAULT_CARD_FIELDS]


def _get_path(value: dict[str, Any], path: str) -> Any:
    cur: Any = value
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur if _scalar(cur) else None


def facts_from_cards(cards: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Une fiche AG-S1 → ``<feature>.state`` + ses champs retenus (``CARD_FIELDS``)."""
    facts: list[dict[str, Any]] = []
    for card in cards:
        feat = str(card["feature"])
        common = dict(
            engine=feat,
            timeframe=str(card["timeframe"]),
            as_of=card.get("as_of"),
            known_at=card.get("known_at"),
            source="engine",
            validation_status=str(card.get("validation_status") or "NON_VALIDE"),
            decision_role=str(card.get("decision_role") or ""),
        )
        value = card.get("value") if isinstance(card.get("value"), dict) else {}
        fields = [(path, _get_path(value, path)) for path in _card_field_paths(feat, value)]
        # `state` n'est ajouté que s'il n'est pas déjà la valeur d'un champ retenu (pas de doublon).
        if card.get("state") not in {v for _, v in fields if v is not None}:
            facts.append(_fact(f"{feat}.state", field="state", value=card.get("state"), **common))
        for path, v in fields:
            facts.append(_fact(f"{feat}.{path}", field=path, value=v, **common))
    return facts


def facts_from_pipeline(
    detail: dict[str, Any] | None,
    *,
    timeframe: str,
    as_of: int | None,
    reason: str | None = None,
    now: int | None = None,
) -> list[dict[str, Any]]:
    """Verdict et étapes du pipeline (source de vérité de Décisions). Tous NON_VALIDE (VP3).

    ``price.live`` est le dernier prix traité (barre en cours) : horodaté à ``now`` (E1, revue #171),
    pas à la clôture de barre. ``pipeline.blocking_stages`` = étapes en échec (faits relationnels, V8).
    """
    live = dict(engine="provider", timeframe=timeframe, as_of=None, known_at=now, validation_status="NON_VALIDE",
                decision_role="context")
    common = dict(
        engine="pipeline",
        timeframe=timeframe,
        as_of=as_of,
        known_at=as_of,
        validation_status="NON_VALIDE",
        decision_role="decision",
    )
    if detail is None:
        why = reason or "pipeline_unavailable"
        return [
            _fact("pipeline.decision", field="decision", value=None, source="engine", status="unavailable",
                  reason=why, **common),
            _fact("price.live", field="price", value=None, source="provider", status="unavailable", reason=why,
                  **live),
        ]
    pipeline = detail.get("pipeline") or {}
    facts = [
        _fact("pipeline.decision", field="decision", value=pipeline.get("decision"), source="engine", **common),
        _fact("pipeline.direction", field="direction", value=pipeline.get("direction") or detail.get("direction"),
              source="engine", **common),
        _fact("price.live", field="price", value=detail.get("price"), source="provider", **live),
    ]
    stages = [s for s in (pipeline.get("stages") or []) if s.get("id")]
    failing = [str(s["id"]) for s in stages if s.get("status") == "fail"]
    facts.append(
        _fact("pipeline.blocking_stages", field="blocking_stages", value=", ".join(failing) if failing else "aucune",
              source="engine", **common)
    )
    for stage in stages:
        sid = str(stage["id"])
        facts.append(
            _fact(f"pipeline.stage.{sid}.status", field=f"stage.{sid}.status", value=stage.get("status"),
                  source="engine", **common)
        )
    return facts


def price_vs_value_area(price: float | None, location: dict[str, Any] | None) -> str | None:
    """Position du prix live par rapport à la value area (VAL ≤ POC ≤ VAH). Relation pré-calculée (V8)."""
    if price is None or not isinstance(location, dict):
        return None
    poc, vah, val = location.get("poc"), location.get("vah"), location.get("val")
    if not all(isinstance(x, (int, float)) for x in (poc, vah, val)):
        return None
    if price > vah:
        return "above_vah"
    if price >= poc:
        return "between_poc_vah"
    if price >= val:
        return "between_val_poc"
    return "below_val"


def facts_derived(
    detail: dict[str, Any] | None, cards: Sequence[dict[str, Any]], *, timeframe: str, now: int | None
) -> list[dict[str, Any]]:
    """Faits relationnels calculés côté moteur, pour que le LLM n'ait pas à comparer lui-même."""
    loc = next((c for c in cards if c.get("feature") == "location"), None)
    price = detail.get("price") if detail else None
    rel = price_vs_value_area(price, (loc or {}).get("value"))
    return [
        _fact("location.price_vs_value_area", engine="location", field="price_vs_value_area", value=rel,
              timeframe=timeframe, as_of=None, known_at=now, source="engine", validation_status="NON_VALIDE",
              decision_role=str((loc or {}).get("decision_role") or "context"),
              reason=None if rel is not None else "price_or_value_area_missing")
    ]


def facts_from_paper(
    position: dict[str, Any] | None,
    lock: dict[str, Any] | None,
    *,
    timeframe: str,
    as_of: int | None,
    reason: str | None = None,
) -> list[dict[str, Any]]:
    """Position ouverte du portefeuille de référence sur ce symbole + verrous de risque."""
    common = dict(
        engine="paper",
        timeframe=timeframe,
        as_of=as_of,
        known_at=as_of,
        source="paper",
        validation_status=_VALIDATION_NA,
        decision_role="context",
    )
    if lock is None:
        why = reason or "paper_unavailable"
        return [_fact("paper.position.open", field="position.open", value=None, status="unavailable",
                      reason=why, **common)]
    facts = [_fact("paper.position.open", field="position.open", value=position is not None, **common)]
    if position is not None:
        for key in ("timeframe", "direction", "entry_price", "stop_price", "take_profit_price", "qty"):
            facts.append(_fact(f"paper.position.{key}", field=f"position.{key}", value=position.get(key), **common))
    for key in ("entries_blocked", "kill_switch_armed", "daily_loss_locked"):
        facts.append(_fact(f"paper.lock.{key}", field=f"lock.{key}", value=bool(lock.get(key)), **common))
    return facts


def _parse_iso(s: str) -> int | None:
    try:
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
    except (TypeError, ValueError):
        return None


def facts_from_calendar(
    events: Sequence[Any] | None, *, now: int, timeframe: str, reason: str | None = None
) -> list[dict[str, Any]]:
    """Prochain événement macro d'impact High (flux hebdo). Absence d'événement = valeur nulle, statut ok."""
    common = dict(
        engine="calendar",
        timeframe=timeframe,
        as_of=now,
        known_at=now,
        source="calendar",
        validation_status=_VALIDATION_NA,
        decision_role="context",
    )
    if events is None:
        return [_fact("calendar.next_high.title", field="next_high.title", value=None, status="unavailable",
                      reason=reason or "calendar_unavailable", **common)]
    upcoming = sorted(
        [
            (t, e)
            for e in events
            if str(getattr(e, "impact", "")) == "High"
            and (t := _parse_iso(str(getattr(e, "date", "")))) is not None
            and t >= now
        ],
        key=lambda te: (te[0], str(getattr(te[1], "title", ""))),
    )
    if not upcoming:
        return [_fact("calendar.next_high.title", field="next_high.title", value=None, status="ok", **common)]
    t, ev = upcoming[0]
    return [
        _fact("calendar.next_high.title", field="next_high.title", value=str(ev.title), **common),
        _fact("calendar.next_high.country", field="next_high.country", value=str(ev.country), **common),
        _fact("calendar.next_high.time_utc", field="next_high.time_utc",
              value=datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), **common),
        _fact("calendar.next_high.minutes_to", field="next_high.minutes_to", value=int((t - now) // 60),
              unit="min", **common),
    ]


def assemble(
    *,
    symbol: str,
    timeframe: str,
    as_of: int | None,
    fact_groups: Sequence[Sequence[dict[str, Any]]],
    engine_version: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Assemble, plafonne à MAX_FACTS (ordre des groupes = priorité) et identifie de façon déterministe."""
    facts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in fact_groups:
        for f in group:
            if f["id"] in seen:
                continue
            seen.add(f["id"])
            facts.append(f)
    truncated = max(0, len(facts) - MAX_FACTS)
    cut = facts[MAX_FACTS:]
    facts = facts[:MAX_FACTS]
    core = {"schema": SCHEMA, "symbol": symbol.upper(), "timeframe": timeframe, "as_of": as_of, "facts": facts}
    digest = hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()
    return {
        **core,
        "factsheet_id": digest,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "engine_version": engine_version,
        "truncated": truncated,
        "missing": [{"id": f["id"], "reason": f.get("reason")} for f in facts if f["status"] != "ok"]
        + [{"id": f["id"], "reason": "truncated"} for f in cut],
        "observe_only": True,
        "used_by_decision": False,
    }


# --- collecte (I/O) ---------------------------------------------------------------------------


def _paper_state(symbol: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    from sqlalchemy import select

    from app.db.models import PaperPortfolio, PaperPosition
    from app.db.session import SessionLocal
    from app.paper.kill_switch import lock_status
    from app.paper.portfolio import BASELINE_CODE

    session = SessionLocal()
    try:
        pf = session.execute(select(PaperPortfolio).where(PaperPortfolio.code == BASELINE_CODE)).scalar_one_or_none()
        if pf is None:
            return None, None
        pos = session.execute(
            select(PaperPosition)
            .where(PaperPosition.portfolio_id == pf.id, PaperPosition.symbol == symbol, PaperPosition.status == "OPEN")
            .order_by(PaperPosition.entry_time.desc())
        ).scalars().first()
        position = None
        if pos is not None:
            position = {k: getattr(pos, k) for k in
                        ("timeframe", "direction", "entry_price", "stop_price", "take_profit_price", "qty")}
        return position, lock_status(pf)
    finally:
        session.close()


def build_factsheet(
    symbol: str,
    timeframe: str,
    *,
    as_of: int | None = None,
    now: int | None = None,
    x_twelve_data_key: str | None = None,
) -> dict[str, Any]:
    """FactSheet live (``as_of=None``) ou historique (fiches seulement ; le reste marqué indisponible)."""
    from app.agents.analyst_cards import ENGINE_VERSION, build_analyst_cards

    sym = symbol.upper()
    now_s = int(time.time()) if now is None else int(now)
    cards_payload = build_analyst_cards(sym, timeframe, as_of=as_of, now=now, x_twelve_data_key=x_twelve_data_key)
    bar_as_of = cards_payload.get("as_of")
    cards = cards_payload.get("cards") or []

    historical = as_of is not None
    detail: dict[str, Any] | None = None
    pipe_reason = "historical_as_of_not_supported" if historical else None
    if not historical:
        try:
            from app.api.serializers import detail_dict
            from app.screener.service import scan_symbol

            detail = detail_dict(scan_symbol(sym, timeframe=timeframe))
        except Exception:
            logger.warning("factsheet: pipeline unavailable for %s %s", sym, timeframe, exc_info=True)
            pipe_reason = "pipeline_error"

    position = lock = None
    paper_reason = "historical_as_of_not_supported" if historical else None
    if not historical:
        try:
            position, lock = _paper_state(sym)
            if lock is None:
                paper_reason = "baseline_portfolio_missing"
        except Exception:
            logger.warning("factsheet: paper state unavailable", exc_info=True)
            paper_reason = "paper_error"

    events = None
    cal_reason = "historical_as_of_not_supported" if historical else None
    if not historical:
        try:
            from app.context.calendar import fetch_calendar_events

            events = fetch_calendar_events() or None  # l'adaptateur renvoie [] en cas de panne
            if events is None:
                cal_reason = "calendar_empty_or_unavailable"
        except Exception:
            cal_reason = "calendar_error"

    return assemble(
        symbol=sym,
        timeframe=timeframe,
        as_of=bar_as_of,
        fact_groups=[
            facts_from_pipeline(detail, timeframe=timeframe, as_of=bar_as_of, reason=pipe_reason, now=now_s),
            facts_derived(detail, cards, timeframe=timeframe, now=now_s),
            facts_from_paper(position, lock, timeframe=timeframe, as_of=bar_as_of, reason=paper_reason),
            facts_from_calendar(events, now=now_s, timeframe=timeframe, reason=cal_reason),
            facts_from_cards(cards),
        ],
        engine_version=f"fs0-v1+{ENGINE_VERSION}",
    )
