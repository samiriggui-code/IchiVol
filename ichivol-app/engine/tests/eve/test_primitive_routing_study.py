"""Tests déterminant le routage Mode × NOUL/CHOICE/SCORE."""

from __future__ import annotations

from app.eve.calibration import active_policy
from app.eve.primitive_study import (
    MODES,
    PRIMITIVES,
    run_primitive_routing_study,
)


def test_study_covers_full_matrix() -> None:
    report = run_primitive_routing_study()
    assert report["schema"] == "ichivol.eve.primitive_routing_study.v1"
    assert len(report["cells"]) == len(MODES) * len(PRIMITIVES)
    for cell in report["cells"]:
        assert cell["verdict"] in {"YES", "NO", "CONDITIONAL"}
        assert "metrics" in cell


def test_study_does_not_force_all_primitives_everywhere() -> None:
    """Garde-fou : l'étude ne doit pas conclure YES pour les 12 cellules (sur-estimation)."""
    report = run_primitive_routing_study()
    yes = [c for c in report["cells"] if c["verdict"] == "YES"]
    no = [c for c in report["cells"] if c["verdict"] == "NO"]
    assert len(yes) < 12
    assert len(no) >= 1  # au moins une combinaison rejetée


def test_recommended_routing_is_selective() -> None:
    report = run_primitive_routing_study()
    routing = report["recommended_routing"]
    # Analyst: SCORE is primary fit
    assert "score" in routing["analyst"]
    # Challenger: CHOICE is primary fit
    assert "choice" in routing["challenger"]
    # Guardian: NOUL is primary fit
    assert "noul" in routing["guardian"]
    # Shadow protocol: at least NOUL; study may add choice/score
    assert "noul" in routing["shadow"]
    # Explicitly not: analyst must not require all three blindly
    assert routing["analyst"] != ["noul", "choice", "score"]


def test_policy_embeds_study_routing() -> None:
    policy = active_policy()
    routing = policy["routing"]
    assert "analyst_primitives" in routing
    assert "challenger_primitives" in routing
    assert "guardian_primitives" in routing
    assert "shadow_primitives" in routing
    assert policy["version"].startswith("eve.policy.v1")
    cells = policy.get("primitive_study", {}).get("cells") or []
    assert len(cells) == 12


def test_print_matrix_for_humans(capsys) -> None:
    """Affiche la matrice dans la sortie de test (preuve lisible)."""
    report = run_primitive_routing_study()
    print("\nMode×Primitive routing study")
    print(f"{'mode':12} {'primitive':8} {'verdict':12} reason")
    for cell in report["cells"]:
        print(
            f"{cell['mode']:12} {cell['primitive']:8} {cell['verdict']:12} {cell['reason']}"
        )
    print("recommended:", report["recommended_routing"])
    captured = capsys.readouterr()
    assert "analyst" in captured.out
    assert "recommended:" in captured.out
