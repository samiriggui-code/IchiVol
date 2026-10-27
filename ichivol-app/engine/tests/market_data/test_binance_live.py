"""Flux direct Binance : parsing, cache, flux figé → dégradé, reconnexion, retour REST. Aucun réseau réel."""

from __future__ import annotations

import asyncio
import json

from app.market_data.binance_live import (
    BinanceLiveFeed,
    LivePriceCache,
    LiveQuote,
    parse_book_ticker_message,
    parse_rest_book_tickers,
)


def _bt(symbol="BTCUSDT", bid="100.0", ask="100.5", u=1) -> str:
    return json.dumps({"stream": f"{symbol.lower()}@bookTicker",
                       "data": {"u": u, "s": symbol, "b": bid, "B": "1.5", "a": ask, "A": "2"}})


def test_parse_combined_book_ticker():
    q = parse_book_ticker_message(_bt(), 1234)
    assert q == LiveQuote("BTCUSDT", 100.0, 100.5, 1234, bid_qty=1.5, ask_qty=2.0, source="ws", update_id=1)
    assert q.mid == 100.25


def test_parse_rejects_garbage_crossed_and_zero():
    assert parse_book_ticker_message('{"result":null,"id":1}', 1) is None
    assert parse_book_ticker_message("pas du json", 1) is None
    assert parse_book_ticker_message(_bt(bid="101", ask="100"), 1) is None  # carnet croisé
    assert parse_book_ticker_message(_bt(bid="0", ask="1"), 1) is None


def test_parse_rest_book_tickers():
    rows = [{"symbol": "ETHUSDT", "bidPrice": "10", "bidQty": "1", "askPrice": "10.1", "askQty": "2"},
            {"symbol": "BAD", "bidPrice": "x"}]
    qs = parse_rest_book_tickers(rows, 5)
    assert [(q.symbol, q.bid, q.ask, q.source) for q in qs] == [("ETHUSDT", 10.0, 10.1, "rest")]


def test_cache_keeps_newest_and_honours_max_age():
    c = LivePriceCache()
    c.put(LiveQuote("BTCUSDT", 1, 2, received_ms=2000))
    c.put(LiveQuote("BTCUSDT", 5, 6, received_ms=1000, source="rest"))  # plus ancien : ignoré
    assert c.get("btcusdt").bid == 1
    assert c.get("BTCUSDT", max_age_ms=500, at_ms=2400) is not None
    assert c.get("BTCUSDT", max_age_ms=500, at_ms=2600) is None


class FakeClock:
    def __init__(self, t=1_000_000):
        self.t = t

    def __call__(self) -> int:
        return self.t


class FakeWS:
    """Faux WebSocket : rend des messages, puis se tait (flux figé) ou lève (coupure)."""

    def __init__(self, messages, *, then="silence", clock=None, step_ms=0):
        self.messages = list(messages)
        self.then = then
        self.clock = clock
        self.step_ms = step_ms

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def recv(self):
        if self.messages:
            return self.messages.pop(0)
        if self.then == "error":
            raise ConnectionError("coupure simulée")
        if self.clock is not None:
            self.clock.t += self.step_ms  # le temps passe sans message
        await asyncio.sleep(0.01)
        raise TimeoutError


class FailingConnect:
    async def __aenter__(self):
        raise OSError("connexion refusée")

    async def __aexit__(self, *exc):
        return False


def test_stream_url_is_combined_book_ticker():
    f = BinanceLiveFeed(symbols=["ethusdt", "BTCUSDT", "BTCUSDT"])
    assert f.stream_url == "wss://data-stream.binance.vision/stream?streams=btcusdt@bookTicker/ethusdt@bookTicker"


def test_messages_feed_cache_and_callback_and_live_state():
    clock = FakeClock()
    seen: list[LiveQuote] = []
    f = BinanceLiveFeed(symbols=["BTCUSDT"], on_quote=seen.append, clock_ms=clock, stale_after_s=10)
    assert f.state() == "degraded"  # rien reçu : pas « en direct »
    f.stats.connected = True
    f.handle_message(_bt(bid="200", ask="201"))
    assert f.cache.get("BTCUSDT").bid == 200.0 and len(seen) == 1
    assert f.state() == "live"
    clock.t += 10_001
    assert f.state() == "degraded"  # aucun message depuis plus de 10 s
    assert f.status()["rest_fallback"] is True


def test_on_quote_failure_never_breaks_the_feed():
    def boom(_q):
        raise RuntimeError("consommateur fautif")

    f = BinanceLiveFeed(symbols=["BTCUSDT"], on_quote=boom)
    assert f.handle_message(_bt()) is not None
    assert f.cache.get("BTCUSDT") is not None


def test_frozen_stream_is_detected_and_reconnects_then_coupure_reconnects_with_backoff():
    clock = FakeClock()
    connections: list[str] = []
    stop_holder: dict = {}

    def connect(url):
        connections.append(url)
        n = len(connections)
        if n == 1:  # un message, puis plus rien : flux figé
            return FakeWS([_bt(u=1)], then="silence", clock=clock, step_ms=4_000)
        if n == 2:  # refus de connexion (DNS, réseau)
            return FailingConnect()
        if n == 3:  # un message puis coupure réseau
            return FakeWS([_bt(u=2, bid="300", ask="301")], then="error")
        stop_holder["stop"].set()  # quatrième connexion : fin du test
        return FakeWS([_bt(u=3, bid="400", ask="401")], then="error")

    f = BinanceLiveFeed(symbols=["BTCUSDT"], connect=connect, clock_ms=clock, stale_after_s=10)
    waits: list[float] = []

    async def no_wait(stop, seconds):
        waits.append(seconds)

    f._wait = no_wait  # type: ignore[method-assign]

    async def main():
        stop = asyncio.Event()
        stop_holder["stop"] = stop
        await asyncio.wait_for(f.run(stop), timeout=5)

    asyncio.run(main())
    assert len(connections) == 4
    assert f.stats.stale_events == 1
    assert f.stats.reconnects == 3
    # figé (1 s), refus (2 s : doublé), puis coupure après un message (remis à 1 s)
    assert waits == [1.0, 2.0, 1.0]
    assert "coupure" in (f.stats.last_error or "")
    assert f.cache.get("BTCUSDT").bid == 300.0  # la 4e connexion est fermée dès l'arrêt demandé
    assert f.stats.connected is False


def test_rest_fallback_polls_only_when_degraded():
    clock = FakeClock()
    calls: list[list[str]] = []

    def fetch(symbols):
        calls.append(symbols)
        return [{"symbol": "BTCUSDT", "bidPrice": "99", "bidQty": "1", "askPrice": "99.5", "askQty": "1"}]

    seen: list[LiveQuote] = []
    f = BinanceLiveFeed(symbols=["BTCUSDT"], rest_fetch=fetch, clock_ms=clock, on_quote=seen.append, rest_poll_s=0.01)
    assert f.poll_rest_once() == 1
    assert f.cache.get("BTCUSDT").source == "rest" and seen[-1].bid == 99.0
    assert f.status()["rest_polls"] == 1

    async def run_loop(live: bool) -> int:
        calls.clear()
        f.stats.connected = live
        f.stats.last_message_ms = clock.t if live else None
        stop = asyncio.Event()

        async def stopper():
            await asyncio.sleep(0.05)
            stop.set()

        await asyncio.gather(f.rest_fallback_loop(stop), stopper())
        return len(calls)

    assert asyncio.run(run_loop(live=False)) >= 1
    assert asyncio.run(run_loop(live=True)) == 0


def test_rest_error_is_counted_not_raised():
    def fetch(_s):
        raise ConnectionError("hors ligne")

    f = BinanceLiveFeed(symbols=["BTCUSDT"], rest_fetch=fetch)
    assert f.poll_rest_once() == 0
    assert f.stats.rest_errors == 1 and "hors ligne" in f.stats.last_error


def test_empty_symbol_list_is_inactive():
    f = BinanceLiveFeed(symbols=[])
    assert f.state() == "inactive"
    asyncio.run(f.run(asyncio.Event()))  # rend la main immédiatement
