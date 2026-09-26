"""Helpers for golden JSON comparisons across Python minor versions.

Python 3.12 changed ``sum()`` on floats (compensated summation). Goldens were
generated on 3.12; exact ``==`` can fail at ~1 ULP on 3.11. Floats use
``pytest.approx``; strings, bools, ints, and None stay strict.
"""

from __future__ import annotations

from typing import Any

import pytest

_REL = 1e-12
_ABS = 1e-12


def assert_golden_equal(actual: Any, expected: Any, *, path: str = "$") -> None:
    """Recursively compare golden payloads with float tolerance."""
    if isinstance(expected, float) or isinstance(actual, float):
        if actual is None or expected is None:
            assert actual == expected, f"{path}: {actual!r} != {expected!r}"
            return
        assert actual == pytest.approx(expected, rel=_REL, abs=_ABS), (
            f"{path}: {actual!r} !~ {expected!r} (rel={_REL}, abs={_ABS})"
        )
        return

    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"{path}: expected dict, got {type(actual).__name__}"
        assert set(actual.keys()) == set(expected.keys()), (
            f"{path}: keys {set(actual.keys()) ^ set(expected.keys())}"
        )
        for key in expected:
            assert_golden_equal(actual[key], expected[key], path=f"{path}.{key}")
        return

    if isinstance(expected, list):
        assert isinstance(actual, list), f"{path}: expected list, got {type(actual).__name__}"
        assert len(actual) == len(expected), f"{path}: len {len(actual)} != {len(expected)}"
        for i, (a, e) in enumerate(zip(actual, expected)):
            assert_golden_equal(a, e, path=f"{path}[{i}]")
        return

    assert actual == expected, f"{path}: {actual!r} != {expected!r}"
