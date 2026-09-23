"""Agent command channel (read-only)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agent_channel.registry import TOOLS, dispatch_command, list_tool_specs
from app.config import settings

router = APIRouter(prefix=settings.engine_api_prefix, tags=["engine"])

_AGENT_CHANNEL_VERSION = "engine_agent_v1"
_MAX_AGENT_BATCH_ITEMS = 20
_AGENT_BATCH_CONCURRENCY = 6


@router.get("/agent/tools")
def get_agent_tools() -> dict:
    """Allowlist introspection -- same content `list_tools` (the command)
    returns, as a plain GET for a client that just wants to enumerate
    capabilities without a POST body."""
    return {"tools": list_tool_specs()}


@router.get("/agent/capabilities")
def get_agent_capabilities() -> dict:
    """Capabilities descriptor. Chart-overlay WRITE (draw_*/delete_chart_object)
    is enabled (T2b). Paper trading stays off this channel — only via
    ``POST /paper/positions`` (app/paper/engine.py)."""
    write_cmds = sorted(name for name, spec in TOOLS.items() if not spec.read_only)
    return {
        "version": _AGENT_CHANNEL_VERSION,
        "read_only": False,
        "write_tier_enabled": True,
        "write_scopes": ["chart_objects"],
        "write_commands": write_cmds,
        "max_batch_items": _MAX_AGENT_BATCH_ITEMS,
        "commands": sorted(TOOLS.keys()),
    }


class AgentCommandRequest(BaseModel):
    cmd: str
    args: dict = Field(default_factory=dict)


@router.post("/agent/command")
def post_agent_command(payload: AgentCommandRequest) -> dict:
    """Single-command entry point: `{cmd, args}` -> `{ok, cmd, data|error}`.
    Never raises for a client-caused failure (unknown command, bad args) --
    see app/agent_channel/registry.py::dispatch_command."""
    return dispatch_command(payload.cmd, payload.args)


class AgentBatchItem(BaseModel):
    cmd: str
    args: dict = Field(default_factory=dict)


class AgentBatchRequest(BaseModel):
    commands: list[AgentBatchItem] = Field(default_factory=list)


@router.post("/agent/batch")
def post_agent_batch(payload: AgentBatchRequest) -> dict:
    """Concurrent batch of up to `_MAX_AGENT_BATCH_ITEMS` commands, results
    returned in the SAME ORDER as the request (order-stable) regardless of
    which finishes first -- same pattern as `POST /decisions/batch`."""
    if not payload.commands:
        return {"results": []}
    if len(payload.commands) > _MAX_AGENT_BATCH_ITEMS:
        raise HTTPException(
            status_code=422,
            detail=f"batch_too_large: max {_MAX_AGENT_BATCH_ITEMS} commands per request",
        )

    results: list[dict | None] = [None] * len(payload.commands)
    with ThreadPoolExecutor(max_workers=_AGENT_BATCH_CONCURRENCY) as pool:
        futures = {
            pool.submit(dispatch_command, item.cmd, item.args): index
            for index, item in enumerate(payload.commands)
        }
        for future in as_completed(futures):
            index = futures[future]
            item = payload.commands[index]
            try:
                results[index] = future.result()
            except Exception as exc:  # noqa: BLE001 -- one command's crash must not sink the batch
                results[index] = {"ok": False, "cmd": item.cmd, "error": f"internal_error: {exc}"}

    return {"results": results}
