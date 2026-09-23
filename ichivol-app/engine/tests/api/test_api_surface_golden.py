"""Golden parity — OpenAPI schema + ordered HTTP route surface."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.routing import APIRoute, _IncludedRouter

from app.main import app

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
_OPENAPI = _FIXTURES / "openapi_golden.json"
_ORDER = _FIXTURES / "route_order_golden.json"


def _walk_api_routes(routes):
    for r in routes:
        if isinstance(r, APIRoute):
            yield r
        elif isinstance(r, _IncludedRouter):
            yield from _walk_api_routes(r.original_router.routes)
        elif hasattr(r, "routes"):
            yield from _walk_api_routes(r.routes)


def _route_order() -> list[dict]:
    out: list[dict] = []
    for r in _walk_api_routes(app.routes):
        methods = sorted(m for m in (r.methods or []) if m not in ("HEAD",))
        out.append(
            {
                "methods": methods,
                "path": r.path,
                "endpoint": r.endpoint.__name__,
            }
        )
    return out


def test_openapi_matches_golden():
    actual = app.openapi()
    expected = json.loads(_OPENAPI.read_text())
    assert json.loads(json.dumps(actual, sort_keys=True)) == expected


def test_route_order_matches_golden():
    actual = _route_order()
    expected = json.loads(_ORDER.read_text())
    assert actual == expected
