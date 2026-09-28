"""AG-S0 — calendrier des sessions (lecture seule)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.config import settings
from app.sessions.calendar import build_session_calendar

router = APIRouter(prefix=settings.engine_api_prefix, tags=["sessions"])


@router.get("/sessions")
def get_sessions(
    now: int | None = Query(
        default=None,
        description="Unix seconds (tests). Default: serveur UTC.",
    ),
) -> dict:
    """Sessions en cours, prochaine ouverture, prochaine clôture 1d."""
    as_of = (
        datetime.fromtimestamp(int(now), tz=timezone.utc)
        if now is not None
        else datetime.now(timezone.utc)
    )
    return build_session_calendar(as_of).to_dict()
