"""OB-1 — lecture des fichiers du collecteur pour l'API et les agents (engine, lecture seule).

Un statut écrit il y a plus de ``COLLECTOR_DOWN_AFTER_S`` secondes = collecteur arrêté : l'état publié
devient ``STALE`` (raison ``collector_down``), jamais le dernier état SYNCED figé.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from app.microstructure.book.storage import latest_minute, list_symbols, read_minutes, read_status

COLLECTOR_DOWN_AFTER_S = 30


def effective_status(status: dict[str, Any] | None, now_s: int) -> dict[str, Any]:
    if status is None:
        return {"state": "UNAVAILABLE", "reason": "not_collected"}
    out = dict(status)
    written = status.get("written_at_ms")
    age = None if written is None else now_s - int(written) / 1000
    out["status_age_s"] = age
    out["collector_alive"] = age is not None and age <= COLLECTOR_DOWN_AFTER_S
    if not out["collector_alive"]:
        out["state"] = "STALE"
        out["reason"] = "collector_down"
    return out


def status_all(root: str | Path, now_s: int | None = None) -> dict[str, Any]:
    now = int(time.time()) if now_s is None else int(now_s)
    root = Path(root)
    symbols = list_symbols(root)
    return {
        "enabled": root.is_dir(),
        "venue": "binance-spot",
        "symbols": {s: effective_status(read_status(root, s), now) for s in symbols},
        "note": "Carnet d'une seule plateforme (Binance spot) : ne représente pas tout le marché. "
        "Liquidité affichée ≠ volume exécuté ; ni carte de liquidations, ni stops.",
    }


def minutes(root: str | Path, symbol: str, start_s: int, end_s: int, limit: int) -> dict[str, Any]:
    rows = read_minutes(Path(root), symbol, start_s, end_s, limit=limit)
    expected = max(0, (end_s - (start_s - start_s % 60) + 59) // 60)
    return {
        "symbol": symbol.upper(),
        "venue": "binance-spot",
        "from": start_s,
        "to": end_s,
        "rows": rows,
        "n_rows": len(rows),
        # minutes de la plage sans ligne : historique indisponible (collecteur absent), jamais « carnet vide »
        "missing_minutes": max(0, min(expected, limit) - len(rows)),
        "states": {s: sum(1 for r in rows if r.get("book_state") == s) for s in ("SYNCED", "PARTIAL", "STALE", "UNAVAILABLE")},
    }


def latest(root: str | Path, symbol: str, now_s: int | None = None) -> dict[str, Any] | None:
    now = int(time.time()) if now_s is None else int(now_s)
    return latest_minute(Path(root), symbol, now)


def _pct(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    return s[min(len(s) - 1, int(q * (len(s) - 1) + 0.5))]


def quality(root: str | Path, symbol: str, hours: int, now_s: int | None = None) -> dict[str, Any]:
    """Tableau de bord qualité de la collecte sur ``hours`` heures : part des minutes SYNCED rapportée aux
    minutes **attendues** (une minute absente compte comme non mesurée), trous, resyncs, spread."""
    now = int(time.time()) if now_s is None else int(now_s)
    end = now - now % 60
    start = end - hours * 3600
    root = Path(root)
    rows = read_minutes(root, symbol, start, end, limit=hours * 60 + 1)
    expected = hours * 60
    states = {s: sum(1 for r in rows if r.get("book_state") == s) for s in ("SYNCED", "PARTIAL", "STALE", "UNAVAILABLE")}
    spreads = [r["spread_bps_mean"] for r in rows if r.get("book_state") == "SYNCED" and r.get("spread_bps_mean") is not None]
    return {
        "symbol": symbol.upper(),
        "venue": "binance-spot",
        "window_hours": hours,
        "from": start,
        "to": end,
        "expected_minutes": expected,
        "written_minutes": len(rows),
        "missing_minutes": max(0, expected - len(rows)),
        "states": states,
        "synced_pct": round(100 * states["SYNCED"] / expected, 2) if expected else None,
        "book_gaps": sum(int(r.get("book_gaps") or 0) for r in rows),
        "trade_gaps": sum(int(r.get("trade_gaps") or 0) for r in rows),
        "trades": sum(int((r.get("trades") or {}).get("n") or 0) for r in rows),
        "spread_bps_median": _pct(spreads, 0.5),
        "spread_bps_p95": _pct(spreads, 0.95),
        "first_minute": rows[0]["t"] if rows else None,
        "last_minute": rows[-1]["t"] if rows else None,
        "status": effective_status(read_status(root, symbol), now),
    }
