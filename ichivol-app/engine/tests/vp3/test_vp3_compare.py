"""compare_question wiring smoke (no VP1 disk)."""

from vp3.compare import COMPARE_QUESTIONS


def test_compare_questions_map():
    assert COMPARE_QUESTIONS["A"] == ("B1", "B0")
    assert COMPARE_QUESTIONS["B"] == ("B2", "B1")
    assert COMPARE_QUESTIONS["H"] == ("B5", "B2")
