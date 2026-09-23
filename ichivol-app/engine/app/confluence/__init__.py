"""T5a/T5b — versioned family weights (observation-only).

Never alters decision, confidence, pipeline votes, or gates.
T5b adds named profiles + historical study (still observation-only).
"""

from app.confluence.compare import compare_family_weight_profiles
from app.confluence.families import ConfluenceFamily
from app.confluence.observe import (
    FamilyWeightsObservation,
    family_weights_observation_dict,
    observe_family_weights,
)
from app.confluence.profiles import (
    FAMILY_WEIGHT_PROFILES,
    FamilyWeightProfile,
    get_family_weight_profile,
    list_family_weight_profiles,
)
from app.confluence.study import FamilyWeightsStudyReport, run_family_weights_study
from app.confluence.weights import (
    DEFAULT_FAMILY_WEIGHTS,
    FAMILY_WEIGHTS_VERSION,
    FamilyWeightsConfig,
)

__all__ = [
    "ConfluenceFamily",
    "DEFAULT_FAMILY_WEIGHTS",
    "FAMILY_WEIGHTS_VERSION",
    "FAMILY_WEIGHT_PROFILES",
    "FamilyWeightProfile",
    "FamilyWeightsConfig",
    "FamilyWeightsObservation",
    "FamilyWeightsStudyReport",
    "compare_family_weight_profiles",
    "family_weights_observation_dict",
    "get_family_weight_profile",
    "list_family_weight_profiles",
    "observe_family_weights",
    "run_family_weights_study",
]
