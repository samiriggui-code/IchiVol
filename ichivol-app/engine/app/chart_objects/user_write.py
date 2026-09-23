"""USER chart-object writes (T2c) — ENTRY / STOP / TARGET only."""

from __future__ import annotations

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

    twelve_data.set_api_key_override(x_twelve_data_key)
    try:
        _provider, _psym, candles = resolve_and_fetch(
            obj.symbol, obj.timeframe, limit
        )
        assert_object_grounded(obj, candles)
    except ProviderNotWiredError as exc:
        raise UserWriteError(str(exc)) from exc
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
