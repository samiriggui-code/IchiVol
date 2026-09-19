"""Unit tests for symbol_map.py -- pure python, no Wine/terminal needed.

The bridge's own runtime code (bridge_server.py) can't be exercised here
(it needs mt5linux + a live Wine/MT5 process), but the alias-resolution
logic it depends on is plain python against a fake client and is worth
testing in isolation.
"""

from __future__ import annotations

import pytest

from symbol_map import SymbolNotFoundError, resolve_symbol


class FakeMt5:
    def __init__(self, known_symbols: set[str]):
        self.known_symbols = known_symbols
        self.selected: list[str] = []

    def symbol_info(self, name: str):
        return object() if name in self.known_symbols else None

    def symbol_select(self, name: str, visible: bool) -> bool:
        self.selected.append(name)
        return True


def test_resolve_symbol_returns_first_matching_alias():
    client = FakeMt5({"XAUUSD.a"})
    resolved = resolve_symbol(client, "XAUUSD")
    assert resolved == "XAUUSD.a"
    assert client.selected == ["XAUUSD.a"]


def test_resolve_symbol_prefers_earlier_candidate_when_both_exist():
    client = FakeMt5({"XAUUSD", "XAUUSD.a"})
    assert resolve_symbol(client, "XAUUSD") == "XAUUSD"


def test_resolve_symbol_falls_back_to_raw_symbol_when_not_in_candidate_table():
    client = FakeMt5({"US30"})
    assert resolve_symbol(client, "US30") == "US30"


def test_resolve_symbol_raises_with_every_alias_tried_when_none_match():
    client = FakeMt5(set())
    with pytest.raises(SymbolNotFoundError, match="XAUUSD"):
        resolve_symbol(client, "XAUUSD")
