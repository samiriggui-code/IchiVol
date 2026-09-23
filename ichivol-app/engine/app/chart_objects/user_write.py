"""USER chart-object writes (T2c) — ENTRY / STOP / TARGET + atomic setup."""

from __future__ import annotations

import uuid
from typing import Any

from app.chart_objects.draw import build_from_draw_args
from app.chart_objects.grounding import assert_object_grounded
from app.chart_objects.store import soft_delete_chart_object, upsert_chart_object
from app.chart_objects.types import ChartObject, ChartObjectType
from app.db.session import SessionLocal
from app.market_data import twelve_data
from app.market_data.resolve import ProviderNotWiredError, resolve_and_fetch

USER_TRADE_TYPES = frozenset(
    {
        ChartObjectType.ENTRY,
        ChartObjectType.STOP,
        ChartObjectType.TARGET,
    }
)


class UserWriteError(ValueError):
    """Raised for validation / grounding / persist failures on USER writes."""


def _parse_type(raw: Any) -> ChartObjectType:
    if raw is None or raw == "":
        raise UserWriteError("type is required (entry|stop|target)")
    try:
        obj_type = ChartObjectType(str(raw).strip().lower())
    except ValueError as exc:
        raise UserWriteError(f"invalid type: {raw!r}") from exc
    if obj_type not in USER_TRADE_TYPES:
        raise UserWriteError(
            "USER HTTP writes only allow type=entry|stop|target "
            f"(got {obj_type.value!r})"
        )
    return obj_type


def _parse_point(raw: Any, label: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or "time" not in raw or "price" not in raw:
        raise UserWriteError(f"{label} must be {{time, price}}")
    try:
        return {"time": int(raw["time"]), "price": float(raw["price"])}
    except (TypeError, ValueError) as exc:
        raise UserWriteError(f"{label} time/price invalid") from exc


def deduce_direction(entry_price: float, stop_price: float) -> str:
    """Return ``long`` or ``short``. Raises if stop == entry."""
    if stop_price < entry_price:
        return "long"
    if stop_price > entry_price:
        return "short"
    raise UserWriteError(
        "stop et entry au même prix — impossible de déduire le sens "
        "(stop < entry → LONG ; stop > entry → SHORT)"
    )


def assert_setup_geometry(
    *,
    direction: str,
    entry_price: float,
    stop_price: float,
    target_price: float,
) -> None:
    """LONG: stop < entry < target ; SHORT: target < entry < stop."""
    if direction == "long":
        if not (stop_price < entry_price < target_price):
            if target_price <= entry_price:
                raise UserWriteError(
                    "objectif du mauvais côté de l'entrée pour un LONG "
                    "(attendu : stop < entry < target)"
                )
            raise UserWriteError(
                "setup LONG incohérent (attendu : stop < entry < target)"
            )
    elif direction == "short":
        if not (target_price < entry_price < stop_price):
            if target_price >= entry_price:
                raise UserWriteError(
                    "objectif du mauvais côté de l'entrée pour un SHORT "
                    "(attendu : target < entry < stop)"
                )
            raise UserWriteError(
                "setup SHORT incohérent (attendu : target < entry < stop)"
            )
    else:
        raise UserWriteError(f"direction invalide: {direction!r}")


def build_user_trade_object(symbol: str, body: dict[str, Any]) -> ChartObject:
    """Build a source=user ENTRY/STOP/TARGET from HTTP body.

    ``setup_id`` (optional) is stored in ``origin.setup_id`` and as
    ``subtype=setup:<id>`` so deterministic ids stay unique per setup.
    """
    obj_type = _parse_type(body.get("type"))
    args = dict(body)
    args["symbol"] = symbol
    args["source"] = "user"
    args.pop("type", None)

    setup_id = args.pop("setup_id", None)
    origin = dict(args.get("origin") or {})
    if setup_id is not None and str(setup_id).strip():
        sid = str(setup_id).strip()
        origin["setup_id"] = sid
        if not args.get("subtype"):
            args["subtype"] = f"setup:{sid}"
    origin.setdefault("via", "user_mark_trade")
    args["origin"] = origin

    try:
        return build_from_draw_args(obj_type, args, agent_channel=False)
    except ValueError as exc:
        raise UserWriteError(str(exc)) from exc


def _fetch_candles(
    symbol: str,
    timeframe: str,
    limit: int,
    *,
    x_twelve_data_key: str | None,
):
    twelve_data.set_api_key_override(x_twelve_data_key)
    try:
        return resolve_and_fetch(symbol, timeframe, limit)
    except ProviderNotWiredError as exc:
        raise UserWriteError(str(exc)) from exc
    except ValueError as exc:
        raise UserWriteError(str(exc)) from exc


def persist_user_trade_object(
    symbol: str,
    body: dict[str, Any],
    *,
    x_twelve_data_key: str | None = None,
) -> dict[str, Any]:
    """Ground against OHLCV then upsert. Returns ``{object, upserted}``."""
    obj = build_user_trade_object(symbol, body)
    if obj.source.value != "user":
        raise UserWriteError("USER write path must persist source=user")

    limit = int(body.get("limit") or 500)
    if limit < 50 or limit > 5000:
        limit = 500

    _provider, _psym, candles = _fetch_candles(
        obj.symbol, obj.timeframe, limit, x_twelve_data_key=x_twelve_data_key
    )
    try:
        assert_object_grounded(obj, candles)
    except ValueError as exc:
        raise UserWriteError(str(exc)) from exc

    session = SessionLocal()
    try:
        saved = upsert_chart_object(session, obj)
        session.commit()
        return {"object": saved.to_dict(), "upserted": True}
    except ValueError as exc:
        session.rollback()
        raise UserWriteError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise UserWriteError(f"persist_failed: {exc}") from exc
    finally:
        session.close()


def persist_user_trade_setup(
    symbol: str,
    body: dict[str, Any],
    *,
    x_twelve_data_key: str | None = None,
) -> dict[str, Any]:
    """Validate + ground ENTRY/STOP/TARGET then persist all three atomically.

    Body: ``{timeframe, entry:{time,price}, stop:{…}, target:{…}, setup_id?}``.
    Direction is deduced from stop vs entry; geometry is enforced server-side.
    """
    if not isinstance(body, dict):
        raise UserWriteError("body must be an object")
    timeframe = str(body.get("timeframe") or "").strip()
    if not timeframe:
        raise UserWriteError("timeframe is required")

    entry = _parse_point(body.get("entry"), "entry")
    stop = _parse_point(body.get("stop"), "stop")
    target = _parse_point(body.get("target"), "target")

    direction = deduce_direction(entry["price"], stop["price"])
    assert_setup_geometry(
        direction=direction,
        entry_price=entry["price"],
        stop_price=stop["price"],
        target_price=target["price"],
    )

    setup_id = str(body.get("setup_id") or "").strip() or str(uuid.uuid4())
    side = "LONG" if direction == "long" else "SHORT"
    limit = int(body.get("limit") or 500)
    if limit < 50 or limit > 5000:
        limit = 500

    sym = symbol.strip().upper()
    specs = (
        (ChartObjectType.ENTRY, entry, "Entry"),
        (ChartObjectType.STOP, stop, "Stop"),
        (ChartObjectType.TARGET, target, "Target"),
    )
    objects: list[ChartObject] = []
    for obj_type, pt, label in specs:
        objects.append(
            build_user_trade_object(
                sym,
                {
                    "type": obj_type.value,
                    "timeframe": timeframe,
                    "price": pt["price"],
                    "time": pt["time"],
                    "as_of": pt["time"],
                    "side": side,
                    "label": label,
                    "setup_id": setup_id,
                    "origin": {
                        "via": "user_mark_trade_setup",
                        "setup_id": setup_id,
                        "direction": direction,
                    },
                },
            )
        )

    _provider, _psym, candles = _fetch_candles(
        sym, timeframe, limit, x_twelve_data_key=x_twelve_data_key
    )
    for obj in objects:
        try:
            assert_object_grounded(obj, candles)
        except ValueError as exc:
            raise UserWriteError(str(exc)) from exc

    session = SessionLocal()
    try:
        saved = [upsert_chart_object(session, obj) for obj in objects]
        session.commit()
        return {
            "setup_id": setup_id,
            "direction": direction,
            "upserted": True,
            "objects": [o.to_dict() for o in saved],
        }
    except ValueError as exc:
        session.rollback()
        raise UserWriteError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise UserWriteError(f"persist_failed: {exc}") from exc
    finally:
        session.close()


def delete_user_chart_object(object_id: str) -> dict[str, Any]:
    """Soft-delete a USER overlay only (never CLAUDE/ENGINE)."""
    oid = str(object_id or "").strip()
    if not oid:
        raise UserWriteError("id is required")
    session = SessionLocal()
    try:
        deleted = soft_delete_chart_object(session, oid, source="user")
        session.commit()
        if not deleted:
            raise UserWriteError(f"not_found: chart object {oid!r} (user)")
        return {"id": oid, "deleted": True, "source": "user"}
    except UserWriteError:
        session.rollback()
        raise
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise UserWriteError(f"delete_failed: {exc}") from exc
    finally:
        session.close()
