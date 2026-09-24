"""T12a — versioned deep history for Strategy Lab (observation / research).

Local Candle datasets with manifeste (sha256 + quality code counts).
Built via Binance ``startTime`` pagination or Twelve Data (≤ 5 000 bars).
Always runs ``validate_candles`` at construction — never silently repairs.

Degraded datasets remain loadable; callers must surface ``data_warning``.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import httpx

from app.indicators.ichimoku import Candle
from app.market_data.quality import QualityReport, validate_candles
from app.market_data.timeframes import TF_SECONDS
from app.market_data.volume_semantics import VolumeType

BINANCE_BASE = "https://data-api.binance.vision"
_INTERVAL_MS = {"15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
_MIN_SLEEP_S = 0.12
TWELVE_DATA_MAX_BARS = 5_000
DEFAULT_CRYPTO_YEARS = 2

DATASETS_DIR = Path(__file__).resolve().parent / "datasets"


@dataclass(frozen=True)
class LabHistoryBundle:
    """Candles + provenance for one Lab study window."""

    dataset_id: str
    candles: list[Candle]
    manifest: dict[str, Any]
    quality: dict[str, Any]
    data_warning: str | None
    history_span_seconds: int | None = None
    history_warning: str | None = None

    def to_meta_dict(self) -> dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "quality_report": dict(self.quality),
            "data_warning": self.data_warning,
            "history_span_seconds": self.history_span_seconds,
            "history_warning": self.history_warning,
            "manifest": {
                k: self.manifest[k]
                for k in (
                    "dataset_id",
                    "provider",
                    "symbol",
                    "timeframe",
                    "n_bars",
                    "sha256",
                    "fetched_at",
                    "start_ms",
                    "end_ms",
                    "quality",
                    "degraded",
                )
                if k in self.manifest
            },
        }


def _datasets_root(root: Path | None = None) -> Path:
    path = root if root is not None else DATASETS_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _manifest_path(root: Path) -> Path:
    return root / "manifest.json"


def _load_manifest(root: Path) -> dict[str, Any]:
    mp = _manifest_path(root)
    if not mp.exists():
        return {}
    return json.loads(mp.read_text(encoding="utf-8"))


def _save_manifest(root: Path, man: dict[str, Any]) -> None:
    _manifest_path(root).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")


def _aligned_cache_end_ms(now_ms: int, timeframe: str) -> int:
    """Stable cache-key end: last closed boundary used for dataset_id.

    For ``1h`` / ``4h`` / ``1d``: midnight UTC of the current UTC day so two
    calls the same day share one id. For ``15m``: last closed 15m boundary.
    """
    if timeframe in ("1h", "4h", "1d"):
        day_ms = 86_400_000
        return (int(now_ms) // day_ms) * day_ms
    step = _INTERVAL_MS.get(timeframe)
    if step is None:
        raise ValueError(f"unsupported interval for deep history: {timeframe!r}")
    return (int(now_ms) // step) * step


def _cache_window_ms(
    timeframe: str,
    years: float,
    *,
    now_ms: int | None = None,
) -> tuple[int, int]:
    raw_end = int(now_ms) if now_ms is not None else int(time.time() * 1000)
    end = _aligned_cache_end_ms(raw_end, timeframe)
    start = end - int(float(years) * 365.25 * 86400 * 1000)
    return start, end


def _series_payload_text(series_path: Path) -> str:
    text = series_path.read_text(encoding="utf-8")
    return text[:-1] if text.endswith("\n") else text


def _verify_series_sha256(series_path: Path, expected: str) -> None:
    digest = _sha256_bytes(_series_payload_text(series_path).encode("utf-8"))
    if digest != expected:
        raise ValueError(
            f"dataset sha256 mismatch for {series_path.name}: "
            f"expected {expected}, got {digest}"
        )


def _load_verified_candles(series_path: Path, expected_sha: str) -> list[Candle]:
    _verify_series_sha256(series_path, expected_sha)
    rows = json.loads(_series_payload_text(series_path))
    return _candles_from_jsonable(rows)


def _span_seconds(candles: Sequence[Candle]) -> int | None:
    if len(candles) < 2:
        return 0 if candles else None
    return int(candles[-1].time) - int(candles[0].time)


def _coverage_warning(
    candles: Sequence[Candle],
    *,
    requested_seconds: int | None,
) -> tuple[int | None, str | None]:
    """Warn when obtained span is shorter than requested coverage."""
    span = _span_seconds(candles)
    if span is None or requested_seconds is None or requested_seconds <= 0:
        return span, None
    if span >= int(requested_seconds):
        return span, None
    got_days = max(0, int(span) // 86400)
    want_days = max(1, int(requested_seconds) // 86400)
    return span, f"historique obtenu {got_days} j pour {want_days} demandés"


def _with_coverage(
    bundle: LabHistoryBundle,
    *,
    requested_seconds: int | None,
) -> LabHistoryBundle:
    span, hist_warn = _coverage_warning(
        bundle.candles, requested_seconds=requested_seconds
    )
    if (
        span == bundle.history_span_seconds
        and hist_warn == bundle.history_warning
    ):
        return bundle
    return LabHistoryBundle(
        dataset_id=bundle.dataset_id,
        candles=bundle.candles,
        manifest=bundle.manifest,
        quality=bundle.quality,
        data_warning=bundle.data_warning,
        history_span_seconds=span,
        history_warning=hist_warn,
    )


def _candles_to_jsonable(candles: Sequence[Candle]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for c in candles:
        out.append(
            {
                "time": int(c.time),
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": float(c.volume),
                "taker_buy_volume": c.taker_buy_volume,
                "volume_type": c.volume_type.value
                if hasattr(c.volume_type, "value")
                else str(c.volume_type),
            }
        )
    return out


def _candles_from_jsonable(rows: list[dict[str, Any]]) -> list[Candle]:
    out: list[Candle] = []
    for r in rows:
        vt_raw = r.get("volume_type") or "none"
        try:
            vt = VolumeType(str(vt_raw))
        except ValueError:
            vt = VolumeType.NONE
        tb = r.get("taker_buy_volume")
        out.append(
            Candle(
                time=int(r["time"]),
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
                volume=float(r.get("volume") or 0.0),
                taker_buy_volume=float(tb) if tb is not None else None,
                volume_type=vt,
            )
        )
    return out


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def quality_report_to_manifest(report: QualityReport) -> dict[str, Any]:
    """Codes + counts for manifeste (rév.51)."""
    return report.to_dict()


def _binance_fetch_range(
    symbol: str,
    interval: str,
    start_ms: int,
    end_ms: int,
    *,
    client: httpx.Client | None = None,
) -> list[Candle]:
    """Closed bars with open in ``[start_ms, end_ms)`` — startTime pagination."""
    if interval not in _INTERVAL_MS:
        raise ValueError(f"unsupported interval for deep history: {interval!r}")
    own = client is None
    client = client or httpx.Client()
    out: list[Candle] = []
    step = _INTERVAL_MS[interval]
    now_ms = int(time.time() * 1000)
    cur = start_ms
    try:
        while cur < end_ms:
            for attempt in range(5):
                r = client.get(
                    f"{BINANCE_BASE}/api/v3/klines",
                    params={
                        "symbol": symbol,
                        "interval": interval,
                        "startTime": cur,
                        "limit": 1000,
                    },
                    timeout=30.0,
                )
                if r.status_code in (418, 429):
                    time.sleep(int(r.headers.get("Retry-After", "5")) + 1)
                    continue
                r.raise_for_status()
                time.sleep(_MIN_SLEEP_S)
                rows = r.json()
                break
            else:
                raise RuntimeError(f"rate limited fetching {symbol} {interval}")
            if not rows:
                break
            for row in rows:
                open_ms = int(row[0])
                if open_ms >= end_ms:
                    break
                close_ms = int(row[6])
                if close_ms >= now_ms:
                    continue
                out.append(
                    Candle(
                        time=open_ms // 1000,
                        open=float(row[1]),
                        high=float(row[2]),
                        low=float(row[3]),
                        close=float(row[4]),
                        volume=float(row[5]),
                        taker_buy_volume=float(row[9]) if len(row) > 9 else None,
                        volume_type=VolumeType.EXCHANGE_VOLUME,
                    )
                )
            last_open = int(rows[-1][0])
            if last_open + step <= cur:
                break
            cur = last_open + step
            if len(rows) < 1000:
                break
    finally:
        if own:
            client.close()
    return out


def build_or_load_binance_history(
    symbol: str,
    timeframe: str = "1h",
    *,
    years: float = DEFAULT_CRYPTO_YEARS,
    end_ms: int | None = None,
    root: Path | None = None,
    client: httpx.Client | None = None,
    now: int | None = None,
) -> LabHistoryBundle:
    """Build (≥ ``years``) or load cached Binance deep history for Lab.

    ``dataset_id`` uses a day-aligned (1h/4h/1d) end so two calls the same
    UTC day hit the same cache entry.
    """
    if timeframe not in TF_SECONDS:
        raise ValueError(f"timeframe must be one of {sorted(TF_SECONDS)}")
    root = _datasets_root(root)
    raw_end = end_ms if end_ms is not None else int(time.time() * 1000)
    start, end = _cache_window_ms(timeframe, years, now_ms=raw_end)
    requested_seconds = max(0, (end - start) // 1000)
    dataset_id = f"binance_{symbol.upper()}_{timeframe}_{start}_{end}"
    man = _load_manifest(root)
    series_path = root / f"{dataset_id}.json"

    if dataset_id in man and series_path.exists():
        entry = man[dataset_id]
        expected = str(entry.get("sha256") or "")
        if not expected:
            raise ValueError(f"dataset manifest missing sha256: {dataset_id!r}")
        candles = _load_verified_candles(series_path, expected)
        quality = dict(entry.get("quality") or {})
        warning = (
            "dataset quality degraded — usable with caution"
            if entry.get("degraded")
            else None
        )
        bundle = LabHistoryBundle(
            dataset_id=dataset_id,
            candles=candles,
            manifest=entry,
            quality=quality,
            data_warning=warning,
        )
        return _with_coverage(bundle, requested_seconds=requested_seconds)

    candles = _binance_fetch_range(
        symbol.upper(), timeframe, start, end, client=client
    )
    return _persist_bundle(
        root,
        dataset_id=dataset_id,
        provider="binance",
        symbol=symbol.upper(),
        timeframe=timeframe,
        candles=candles,
        start_ms=start,
        end_ms=end,
        now=now,
        requested_seconds=requested_seconds,
    )


def build_or_load_from_candles(
    candles: Sequence[Candle],
    *,
    dataset_id: str,
    provider: str,
    symbol: str,
    timeframe: str,
    start_ms: int | None = None,
    end_ms: int | None = None,
    root: Path | None = None,
    now: int | None = None,
    requested_seconds: int | None = None,
) -> LabHistoryBundle:
    """Validate + persist an in-memory series (tests / offline inject)."""
    root = _datasets_root(root)
    if not candles:
        raise ValueError("candles must be non-empty")
    s_ms = start_ms if start_ms is not None else int(candles[0].time) * 1000
    e_ms = (
        end_ms
        if end_ms is not None
        else (int(candles[-1].time) + TF_SECONDS.get(timeframe, 3600)) * 1000
    )
    req = (
        requested_seconds
        if requested_seconds is not None
        else max(0, (e_ms - s_ms) // 1000)
    )
    return _persist_bundle(
        root,
        dataset_id=dataset_id,
        provider=provider,
        symbol=symbol.upper(),
        timeframe=timeframe,
        candles=list(candles),
        start_ms=s_ms,
        end_ms=e_ms,
        now=now,
        requested_seconds=req,
    )


def load_dataset(dataset_id: str, *, root: Path | None = None) -> LabHistoryBundle:
    root = _datasets_root(root)
    man = _load_manifest(root)
    if dataset_id not in man:
        raise ValueError(f"unknown dataset_id: {dataset_id!r}")
    series_path = root / f"{dataset_id}.json"
    if not series_path.exists():
        raise ValueError(f"dataset file missing: {series_path}")
    entry = man[dataset_id]
    expected = str(entry.get("sha256") or "")
    if not expected:
        raise ValueError(f"dataset manifest missing sha256: {dataset_id!r}")
    candles = _load_verified_candles(series_path, expected)
    quality = dict(entry.get("quality") or {})
    warning = (
        "dataset quality degraded — usable with caution"
        if entry.get("degraded")
        else None
    )
    start_ms = entry.get("start_ms")
    end_ms = entry.get("end_ms")
    requested = None
    if isinstance(start_ms, int) and isinstance(end_ms, int) and end_ms > start_ms:
        requested = (end_ms - start_ms) // 1000
    bundle = LabHistoryBundle(
        dataset_id=dataset_id,
        candles=candles,
        manifest=entry,
        quality=quality,
        data_warning=warning,
    )
    return _with_coverage(bundle, requested_seconds=requested)


def _persist_bundle(
    root: Path,
    *,
    dataset_id: str,
    provider: str,
    symbol: str,
    timeframe: str,
    candles: list[Candle],
    start_ms: int,
    end_ms: int,
    now: int | None,
    requested_seconds: int | None = None,
) -> LabHistoryBundle:
    tf_sec = TF_SECONDS.get(timeframe)
    if tf_sec is None:
        raise ValueError(f"unknown timeframe: {timeframe!r}")
    report = validate_candles(candles, tf_sec, now=now)
    quality = quality_report_to_manifest(report)
    payload = _candles_to_jsonable(candles)
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    digest = _sha256_bytes(body.encode("utf-8"))
    series_path = root / f"{dataset_id}.json"
    series_path.write_text(body + "\n", encoding="utf-8")
    entry: dict[str, Any] = {
        "dataset_id": dataset_id,
        "provider": provider,
        "symbol": symbol,
        "timeframe": timeframe,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "n_bars": len(candles),
        "first_time": int(candles[0].time) if candles else None,
        "last_time": int(candles[-1].time) if candles else None,
        "sha256": digest,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "quality": quality,
        "degraded": not report.ok,
        "twelve_data_max_bars": TWELVE_DATA_MAX_BARS,
    }
    man = _load_manifest(root)
    man[dataset_id] = entry
    _save_manifest(root, man)
    warning = (
        "dataset quality degraded — usable with caution" if not report.ok else None
    )
    req = (
        requested_seconds
        if requested_seconds is not None
        else max(0, (end_ms - start_ms) // 1000)
    )
    bundle = LabHistoryBundle(
        dataset_id=dataset_id,
        candles=candles,
        manifest=entry,
        quality=quality,
        data_warning=warning,
    )
    return _with_coverage(bundle, requested_seconds=req)


def twelve_data_max_bars() -> int:
    return TWELVE_DATA_MAX_BARS


def bundle_from_live_candles(
    candles: Sequence[Candle],
    *,
    symbol: str,
    timeframe: str,
    provider: str = "live",
    dataset_id: str | None = None,
    now: int | None = None,
    requested_seconds: int | None = None,
) -> LabHistoryBundle:
    """Validate candles for a Lab study without writing the datasets cache."""
    if not candles:
        raise ValueError("candles must be non-empty")
    tf_sec = TF_SECONDS.get(timeframe)
    if tf_sec is None:
        raise ValueError(f"unknown timeframe: {timeframe!r}")
    report = validate_candles(candles, tf_sec, now=now)
    quality = quality_report_to_manifest(report)
    did = dataset_id or f"live_{symbol.upper()}_{timeframe}_{len(candles)}"
    entry: dict[str, Any] = {
        "dataset_id": did,
        "provider": provider,
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "n_bars": len(candles),
        "first_time": int(candles[0].time),
        "last_time": int(candles[-1].time),
        "quality": quality,
        "degraded": not report.ok,
        "persisted": False,
        "twelve_data_max_bars": TWELVE_DATA_MAX_BARS,
    }
    warning = (
        "dataset quality degraded — usable with caution" if not report.ok else None
    )
    bundle = LabHistoryBundle(
        dataset_id=did,
        candles=list(candles),
        manifest=entry,
        quality=quality,
        data_warning=warning,
    )
    return _with_coverage(bundle, requested_seconds=requested_seconds)


def resolve_lab_history(
    symbol: str,
    timeframe: str = "1h",
    *,
    limit: int = 1000,
    deep_history: bool = False,
    years: float = DEFAULT_CRYPTO_YEARS,
    dataset_id: str | None = None,
    exchange: str = "binance",
    root: Path | None = None,
    now: int | None = None,
    client: httpx.Client | None = None,
) -> LabHistoryBundle:
    """Resolve candles for Lab studies with quality always attached.

    - ``dataset_id`` → load versioned cache (sha256 verified)
    - ``deep_history`` + Binance → ≥ ``years`` via startTime pagination + persist
    - ``deep_history`` + other providers → ``resolve_and_fetch`` capped at
      ``TWELVE_DATA_MAX_BARS`` (5 000), then validate + persist
    - otherwise → live fetch + validate (ephemeral, not persisted)
    """
    from app.market_data.resolve import resolve, resolve_and_fetch

    sym = symbol.upper()
    exch = (exchange or "binance").lower()

    if dataset_id:
        return load_dataset(str(dataset_id).strip(), root=root)

    provider, _psym = resolve(sym, exch)
    requested_years_s = int(float(years) * 365.25 * 86400)

    if deep_history:
        if provider.id == "binance":
            return build_or_load_binance_history(
                sym,
                timeframe,
                years=years,
                root=root,
                client=client,
                now=now,
            )
        # Twelve Data / biquote / FX: hard cap 5 000 bars (provider limit).
        want = min(max(int(limit), 300), TWELVE_DATA_MAX_BARS)
        prov, _psym2, candles = resolve_and_fetch(
            sym, timeframe, want, default_provider=exchange
        )
        if len(candles) < 2:
            raise ValueError(f"not enough candles for {sym} {timeframe}")
        raw_end = int(time.time() * 1000)
        start_ms, end_ms = _cache_window_ms(timeframe, years, now_ms=raw_end)
        did = f"{prov.id}_{sym}_{timeframe}_{start_ms}_{end_ms}"
        # Cache hit if already persisted under the day-aligned id.
        man = _load_manifest(_datasets_root(root))
        series_path = _datasets_root(root) / f"{did}.json"
        if did in man and series_path.exists():
            return load_dataset(did, root=root)
        return build_or_load_from_candles(
            candles,
            dataset_id=did,
            provider=prov.id,
            symbol=sym,
            timeframe=timeframe,
            start_ms=start_ms,
            end_ms=end_ms,
            root=root,
            now=now,
            requested_seconds=requested_years_s,
        )

    prov, _psym2, candles = resolve_and_fetch(
        sym, timeframe, int(limit), default_provider=exchange
    )
    if len(candles) < 2:
        raise ValueError(f"not enough candles for {sym} {timeframe}")
    req = int(limit) * int(TF_SECONDS.get(timeframe, 3600))
    return bundle_from_live_candles(
        candles,
        symbol=sym,
        timeframe=timeframe,
        provider=prov.id,
        now=now,
        requested_seconds=req,
    )


__all__ = [
    "DATASETS_DIR",
    "DEFAULT_CRYPTO_YEARS",
    "LabHistoryBundle",
    "TWELVE_DATA_MAX_BARS",
    "build_or_load_binance_history",
    "build_or_load_from_candles",
    "bundle_from_live_candles",
    "load_dataset",
    "quality_report_to_manifest",
    "resolve_lab_history",
    "twelve_data_max_bars",
]
