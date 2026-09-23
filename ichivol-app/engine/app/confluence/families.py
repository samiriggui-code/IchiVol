"""Product confluence families — aligned on pipeline StageId values.

TREND is an alias product name for ``direction`` (Ichimoku sets direction).
IndicatorCategory (TREND/VOLUME/…) is a separate registry taxonomy and is
not used as weight keys.
"""

from __future__ import annotations

from enum import Enum


class ConfluenceFamily(str, Enum):
    DIRECTION = "direction"
    PARTICIPATION = "participation"
    STRUCTURE = "structure"
    LOCATION = "location"
    REGIME = "regime"


# Product alias used in docs / audit tables (TREND ≡ direction).
FAMILY_ALIASES: dict[str, ConfluenceFamily] = {
    "trend": ConfluenceFamily.DIRECTION,
    "TREND": ConfluenceFamily.DIRECTION,
}

ALL_FAMILIES: tuple[ConfluenceFamily, ...] = tuple(ConfluenceFamily)
