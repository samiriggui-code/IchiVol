"""Fenêtres de décision « ouvertures / fermetures des grandes places » pour le paper automatique.

Un profil qui porte ``decision_windows`` (liste d'événements ci-dessous) n'ouvre une position et ne la ferme
sur signal qu'aux bougies 1h liées à ces événements. Stop / objectif restent surveillés en continu
(``app/paper/protection.py`` + ``check_stop_or_tp``) : la fenêtre ne retarde jamais une protection.

Bougie retenue (la décision reste sur bougie **close**, comme partout ailleurs) :
- ouverture ``T`` → première bougie qui contient de l'activité de séance, close au premier multiple de la
  bougie **strictement après** ``T`` (Tokyo 09:00 JST → bougie close 10:00 JST ; NY 09:30 ET → 10:00 ET) ;
- fermeture ``T`` → dernière bougie qui contient de l'activité de séance, close au premier multiple
  **à ou après** ``T`` (Londres 16:30 → 17:00 ; NY 16:00 → 16:00 ET).

Heures en heure locale de place + fuseau IANA : l'heure d'été est absorbée par ``zoneinfo`` (Londres et
New York ne changent pas d'heure le même jour). Week-ends locaux sautés. Jours fériés **non gérés** (v1).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

UTC = timezone.utc


@dataclass(frozen=True)
class MarketEvent:
    key: str
    tz_name: str
    hour: int
    minute: int
    kind: str  # "open" | "close"


MARKET_EVENTS: dict[str, MarketEvent] = {
    e.key: e
    for e in (
        MarketEvent("tokyo_open", "Asia/Tokyo", 9, 0, "open"),
        MarketEvent("tokyo_close", "Asia/Tokyo", 15, 30, "close"),  # TSE ferme à 15:30 depuis 2024-11-05
        MarketEvent("london_open", "Europe/London", 8, 0, "open"),
        MarketEvent("london_close", "Europe/London", 16, 30, "close"),
        MarketEvent("ny_open", "America/New_York", 9, 30, "open"),
        MarketEvent("ny_close", "America/New_York", 16, 0, "close"),
    )
}

DEFAULT_DECISION_WINDOWS: tuple[str, ...] = tuple(MARKET_EVENTS)


def _event_utc(event: MarketEvent, local_day: date) -> datetime:
    local = datetime(local_day.year, local_day.month, local_day.day, event.hour, event.minute, tzinfo=ZoneInfo(event.tz_name))
    return local.astimezone(UTC)


def decision_bar_close(event: MarketEvent, local_day: date, bar_seconds: int = 3600) -> int:
    """Epoch (s) of the close of the candle that carries ``event`` on ``local_day`` (rule in module doc)."""
    t = int(_event_utc(event, local_day).timestamp())
    if event.kind == "open":
        return (t // bar_seconds + 1) * bar_seconds
    return -(-t // bar_seconds) * bar_seconds


def decision_event_for_bar(
    bar_close_s: int,
    events: Iterable[str],
    bar_seconds: int = 3600,
) -> str | None:
    """Key of the first configured event whose decision candle closes at ``bar_close_s``, else None.

    Unknown keys are ignored. Events falling on a local Saturday/Sunday do not exist.
    """
    bar_utc = datetime.fromtimestamp(int(bar_close_s), tz=UTC)
    for key in events:
        event = MARKET_EVENTS.get(key)
        if event is None:
            continue
        local_day = bar_utc.astimezone(ZoneInfo(event.tz_name)).date()
        # The decision candle closes within a few hours of the event: check the neighbouring local days too.
        for day in (local_day - timedelta(days=1), local_day, local_day + timedelta(days=1)):
            if day.weekday() >= 5:
                continue
            if decision_bar_close(event, day, bar_seconds) == int(bar_close_s):
                return key
    return None
