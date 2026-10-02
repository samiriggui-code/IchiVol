"""OB-1 — stockage fichiers (hors Postgres) : brut rejouable, agrégat 1 min, statut courant.

Arborescence sous ``OB_DATA_DIR`` (volume partagé, lecture seule côté engine) :
- ``raw/{SYMBOL}/{YYYY-MM-DD}.ndjson.gz`` : snapshots, deltas, aggTrades, trous, resyncs, déconnexions,
  chacun avec l'heure plateforme et ``rx`` (réception). Base du **replay fidèle**. Rétention courte.
- ``agg/{SYMBOL}/{YYYY-MM-DD}.ndjson`` : une ligne par minute (``aggregate.py``). Rétention longue.
- ``status/{SYMBOL}.json`` : état courant du collecteur (écrit atomiquement).

Lecture tolérante : une fin de fichier tronquée (arrêt brutal) est ignorée, pas une erreur.
"""

from __future__ import annotations

import gzip
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def utc_day(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def _dumps(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


class DailyWriter:
    """Append NDJSON dans un fichier par jour UTC (gzip ou texte), rotation à minuit UTC."""

    def __init__(self, root: Path, symbol: str, kind: str, *, compress: bool):
        self.dir = Path(root) / kind / symbol.upper()
        self.compress = compress
        self._day: str | None = None
        self._fh: Any = None
        self._last_flush = 0.0

    def _path(self, day: str) -> Path:
        return self.dir / (f"{day}.ndjson.gz" if self.compress else f"{day}.ndjson")

    def write(self, obj: dict[str, Any], at_ms: int) -> None:
        day = utc_day(at_ms)
        if day != self._day:
            self.close()
            self.dir.mkdir(parents=True, exist_ok=True)
            path = self._path(day)
            self._fh = gzip.open(path, "at", encoding="utf-8") if self.compress else open(path, "a", encoding="utf-8")
            self._day = day
        self._fh.write(_dumps(obj) + "\n")
        now = time.monotonic()
        if not self.compress or now - self._last_flush > 5:
            self._fh.flush()
            self._last_flush = now

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None
            self._day = None


def write_status(root: Path, symbol: str, status: dict[str, Any]) -> None:
    d = Path(root) / "status"
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f".{symbol.upper()}.json.tmp"
    tmp.write_text(_dumps(status), encoding="utf-8")
    os.replace(tmp, d / f"{symbol.upper()}.json")


def read_status(root: Path, symbol: str) -> dict[str, Any] | None:
    p = Path(root) / "status" / f"{symbol.upper()}.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def list_symbols(root: Path) -> list[str]:
    d = Path(root) / "status"
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.json") if not p.name.startswith("."))


def iter_ndjson(path: Path) -> Iterator[dict[str, Any]]:
    """Lignes JSON d'un fichier (gzip ou texte). Une dernière ligne / un dernier bloc tronqué est ignoré."""
    opener = gzip.open if path.suffix == ".gz" else open
    try:
        with opener(path, "rt", encoding="utf-8") as fh:  # type: ignore[operator]
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except ValueError:
                    continue  # ligne partielle (arrêt brutal pendant l'écriture)
    except (EOFError, gzip.BadGzipFile, OSError):
        return  # bloc gzip tronqué en fin de fichier


def read_minutes(root: Path, symbol: str, start_s: int, end_s: int, limit: int = 1440) -> list[dict[str, Any]]:
    """Lignes d'agrégat 1 min avec ``start_s <= t < end_s`` (au plus ``limit``, les plus anciennes d'abord)."""
    out: list[dict[str, Any]] = []
    day_s = start_s - start_s % 86400
    while day_s < end_s and len(out) < limit:
        p = Path(root) / "agg" / symbol.upper() / f"{utc_day(day_s * 1000)}.ndjson"
        if p.exists():
            for row in iter_ndjson(p):
                t = row.get("t")
                if isinstance(t, int) and start_s <= t < end_s:
                    out.append(row)
                    if len(out) >= limit:
                        break
        day_s += 86400
    out.sort(key=lambda r: r["t"])
    return out


def latest_minute(root: Path, symbol: str, now_s: int) -> dict[str, Any] | None:
    """Dernière minute écrite (aujourd'hui, sinon hier), sans parser plus d'un jour sur le chemin courant."""
    for day_s in (now_s - now_s % 86400, now_s - now_s % 86400 - 86400):
        p = Path(root) / "agg" / symbol.upper() / f"{utc_day(day_s * 1000)}.ndjson"
        if not p.exists():
            continue
        last = None
        for row in iter_ndjson(p):
            if isinstance(row.get("t"), int) and row["t"] <= now_s:
                last = row
        if last is not None:
            return last
    return None


def purge_older_than(root: Path, kind: str, days: int, now_ms: int | None = None) -> int:
    """Supprime les fichiers journaliers plus vieux que ``days`` jours. Renvoie le nombre supprimé."""
    if days <= 0:
        return 0
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    cutoff = utc_day(now_ms - days * 86_400_000)
    removed = 0
    base = Path(root) / kind
    if not base.is_dir():
        return 0
    for p in base.glob("*/*.ndjson*"):
        day = p.name.split(".")[0]
        if day < cutoff:
            p.unlink(missing_ok=True)
            removed += 1
    return removed
