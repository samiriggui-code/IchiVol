"""AW1 — « Pourquoi ? » : explication déterministe d'un ChartObject moteur.

Observe-only. Aucune valeur n'est inventée : chaque fait renvoie au champ
Python d'où il vient (``field``). Le LLM (Eve) peut reformuler ces faits,
jamais en ajouter.

Source de vérité temporelle : le replay walk-forward (CI-R1/R8). ``known_at``
est la première barre où le ``lineage_key`` apparaît dans la fenêtre rejouée ;
s'il apparaît dès la première barre de la fenêtre, ce n'est qu'une borne
haute (l'objet existait peut-être avant) → ``known_at_is_upper_bound``.
"""

from __future__ import annotations

from typing import Any

from app.indicators.registry import REGISTRY

EXPLAIN_VERSION = "aw1-v1"

# Validation VP : aucun type d'objet n'a encore été mesuré par le programme VP.
# À brancher sur les rapports VP (VP5/VP6) quand ils existeront — jamais à la main.
_VALIDATION = {
    "status": "NON_VALIDE",
    "label": "Non validé",
    "note": (
        "Aucune étude du programme de validation (VP) n'a encore mesuré l'apport "
        "de ce type d'objet hors échantillon et après coûts."
    ),
}

# (layer, origin.kind[, event_type]) → feature registre, engine, lecture pipeline.
_ENGINES: dict[str, dict[str, Any]] = {
    "structure_zone": {
        "feature": None,
        "engine": "app/structure (consensus de détecteurs S/R)",
        "pipeline": "Non lu par le pipeline de décision (annotation graphique).",
    },
    "structure_trendline": {
        "feature": None,
        "engine": "app/structure (consensus de détecteurs trendlines)",
        "pipeline": "Non lu par le pipeline de décision (annotation graphique).",
    },
    "structure_event:BOS": {
        "feature": "structure",
        "engine": "indicators/structure (BOS T9b)",
        "pipeline": (
            "Le stage « structure » du pipeline lit le BOS de la dernière barre "
            "clôturée uniquement ; un BOS plus ancien ne vote pas."
        ),
    },
    "structure_event:CHOCH": {
        "feature": "structure",
        "maturity_override": "EXPERIMENTAL",
        "engine": "indicators/structure (CHoCH T9b)",
        "pipeline": "Non lu par le pipeline de décision (CHoCH EXPERIMENTAL, Lab).",
    },
    "fvg": {
        "feature": "fvg",
        "engine": "indicators/fvg (T9d)",
        "pipeline": "Non lu par le pipeline de décision (FVG EXPERIMENTAL, Lab).",
    },
    "fibonacci": {
        "feature": "impulse",
        "engine": "fibonacci/context ancré sur indicators/impulse (T9c/T9e)",
        "pipeline": "Non lu par le pipeline de décision (Fib EXPERIMENTAL, Lab).",
    },
}

# Champs origin → libellé FR. Seuls les champs présents sont rapportés.
_ORIGIN_FACTS: tuple[tuple[str, str], ...] = (
    ("detector", "Détecteur"),
    ("sources", "Détecteurs en accord"),
    ("score", "Score du consensus"),
    ("touch_count", "Touches"),
    ("event_type", "Événement"),
    ("direction", "Direction"),
    ("break_quality", "Qualité de cassure"),
    ("level", "Niveau cassé"),
    ("displacement_atr", "Déplacement (× ATR)"),
    ("rvol", "RVOL à l'événement"),
    ("status", "Statut"),
    ("fill_ratio", "Taux de remplissage"),
    ("gap_atr", "Taille du gap (× ATR)"),
    ("impulse", "Impulsion"),
    ("anchor_source", "Ancrage"),
    ("ratio", "Ratio"),
    ("swing_low", "Swing bas"),
    ("swing_high", "Swing haut"),
)


class ExplainError(ValueError):
    """Objet introuvable ou paramètres invalides (→ HTTP 404)."""


def _engine_key(obj: dict[str, Any]) -> str:
    origin = obj.get("origin") or {}
    kind = str(origin.get("kind") or "")
    if kind == "structure_event":
        ev = str(origin.get("event_type") or "").upper()
        return f"structure_event:{ev}"
    return kind


def _maturity(meta: dict[str, Any] | None) -> dict[str, Any]:
    if meta is None:
        return {"status": "INCONNU", "feature": None, "field": None}
    feature = meta.get("feature")
    if feature is None:
        return {"status": "HORS_REGISTRE", "feature": None, "field": None}
    try:
        status = REGISTRY.get(feature).status.value
    except KeyError:
        return {"status": "INCONNU", "feature": feature, "field": None}
    if meta.get("maturity_override"):
        status = str(meta["maturity_override"])
    return {"status": status, "feature": feature, "field": f"REGISTRY[{feature}].status"}


def _find(objects: list[dict[str, Any]], *, object_id: str | None, lineage_key: str | None):
    if object_id:
        for o in objects:
            if str(o.get("id")) == object_id:
                return o
    if lineage_key:
        for o in objects:
            if str((o.get("origin") or {}).get("lineage_key") or "") == lineage_key:
                return o
    return None


def _anchor_time(obj: dict[str, Any]) -> int | None:
    times = [int(p["time"]) for p in obj.get("points") or [] if p.get("time") is not None]
    origin = obj.get("origin") or {}
    for k in ("swing_time",):
        if origin.get(k) is not None:
            times.append(int(origin[k]))
    return min(times) if times else None


def _reference_price(obj: dict[str, Any], *, at: int) -> tuple[float | None, str | None]:
    """Prix de référence de l'objet à ``at`` + le champ source."""
    lo, hi = obj.get("price_low"), obj.get("price_high")
    if lo is not None and hi is not None:
        return (float(lo) + float(hi)) / 2.0, "mid(price_low, price_high)"
    origin = obj.get("origin") or {}
    if origin.get("level") is not None:
        return float(origin["level"]), "origin.level"
    pts = obj.get("points") or []
    if obj.get("type") in ("trend_line", "ray") and len(pts) >= 2:
        (t0, p0), (t1, p1) = (pts[0]["time"], pts[0]["price"]), (pts[1]["time"], pts[1]["price"])
        if t1 != t0:
            return float(p0) + (float(p1) - float(p0)) * (at - t0) / (t1 - t0), "points (droite prolongée à as_of)"
    if pts:
        return float(pts[0]["price"]), "points[0].price"
    return None, None


def _fmt(v: Any) -> Any:
    if isinstance(v, float):
        return round(v, 6)
    return v


def explain_from_pack(
    pack: dict[str, Any],
    *,
    object_id: str | None = None,
    lineage_key: str | None = None,
) -> dict[str, Any]:
    """Explique un objet d'un pack replay walk-forward. Pure (pas d'I/O)."""
    if not object_id and not lineage_key:
        raise ExplainError("object_id_or_lineage_key_required")

    objects = list(pack.get("objects") or [])
    obj = _find(objects, object_id=object_id, lineage_key=lineage_key)
    if obj is None:
        # L'id change quand les coordonnées bougent : retrouver le lineage via les frames.
        for frame in reversed(pack.get("frames") or []):
            hit = _find(frame.get("objects") or [], object_id=object_id, lineage_key=None)
            if hit is not None:
                lk = (hit.get("origin") or {}).get("lineage_key")
                obj = _find(objects, object_id=None, lineage_key=lk) if lk else None
                break
    if obj is None:
        raise ExplainError(f"object_not_found:{object_id or lineage_key}")
    if obj.get("source") != "engine":
        raise ExplainError(f"not_an_engine_object:{obj.get('source')}")

    origin = obj.get("origin") or {}
    as_of = int(pack["as_of"])
    tf_sec = int((pack.get("replay") or {}).get("bar_seconds") or 3600)
    window_from = pack.get("from")
    known_at = origin.get("known_at")
    upper_bound = known_at is not None and window_from is not None and int(known_at) <= int(window_from)
    anchor = _anchor_time(obj)
    lag_bars = None
    if known_at is not None and anchor is not None and not upper_bound:
        lag_bars = max(0, round((int(known_at) - int(anchor)) / tf_sec))

    meta = _ENGINES.get(_engine_key(obj))
    maturity = _maturity(meta)

    facts: list[dict[str, Any]] = []
    for key, label in _ORIGIN_FACTS:
        if origin.get(key) is not None:
            facts.append({"key": key, "label": label, "value": _fmt(origin[key]), "field": f"origin.{key}"})
    if obj.get("price_low") is not None and obj.get("price_high") is not None:
        facts.append({"key": "price_low", "label": "Bas de zone", "value": _fmt(obj["price_low"]), "field": "price_low"})
        facts.append({"key": "price_high", "label": "Haut de zone", "value": _fmt(obj["price_high"]), "field": "price_high"})
    if obj.get("confidence") is not None:
        facts.append({"key": "confidence", "label": "Confiance producteur", "value": _fmt(obj["confidence"]), "field": "confidence"})

    candles = pack.get("candles") or []
    close = float(candles[-1]["close"]) if candles else None
    ref, ref_field = _reference_price(obj, at=as_of)
    context: dict[str, Any] = {"close": close, "reference_price": _fmt(ref), "reference_field": ref_field}
    if close is not None and ref:
        context["distance_pct"] = round((close - ref) / ref * 100.0, 4)
        lo, hi = obj.get("price_low"), obj.get("price_high")
        if lo is not None and hi is not None and float(lo) <= close <= float(hi):
            context["position"] = "inside"
        else:
            context["position"] = "above" if close > ref else "below"

    history = list(origin.get("status_history") or [])

    caveats: list[str] = []
    if upper_bound:
        caveats.append(
            "Objet déjà présent au début de la fenêtre rejouée : la date de détection "
            "réelle est antérieure ou égale à known_at."
        )
    if known_at is None:
        caveats.append("known_at absent : l'objet n'a pas été observé dans la fenêtre rejouée.")
    if maturity["status"] not in ("PRODUCTION", "VALIDATED"):
        caveats.append(f"Maturité {maturity['status']} : usage exploratoire, pas un signal de décision.")
    if ref_field and "prolongée" in ref_field:
        caveats.append("Prix de la trendline à as_of obtenu en prolongeant la droite entre ses deux ancres.")

    return {
        "version": EXPLAIN_VERSION,
        "symbol": pack.get("symbol"),
        "timeframe": pack.get("timeframe"),
        "as_of": as_of,
        "object_id": obj.get("id"),
        "lineage_key": origin.get("lineage_key"),
        "object": obj,
        "identity": {
            "layer": obj.get("layer"),
            "type": obj.get("type"),
            "kind": origin.get("kind"),
            "label": obj.get("label"),
            "side": obj.get("side"),
            "producer": origin.get("producer"),
            "engine": (meta or {}).get("engine"),
            "maturity": maturity,
            "pipeline": (meta or {}).get("pipeline", "Inconnu."),
        },
        "timeline": {
            "anchor_time": anchor,
            "known_at": known_at,
            "known_at_is_upper_bound": bool(upper_bound),
            "detection_lag_bars": lag_bars,
            "window": {"from": window_from, "to": pack.get("to"), "bar_seconds": tf_sec},
            "status_history": history,
        },
        "facts": facts,
        "context": context,
        "validation": dict(_VALIDATION),
        "caveats": caveats,
    }


def explain_chart_object(
    *,
    symbol: str,
    timeframe: str = "1h",
    object_id: str | None = None,
    lineage_key: str | None = None,
    as_of: int | None = None,
    limit: int = 300,
    lookback_bars: int = 48,
    x_twelve_data_key: str | None = None,
    now: int | None = None,
) -> dict[str, Any]:
    """Rejoue (cache CI-R9) jusqu'à ``as_of`` puis explique l'objet."""
    from app.chart_intelligence.service import build_chart_intelligence_replay

    pack = build_chart_intelligence_replay(
        symbol=symbol,
        timeframe=timeframe,
        limit=limit,
        to_ts=as_of,
        lookback_bars=lookback_bars,
        sources="engine",
        x_twelve_data_key=x_twelve_data_key,
        now=now,
    )
    return explain_from_pack(pack, object_id=object_id, lineage_key=lineage_key)
