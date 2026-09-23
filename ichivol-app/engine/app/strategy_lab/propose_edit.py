"""T3d — propose ruleset edits for Lab review (never auto-applied).

Structured patch → validated DSL via ``parse_ruleset``. No LLM in engine.
Status is always ``proposed``.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from app.strategy_lab.catalog import get_builtin_ruleset
from app.strategy_lab.conditions import CONDITION_REGISTRY
from app.strategy_lab.ruleset import Ruleset, parse_ruleset

PROPOSE_VERSION = "ruleset_propose_v0"

_DISCLAIMER = (
    "Ruleset edit proposed for Lab review only — never auto-applied to "
    "live strategy, catalog builtins, or pipeline gates."
)

_PATCH_OPS = frozenset(
    {
        "set_leaf",
        "unset_leaf",
        "set_direction",
        "set_stop_atr",
        "set_target_atr",
        "set_exit",
        "set_id",
        "set_description",
    }
)


def condition_catalog() -> list[dict[str, Any]]:
    """Serializable CONDITION_REGISTRY for Copilot / Lab NL→DSL grounding."""
    out: list[dict[str, Any]] = []
    for key in sorted(CONDITION_REGISTRY):
        spec = CONDITION_REGISTRY[key]
        row: dict[str, Any] = {
            "key": spec.key,
            "value_type": spec.value_type.__name__,
            "indicator_id": spec.indicator_id,
            "description": spec.description,
        }
        if spec.allowed_values is not None:
            row["allowed_values"] = list(spec.allowed_values)
        out.append(row)
    return out


def _group_payload(group_dict: Mapping[str, Any] | None) -> dict[str, Any]:
    """Normalize conditions blob to always expose all/any maps."""
    if not group_dict:
        return {"all": {}, "any": {}}
    keys = set(group_dict)
    if keys & {"all", "any"}:
        return {
            "all": dict(group_dict.get("all") or {}),
            "any": dict(group_dict.get("any") or {}),
        }
    # legacy flat
    return {"all": dict(group_dict), "any": {}}


def _conditions_from_maps(all_of: dict, any_of: dict) -> dict[str, Any]:
    if all_of and any_of:
        return {"all": all_of, "any": any_of}
    if any_of and not all_of:
        return {"any": any_of}
    return dict(all_of)  # legacy flat (or empty → parse will reject)


def _diff_maps(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, list]:
    b_keys = set(before)
    a_keys = set(after)
    added = sorted(a_keys - b_keys)
    removed = sorted(b_keys - a_keys)
    changed = sorted(k for k in (b_keys & a_keys) if before[k] != after[k])
    return {"added": added, "removed": removed, "changed": changed}


def _apply_patch(payload: dict[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    out = deepcopy(payload)
    op = str(patch.get("op", "")).strip()
    if op not in _PATCH_OPS:
        raise ValueError(f"unknown patch op {op!r}; known: {sorted(_PATCH_OPS)}")

    if op == "set_leaf":
        group = str(patch.get("group", "all")).strip().lower()
        if group not in ("all", "any"):
            raise ValueError("set_leaf.group must be 'all' or 'any'")
        key = patch.get("key")
        if not isinstance(key, str) or not key:
            raise ValueError("set_leaf.key must be a non-empty string")
        if "value" not in patch:
            raise ValueError("set_leaf.value is required")
        maps = _group_payload(out.get("conditions"))
        maps[group][key] = patch["value"]
        out["conditions"] = _conditions_from_maps(maps["all"], maps["any"])
        return out

    if op == "unset_leaf":
        group = str(patch.get("group", "all")).strip().lower()
        if group not in ("all", "any"):
            raise ValueError("unset_leaf.group must be 'all' or 'any'")
        key = patch.get("key")
        if not isinstance(key, str) or not key:
            raise ValueError("unset_leaf.key must be a non-empty string")
        maps = _group_payload(out.get("conditions"))
        maps[group].pop(key, None)
        out["conditions"] = _conditions_from_maps(maps["all"], maps["any"])
        return out

    if op == "set_direction":
        direction = patch.get("direction")
        if not isinstance(direction, str):
            raise ValueError("set_direction.direction must be str")
        out["direction"] = direction.strip().upper()
        return out

    if op == "set_stop_atr":
        out["stop_atr"] = float(patch["value"])
        return out

    if op == "set_target_atr":
        out["target_atr"] = float(patch["value"])
        return out

    if op == "set_exit":
        exit_body = patch.get("exit")
        if exit_body is None:
            out.pop("exit", None)
        elif isinstance(exit_body, Mapping):
            out["exit"] = dict(exit_body)
        else:
            raise ValueError("set_exit.exit must be object or null")
        return out

    if op == "set_id":
        rid = patch.get("id")
        if not isinstance(rid, str) or not rid.strip():
            raise ValueError("set_id.id must be non-empty str")
        out["id"] = rid.strip()
        return out

    if op == "set_description":
        desc = patch.get("description", "")
        if not isinstance(desc, str):
            raise ValueError("set_description.description must be str")
        out["description"] = desc
        return out

    raise ValueError(f"unhandled patch op {op!r}")


def _ruleset_diff(before: Ruleset, after: Ruleset) -> dict[str, Any]:
    b_maps = {
        "all": dict(before.condition_group.all_of),
        "any": dict(before.condition_group.any_of),
    }
    a_maps = {
        "all": dict(after.condition_group.all_of),
        "any": dict(after.condition_group.any_of),
    }
    top: dict[str, Any] = {}
    if before.direction != after.direction:
        top["direction"] = {"from": before.direction.value, "to": after.direction.value}
    if before.stop_atr != after.stop_atr:
        top["stop_atr"] = {"from": before.stop_atr, "to": after.stop_atr}
    if before.target_atr != after.target_atr:
        top["target_atr"] = {"from": before.target_atr, "to": after.target_atr}
    if before.id != after.id:
        top["id"] = {"from": before.id, "to": after.id}
    if before.to_dict().get("exit") != after.to_dict().get("exit"):
        top["exit"] = {"from": before.to_dict().get("exit"), "to": after.to_dict().get("exit")}
    return {
        "conditions_all": _diff_maps(b_maps["all"], a_maps["all"]),
        "conditions_any": _diff_maps(b_maps["any"], a_maps["any"]),
        "top_level": top,
    }


def propose_ruleset_edit(
    *,
    base_ruleset_id: str | None = None,
    base_ruleset: Mapping[str, Any] | None = None,
    patch: Mapping[str, Any] | None = None,
    patches: list[Mapping[str, Any]] | None = None,
    ruleset: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a candidate ruleset (full replace or patch). Always ``proposed``.

    Provide either ``ruleset`` (full candidate) or ``patch``/``patches`` on a base.
    """
    if base_ruleset is not None:
        base = parse_ruleset(base_ruleset)
    elif base_ruleset_id:
        base = get_builtin_ruleset(base_ruleset_id)
    elif ruleset is not None:
        # Full replace without explicit base — use candidate as both for diff id
        candidate = parse_ruleset(ruleset)
        return {
            "status": "proposed",
            "version": PROPOSE_VERSION,
            "base_id": None,
            "ruleset": candidate.to_dict(),
            "diff": _ruleset_diff(candidate, candidate),
            "disclaimer": _DISCLAIMER,
        }
    else:
        raise ValueError("provide base_ruleset_id, base_ruleset, or ruleset")

    if ruleset is not None:
        candidate = parse_ruleset(ruleset)
    else:
        ops: list[Mapping[str, Any]] = []
        if patches:
            ops.extend(patches)
        if patch is not None:
            ops.append(patch)
        if not ops:
            raise ValueError("provide patch, patches, or ruleset candidate")
        payload = base.to_dict()
        for p in ops:
            payload = _apply_patch(payload, p)
        # Mark proposed variant if id unchanged
        if payload.get("id") == base.id:
            payload["id"] = f"{base.id}__proposed"
            meta = dict(payload.get("meta") or {})
            meta["proposed_from"] = base.id
            payload["meta"] = meta
        candidate = parse_ruleset(payload)

    return {
        "status": "proposed",
        "version": PROPOSE_VERSION,
        "base_id": base.id,
        "ruleset": candidate.to_dict(),
        "diff": _ruleset_diff(base, candidate),
        "disclaimer": _DISCLAIMER,
    }
