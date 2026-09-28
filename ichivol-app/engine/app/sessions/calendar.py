"""AG-S0 — calendrier des sessions crypto (repères horaires).

Sessions Asie / Europe / US calculées avec ``zoneinfo`` (heure d'été gérée)
+ clôture bougie 1d à 00:00 UTC. Crypto 24/7 : le week-end reste un repère
horaire, jamais une fermeture de marché.

Observe-only : aucun effet pipeline / paper / gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc


@dataclass(frozen=True)
class SessionDef:
    key: str
    label: str
    tz_name: str
    open_hour: int
    open_minute: int
    close_hour: int
    close_minute: int

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.tz_name)


# Fenêtres alignées sur le calendrier FX déjà utilisé côté server (agentsRoute),
# mais sans skip week-end : crypto = repère horaire 24/7.
SESSION_DEFS: tuple[SessionDef, ...] = (
    SessionDef(
        key="asia",
        label="Asie",
        tz_name="Asia/Tokyo",
        open_hour=9,
        open_minute=0,
        close_hour=18,
        close_minute=0,
    ),
    SessionDef(
        key="europe",
        label="Europe",
        tz_name="Europe/London",
        open_hour=8,
        open_minute=0,
        close_hour=17,
        close_minute=0,
    ),
    SessionDef(
        key="us",
        label="US",
        tz_name="America/New_York",
        open_hour=9,
        open_minute=30,
        close_hour=16,
        close_minute=0,
    ),
)


@dataclass(frozen=True)
class SessionWindow:
    key: str
    label: str
    tz_name: str
    open_utc: datetime
    close_utc: datetime
    open_local: str
    close_local: str
    session_id: str
    open: bool


@dataclass(frozen=True)
class SessionCalendarSnapshot:
    as_of_utc: datetime
    open_sessions: tuple[SessionWindow, ...]
    next_open: SessionWindow | None
    next_daily_close_utc: datetime

    def to_dict(self) -> dict:
        def _win(w: SessionWindow) -> dict:
            return {
                "key": w.key,
                "label": w.label,
                "tz": w.tz_name,
                "session_id": w.session_id,
                "open": w.open,
                "open_utc": w.open_utc.isoformat().replace("+00:00", "Z"),
                "close_utc": w.close_utc.isoformat().replace("+00:00", "Z"),
                "open_local": w.open_local,
                "close_local": w.close_local,
            }

        nxt = self.next_open
        return {
            "as_of_utc": self.as_of_utc.isoformat().replace("+00:00", "Z"),
            "crypto_24_7": True,
            "open_sessions": [_win(w) for w in self.open_sessions],
            "open_count": len(self.open_sessions),
            "next_open": _win(nxt) if nxt is not None else None,
            "next_daily_close_utc": self.next_daily_close_utc.isoformat().replace(
                "+00:00", "Z"
            ),
            "sessions": [_win(w) for w in _windows_for_day(self.as_of_utc)],
            "upcoming_opens": [
                _win(w) for w in upcoming_session_opens(self.as_of_utc, horizon_hours=48)
            ],
        }


def _aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _local_wall(dt_utc: datetime, tz: ZoneInfo) -> datetime:
    return _aware_utc(dt_utc).astimezone(tz)


def wall_time_to_utc(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int,
    tz: ZoneInfo,
) -> datetime:
    """Convert a local wall-clock time to UTC (DST absorbed by zoneinfo)."""
    local = datetime(year, month, day, hour, minute, 0, tzinfo=tz)
    return local.astimezone(UTC)


def session_id_for(defn: SessionDef, open_utc: datetime) -> str:
    local = open_utc.astimezone(defn.tz)
    return f"{defn.key}:{local.date().isoformat()}"


def _window_on_local_date(defn: SessionDef, local_day: date) -> SessionWindow:
    open_utc = wall_time_to_utc(
        local_day.year,
        local_day.month,
        local_day.day,
        defn.open_hour,
        defn.open_minute,
        defn.tz,
    )
    close_utc = wall_time_to_utc(
        local_day.year,
        local_day.month,
        local_day.day,
        defn.close_hour,
        defn.close_minute,
        defn.tz,
    )
    open_local = f"{defn.open_hour:02d}:{defn.open_minute:02d}"
    close_local = f"{defn.close_hour:02d}:{defn.close_minute:02d}"
    return SessionWindow(
        key=defn.key,
        label=defn.label,
        tz_name=defn.tz_name,
        open_utc=open_utc,
        close_utc=close_utc,
        open_local=open_local,
        close_local=close_local,
        session_id=session_id_for(defn, open_utc),
        open=False,
    )


def _windows_for_day(now: datetime) -> tuple[SessionWindow, ...]:
    """Today's windows in each venue's local calendar (for status display)."""
    now = _aware_utc(now)
    out: list[SessionWindow] = []
    for defn in SESSION_DEFS:
        local = _local_wall(now, defn.tz)
        w = _window_on_local_date(defn, local.date())
        is_open = w.open_utc <= now < w.close_utc
        out.append(
            SessionWindow(
                key=w.key,
                label=w.label,
                tz_name=w.tz_name,
                open_utc=w.open_utc,
                close_utc=w.close_utc,
                open_local=w.open_local,
                close_local=w.close_local,
                session_id=w.session_id,
                open=is_open,
            )
        )
    return tuple(out)


def open_sessions_at(now: datetime) -> tuple[SessionWindow, ...]:
    """Sessions whose [open, close) contains ``now`` (week-end inclus)."""
    return tuple(w for w in _windows_for_day(now) if w.open)


def next_session_open(now: datetime) -> SessionWindow | None:
    """Prochaine ouverture parmi Asie / Europe / US (ordre chronologique).

    Crypto 24/7 : on ne saute pas le week-end — le repère horaire reste.
    """
    now = _aware_utc(now)
    candidates: list[SessionWindow] = []
    for defn in SESSION_DEFS:
        local = _local_wall(now, defn.tz)
        for delta in range(0, 8):
            day = local.date() + timedelta(days=delta)
            w = _window_on_local_date(defn, day)
            if w.open_utc > now:
                candidates.append(w)
                break
    if not candidates:
        return None
    candidates.sort(key=lambda w: (w.open_utc, w.key))
    return candidates[0]


def next_daily_close_utc(now: datetime) -> datetime:
    """Prochaine clôture bougie 1d = prochain 00:00 UTC strictement futur."""
    now = _aware_utc(now)
    midnight = datetime(now.year, now.month, now.day, tzinfo=UTC)
    if now < midnight:
        return midnight
    return midnight + timedelta(days=1)


def build_session_calendar(now: datetime | None = None) -> SessionCalendarSnapshot:
    as_of = _aware_utc(now or datetime.now(UTC))
    return SessionCalendarSnapshot(
        as_of_utc=as_of,
        open_sessions=open_sessions_at(as_of),
        next_open=next_session_open(as_of),
        next_daily_close_utc=next_daily_close_utc(as_of),
    )


def upcoming_session_opens(
    now: datetime | None = None,
    *,
    horizon_hours: int = 48,
) -> list[SessionWindow]:
    """Toutes les ouvertures dans ``horizon_hours`` (pour planification AgentTask)."""
    now = _aware_utc(now or datetime.now(UTC))
    horizon = now + timedelta(hours=horizon_hours)
    out: list[SessionWindow] = []
    for defn in SESSION_DEFS:
        local = _local_wall(now, defn.tz)
        for delta in range(0, max(3, horizon_hours // 12 + 2)):
            day = local.date() + timedelta(days=delta)
            w = _window_on_local_date(defn, day)
            if now < w.open_utc <= horizon:
                out.append(w)
    out.sort(key=lambda w: (w.open_utc, w.key))
    return out
