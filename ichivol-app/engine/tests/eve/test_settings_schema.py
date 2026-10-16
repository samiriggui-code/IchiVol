"""Settings schema knobs — Basic/Advanced + writable overrides (QuantDinger P0)."""

from __future__ import annotations

import json
from pathlib import Path

from app.eve import settings_schema as ss
from app.eve.calibration import active_policy


def test_schema_annotates_advanced_and_writable() -> None:
    schema = ss.schema_with_advanced_flags()
    assert "jev" in schema and "event_radar" in schema
    by_key = {
        item["key"]: item
        for group in schema.values()
        for item in group["items"]
    }
    assert by_key["EVENT_RADAR_ENABLED"]["is_advanced"] is False
    assert by_key["EVENT_RADAR_ENABLED"]["writable"] is True
    assert by_key["JEV_TIMEOUT_SECONDS"]["is_advanced"] is True
    assert by_key["JEV_API_KEY"]["writable"] is False
    assert by_key["EVE_PAPER_AUTONOMY"]["writable"] is False


def test_apply_patch_persists_writable_only(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "overrides.json"
    monkeypatch.setenv("EVE_SETTINGS_OVERRIDES_PATH", str(path))
    out = ss.apply_patch(
        {
            "JEV_MIN_CONFIDENCE": 0.5,
            "EVENT_RADAR_ENABLED": True,
            "EVENT_RADAR_MAX_EVENTS": 4,
        }
    )
    assert path.is_file()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["JEV_MIN_CONFIDENCE"] == 0.5
    assert saved["EVENT_RADAR_ENABLED"] is True
    assert saved["EVENT_RADAR_MAX_EVENTS"] == 4
    assert out["values"]["JEV_MIN_CONFIDENCE"] == 0.5


def test_apply_patch_rejects_secret(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EVE_SETTINGS_OVERRIDES_PATH", str(tmp_path / "o.json"))
    try:
        ss.apply_patch({"JEV_API_KEY": "leak"})
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "not_writable" in str(exc)


def test_active_policy_reads_knob_overrides(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "overrides.json"
    monkeypatch.setenv("EVE_SETTINGS_OVERRIDES_PATH", str(path))
    ss.apply_patch(
        {
            "JEV_MIN_CONFIDENCE": 0.61,
            "EVE_ENTRY_GATE_MIN_CONFIDENCE": 0.72,
        }
    )
    pol = active_policy()
    assert pol["thresholds"]["min_jev_confidence"] == 0.61
    assert pol["thresholds"]["entry_gate_min_confidence"] == 0.72


def test_confidence_bounds(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("EVE_SETTINGS_OVERRIDES_PATH", str(tmp_path / "o.json"))
    try:
        ss.apply_patch({"JEV_MIN_CONFIDENCE": 1.5})
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "JEV_MIN_CONFIDENCE" in str(exc)
