"""T5a — versioned family weights (observation-only).

Never alters decision, confidence, pipeline votes, or gates.
"""

from app.confluence.families import ConfluenceFamily
from app.confluence.observe import (
    FamilyWeightsObservation,
    family_weights_observation_dict,
    observe_family_weights,
)
from app.confluence.weights import (
    DEFAULT_FAMILY_WEIGHTS,
    FAMILY_WEIGHTS_VERSION,
    FamilyWeightsConfig,
)

__all__ = [
    "ConfluenceFamily",
    "DEFAULT_FAMILY_WEIGHTS",
    "FAMILY_WEIGHTS_VERSION",
    "FamilyWeightsConfig",
    "FamilyWeightsObservation",
    "family_weights_observation_dict",
    "observe_family_weights",
]
