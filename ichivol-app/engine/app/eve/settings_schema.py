"""Ève / JEV / Event Radar settings schema (QuantDinger Basic/Advanced pattern).

Front consumes schema + values — does not hardcode field lists.
Non-secret knobs may be overridden via a JSON file; secrets stay env-only.
Never enables live brokers.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.config import settings as app_settings

SCHEMA_VERSION = "ichivol.eve.settings_schema.v1"

# Operator rarely-touched knobs → Advanced tab (QuantDinger ADVANCED_KEYS subset).
ADVANCED_KEYS: frozenset[str] = frozenset(
    {
        "JEV_PROVIDER",
        "JEV_URL",
        "JEV_MODEL",
        "JEV_TIMEOUT_SECONDS",
        "JEV_MIN_CONFIDENCE",
        "EVE_ENTRY_GATE_MIN_CONFIDENCE",
        "EVENT_RADAR_JEV_MIN_CONFIDENCE",
        "EVENT_RADAR_NEWS_LOOKBACK_DAYS",
        "EVENT_RADAR_MAX_EVENTS",
        "EVE_PAPER_AUTONOMY",
    }
)

# Writable via PATCH (overrides file). Secrets + autonomy stay env/config only.
WRITABLE_KEYS: frozenset[str] = frozenset(
    {
        "JEV_TIMEOUT_SECONDS",
        "JEV_MIN_CONFIDENCE",
        "EVE_ENTRY_GATE_MIN_CONFIDENCE",
        "EVENT_RADAR_ENABLED",
        "EVENT_RADAR_JEV_MIN_CONFIDENCE",
        "EVENT_RADAR_NEWS_LOOKBACK_DAYS",
        "EVENT_RADAR_MAX_EVENTS",
        "EVENT_RADAR_CRYPTO_RSS_ENABLED",
        "EVENT_RADAR_YAHOO_FINANCE_RSS_ENABLED",
        "EVENT_RADAR_SEC_EDGAR_ENABLED",
    }
)

CONFIG_SCHEMA: dict[str, Any] = {
    "jev": {
        "title": "JEV / System One",
        "order": 1,
        "items": [
            {
                "key": "JEV_API_KEY",
                "label": "Clé JEV / TypeSafe",
                "type": "password",
                "read_only": True,
                "description": "Env only (JEV_API_KEY ou TYPESAFE_API_KEY). Jamais écrite depuis l’UI.",
            },
            {
                "key": "JEV_PROVIDER",
                "label": "Provider JEV",
                "type": "text",
                "read_only": True,
                "description": "jevos (VPS) ou typesafe — via JEV_PROVIDER.",
            },
            {
                "key": "JEV_URL",
                "label": "URL jevos",
                "type": "text",
                "read_only": True,
                "description": "Base URL System One (JEV_URL).",
            },
            {
                "key": "JEV_MODEL",
                "label": "Modèle JEV",
                "type": "text",
                "read_only": True,
                "description": "Pin modèle (JEV_MODEL) — anti silent-upgrade.",
            },
            {
                "key": "JEV_TIMEOUT_SECONDS",
                "label": "Timeout JEV (s)",
                "type": "number",
                "default": 5.0,
                "description": "Budget latence ; dépassement → late → HOLD.",
            },
            {
                "key": "JEV_MIN_CONFIDENCE",
                "label": "Confiance JEV min",
                "type": "number",
                "default": 0.45,
                "description": "Sous ce seuil → ABSTAIN (fallback ladder).",
            },
            {
                "key": "EVE_ENTRY_GATE_MIN_CONFIDENCE",
                "label": "Confiance gate entrée",
                "type": "number",
                "default": 0.55,
                "description": "Seuil du gate 5 CHOICE avant paper.",
            },
            {
                "key": "EVE_PAPER_AUTONOMY",
                "label": "Autonomie paper Ève",
                "type": "boolean",
                "read_only": True,
                "default": False,
                "description": "Kill-switch paper (env EVE_PAPER_AUTONOMY). Jamais live broker.",
            },
        ],
    },
    "event_radar": {
        "title": "Event Radar",
        "order": 2,
        "items": [
            {
                "key": "EVENT_RADAR_ENABLED",
                "label": "Event Radar",
                "type": "boolean",
                "default": False,
                "description": "Master switch — enrichit le contexte news (P1).",
            },
            {
                "key": "EVENT_RADAR_JEV_MIN_CONFIDENCE",
                "label": "Confiance JEV radar",
                "type": "number",
                "default": 0.65,
                "description": "Seuil pertinence événements.",
            },
            {
                "key": "EVENT_RADAR_NEWS_LOOKBACK_DAYS",
                "label": "Lookback news (jours)",
                "type": "number",
                "default": 2,
                "description": "Fenêtre de fraîcheur des news.",
            },
            {
                "key": "EVENT_RADAR_MAX_EVENTS",
                "label": "Max événements",
                "type": "number",
                "default": 8,
                "description": "Cap d’événements injectés dans le contexte.",
            },
            {
                "key": "EVENT_RADAR_CRYPTO_RSS_ENABLED",
                "label": "Source crypto RSS",
                "type": "boolean",
                "default": True,
                "description": "Flux RSS crypto.",
            },
            {
                "key": "EVENT_RADAR_YAHOO_FINANCE_RSS_ENABLED",
                "label": "Source Yahoo Finance RSS",
                "type": "boolean",
                "default": True,
                "description": "Flux Yahoo Finance.",
            },
            {
                "key": "EVENT_RADAR_SEC_EDGAR_ENABLED",
                "label": "Source SEC EDGAR",
                "type": "boolean",
                "default": False,
                "description": "Filings SEC (équités).",
            },
        ],
    },
}


def _overrides_path() -> Path:
    raw = os.getenv("EVE_SETTINGS_OVERRIDES_PATH", "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parents[2] / "data" / "eve_settings_overrides.json"


def load_overrides() -> dict[str, Any]:
    path = _overrides_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if k in WRITABLE_KEYS}


def save_overrides(overrides: dict[str, Any]) -> dict[str, Any]:
    path = _overrides_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    cleaned = {k: overrides[k] for k in sorted(overrides) if k in WRITABLE_KEYS}
    path.write_text(json.dumps(cleaned, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return cleaned


def schema_with_advanced_flags() -> dict[str, Any]:
    """Annotate each item with ``is_advanced`` (QuantDinger pattern)."""
    annotated: dict[str, Any] = {}
    for group_key, group in CONFIG_SCHEMA.items():
        items = []
        for item in group.get("items", []):
            new_item = dict(item)
            new_item["is_advanced"] = item["key"] in ADVANCED_KEYS
            new_item["writable"] = item["key"] in WRITABLE_KEYS and not item.get("read_only")
            items.append(new_item)
        annotated[group_key] = {**group, "items": items}
    return annotated


def _env_defaults() -> dict[str, Any]:
    return {
        "JEV_TIMEOUT_SECONDS": float(app_settings.jev_timeout_seconds),
        "JEV_MIN_CONFIDENCE": float(app_settings.jev_min_confidence),
        "EVE_ENTRY_GATE_MIN_CONFIDENCE": float(app_settings.eve_entry_gate_min_confidence),
        "EVENT_RADAR_ENABLED": bool(app_settings.event_radar_enabled),
        "EVENT_RADAR_JEV_MIN_CONFIDENCE": float(app_settings.event_radar_jev_min_confidence),
        "EVENT_RADAR_NEWS_LOOKBACK_DAYS": int(app_settings.event_radar_news_lookback_days),
        "EVENT_RADAR_MAX_EVENTS": int(app_settings.event_radar_max_events),
        "EVENT_RADAR_CRYPTO_RSS_ENABLED": bool(app_settings.event_radar_crypto_rss_enabled),
        "EVENT_RADAR_YAHOO_FINANCE_RSS_ENABLED": bool(
            app_settings.event_radar_yahoo_finance_rss_enabled
        ),
        "EVENT_RADAR_SEC_EDGAR_ENABLED": bool(app_settings.event_radar_sec_edgar_enabled),
        "EVE_PAPER_AUTONOMY": bool(app_settings.eve_paper_autonomy),
    }


def _provider_snapshot() -> dict[str, Any]:
    try:
        from app.jev.providers import resolve_provider

        cfg = resolve_provider()
        return {
            "JEV_PROVIDER": cfg.name,
            "JEV_URL": cfg.base_url,
            "JEV_MODEL": cfg.model,
            "JEV_API_KEY_SET": bool(cfg.api_key),
        }
    except Exception:
        return {
            "JEV_PROVIDER": os.getenv("JEV_PROVIDER", "jevos"),
            "JEV_URL": os.getenv("JEV_URL", ""),
            "JEV_MODEL": os.getenv("JEV_MODEL", ""),
            "JEV_API_KEY_SET": bool(
                os.getenv("JEV_API_KEY") or os.getenv("TYPESAFE_API_KEY")
            ),
        }


def resolved_values() -> dict[str, Any]:
    """Effective operator values: env/config defaults ← JSON overrides."""
    values = _env_defaults()
    values.update(load_overrides())
    values.update(_provider_snapshot())
    # Env kill-switch still wins for autonomy (ops).
    env_auto = os.getenv("EVE_PAPER_AUTONOMY")
    if env_auto is not None and env_auto != "":
        values["EVE_PAPER_AUTONOMY"] = env_auto.lower() in ("1", "true", "yes", "on")
    return values


def public_values() -> dict[str, Any]:
    """Values safe for UI — password fields never leak the secret."""
    raw = resolved_values()
    out = dict(raw)
    out["JEV_API_KEY"] = "***" if raw.get("JEV_API_KEY_SET") else ""
    out.pop("JEV_API_KEY_SET", None)
    return out


def _coerce(key: str, value: Any, typ: str) -> Any:
    if typ == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("1", "true", "yes", "on")
        return bool(value)
    if typ == "number":
        if key.endswith("_DAYS") or key.endswith("_EVENTS") or key == "EVENT_RADAR_MAX_EVENTS":
            n = int(float(value))
            if n < 0:
                raise ValueError(f"{key} must be >= 0")
            return n
        f = float(value)
        if key.endswith("CONFIDENCE") and not (0.0 <= f <= 1.0):
            raise ValueError(f"{key} must be in [0, 1]")
        if key.endswith("SECONDS") and f <= 0:
            raise ValueError(f"{key} must be > 0")
        return f
    if typ in ("text", "password"):
        return str(value)
    return value


def _type_for_key(key: str) -> str | None:
    for group in CONFIG_SCHEMA.values():
        for item in group.get("items", []):
            if item["key"] == key:
                return str(item["type"])
    return None


def apply_patch(patch: dict[str, Any]) -> dict[str, Any]:
    """Merge writable keys into overrides file. Rejects secrets / read-only."""
    if not isinstance(patch, dict):
        raise ValueError("patch must be an object")
    current = load_overrides()
    for key, value in patch.items():
        if key not in WRITABLE_KEYS:
            raise ValueError(f"not_writable:{key}")
        typ = _type_for_key(key)
        if typ is None:
            raise ValueError(f"unknown_key:{key}")
        current[key] = _coerce(key, value, typ)
    saved = save_overrides(current)
    return {
        "schema": SCHEMA_VERSION,
        "saved": saved,
        "values": public_values(),
    }


def settings_bundle() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "schema": schema_with_advanced_flags(),
        "values": public_values(),
        "advanced_keys": sorted(ADVANCED_KEYS),
        "writable_keys": sorted(WRITABLE_KEYS),
        "note": "Basic/Advanced via is_advanced; secrets env-only; no live trading",
    }


def jev_timeout_seconds() -> float:
    return float(resolved_values().get("JEV_TIMEOUT_SECONDS") or 5.0)


def policy_threshold_overrides() -> dict[str, Any]:
    """Map operator knobs into calibration thresholds."""
    v = resolved_values()
    return {
        "min_jev_confidence": float(v.get("JEV_MIN_CONFIDENCE") or 0.45),
        "entry_gate_min_confidence": float(v.get("EVE_ENTRY_GATE_MIN_CONFIDENCE") or 0.55),
    }
