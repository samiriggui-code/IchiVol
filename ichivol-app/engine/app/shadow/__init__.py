"""ShadowBroker package — counterfactual execution outside Paper cash."""

from app.shadow.broker import (
    list_shadows,
    mark_shadows,
    open_shadow,
    shadow_stats,
    shadow_to_dict,
)

__all__ = [
    "list_shadows",
    "mark_shadows",
    "open_shadow",
    "shadow_stats",
    "shadow_to_dict",
]
