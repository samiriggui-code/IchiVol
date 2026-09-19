"""BrokerSymbolMap -- resolves a canonical IchiVol symbol to whatever alias
the connected broker actually uses (docs/TRADING_ARCHITECTURE_V2.md MT5
integration: "XAUUSD, XAUUSD.a, XAUUSDm, EURUSD.pro..." never assumed).

This runs inside the Wine/MT5 environment, not in the Linux engine -- only
this side can ask the live terminal "which of these aliases does this
broker actually list" via `mt5.symbols_get()`.

Deliberately a runtime probe, not a hardcoded per-broker table: broker
symbol suffixes vary constantly and a wrong guess should never silently
resolve to the wrong instrument.
"""

from __future__ import annotations

# Canonical id -> ordered list of aliases to try, most-common-first.
# Extend this list rather than guessing a new suffix scheme per broker.
_CANDIDATES: dict[str, list[str]] = {
    "XAUUSD": ["XAUUSD", "XAUUSD.a", "XAUUSDm", "GOLD", "GOLD.a"],
    "XAGUSD": ["XAGUSD", "XAGUSD.a", "XAGUSDm", "SILVER"],
    "EURUSD": ["EURUSD", "EURUSD.a", "EURUSD.pro", "EURUSDm"],
    "GBPUSD": ["GBPUSD", "GBPUSD.a", "GBPUSD.pro", "GBPUSDm"],
    "USDJPY": ["USDJPY", "USDJPY.a", "USDJPY.pro", "USDJPYm"],
    "SPX": ["US500", "SPX500", "US500.cash"],
    "NDX": ["USTEC", "NAS100", "USTEC.cash"],
}


class SymbolNotFoundError(ValueError):
    def __init__(self, canonical: str, tried: list[str]):
        super().__init__(f"mt5_symbol_not_found: {canonical!r} (tried {tried})")
        self.canonical = canonical
        self.tried = tried


def resolve_symbol(mt5_module, canonical: str) -> str:
    """`mt5_module` is the connected `MetaTrader5` (or `mt5linux`) client --
    passed in rather than imported here so this stays testable without a
    live terminal (see tests/test_symbol_map.py)."""
    candidates = _CANDIDATES.get(canonical.upper(), [canonical])
    tried: list[str] = []
    for candidate in candidates:
        tried.append(candidate)
        info = mt5_module.symbol_info(candidate)
        if info is not None:
            # Broker lists it but may have it hidden from Market Watch --
            # symbol_select makes it visible so copy_rates_* can read it.
            mt5_module.symbol_select(candidate, True)
            return candidate
    raise SymbolNotFoundError(canonical, tried)
