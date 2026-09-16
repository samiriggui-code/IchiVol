"""SQLAlchemy models for the IchiVol engine's own database (`ichivol_engine_dev`).

Separate from `server/prisma/schema.prisma` (User/Setting/Decision — auth and
app settings, owned by the Node backend) by deliberate agreement: this
engine never writes to that schema, and the Node server never writes here.

Naming is chosen to be forward-compatible with the multi-agent Consensus /
Edge / Risk architecture proposed in docs/TRADING_ARCHITECTURE_V2.md,
without building that architecture now (see docs/INTEGRATION_PLAN.md,
which explicitly leaves Consensus/Edge/Risk/Execution as REWRITE-later
items, not part of this mission):

- `StrategySignal` / `AgentPrediction` use the exact names and field shapes
  proposed there, so a future Consensus Engine can read predictions this
  engine already writes (from ICHIMOKU_AGENT, later RVOL_AGENT) without a
  migration.
- `Decision` keeps this mission's own vocabulary (see the original brief's
  decision JSON shape: decision/confidence/reasons/risks/invalidation) but
  its fields are a superset compatible with the proposed `ConsensusDecision`
  (direction/probability/confidence/agreement/weights_used). Today it is
  produced by a fixed, hardcoded combiner over exactly two agents
  (ICHIMOKU_AGENT + RVOL_AGENT); `agreement`/`weights_used` are populated
  even in that degenerate two-agent case so the table does not need to
  change shape if a real pluggable Consensus Engine replaces the combiner
  later.
- Deliberately NOT modeled yet: `MarketSnapshot`, `EdgeCalculation`,
  `RiskCalculation`, `StrategyPerformance`, `StrategyCalibration`,
  `Backtest` — those belong to the Consensus/Edge/Risk/Polymarket layer,
  which is a separate, not-yet-approved mandate.
- `PaperPosition` (added for the CDC V2 "Paper trading" item, approved
  2026-09-16) is a deliberately narrow exception to that boundary: virtual
  positions only, no order routing, no broker, no real money -- exactly
  the mission's own "paper before live" rule
  (docs/CAHIER-DES-CHARGES.md §7). `user_id` is an opaque id the server
  hands this engine for a `source="user_confirmed"` position; this engine
  has no User table of its own and never authenticates anyone.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("symbol", "exchange", name="uq_asset_symbol_exchange"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    exchange: Mapped[str] = mapped_column(String(16))

    candles: Mapped[list["Candle"]] = relationship(back_populates="asset")


class Candle(Base):
    __tablename__ = "candles"
    __table_args__ = (
        UniqueConstraint("asset_id", "timeframe", "timestamp", name="uq_candle_asset_tf_ts"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    timeframe: Mapped[str] = mapped_column(String(8), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float)

    asset: Mapped[Asset] = relationship(back_populates="candles")
    ichimoku: Mapped["IchimokuIndicator | None"] = relationship(
        back_populates="candle", uselist=False
    )
    rvol: Mapped["RvolIndicator | None"] = relationship(back_populates="candle", uselist=False)
    signals: Mapped[list["StrategySignal"]] = relationship(back_populates="candle")


class IchimokuIndicator(Base):
    __tablename__ = "indicator_ichimoku"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    candle_id: Mapped[str] = mapped_column(ForeignKey("candles.id"), unique=True)

    tenkan: Mapped[float | None] = mapped_column(Float, nullable=True)
    kijun: Mapped[float | None] = mapped_column(Float, nullable=True)
    senkou_a: Mapped[float | None] = mapped_column(Float, nullable=True)
    senkou_b: Mapped[float | None] = mapped_column(Float, nullable=True)
    cloud_top: Mapped[float | None] = mapped_column(Float, nullable=True)
    cloud_bot: Mapped[float | None] = mapped_column(Float, nullable=True)
    kumo_thickness: Mapped[float | None] = mapped_column(Float, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)

    price_vs_kumo: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tk_cross: Mapped[str | None] = mapped_column(String(16), nullable=True)
    tk_strength: Mapped[str | None] = mapped_column(String(16), nullable=True)
    future_kumo: Mapped[str | None] = mapped_column(String(16), nullable=True)
    chikou_state: Mapped[str | None] = mapped_column(String(16), nullable=True)
    kumo_breakout: Mapped[str | None] = mapped_column(String(16), nullable=True)
    trend_strength: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_projected: Mapped[bool] = mapped_column(Boolean, default=False)

    candle: Mapped[Candle] = relationship(back_populates="ichimoku")


class RvolIndicator(Base):
    """Stub — the RVOL engine itself is not built yet; this table shape is
    reserved so IchimokuIndicator's sibling can land without another
    migration once app/indicators/rvol.py exists."""

    __tablename__ = "indicator_rvol"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    candle_id: Mapped[str] = mapped_column(ForeignKey("candles.id"), unique=True)

    rvol: Mapped[float | None] = mapped_column(Float, nullable=True)
    rvol5: Mapped[float | None] = mapped_column(Float, nullable=True)
    rvol10: Mapped[float | None] = mapped_column(Float, nullable=True)
    rvol20: Mapped[float | None] = mapped_column(Float, nullable=True)
    vol_accel: Mapped[float | None] = mapped_column(Float, nullable=True)
    percentile: Mapped[float | None] = mapped_column(Float, nullable=True)
    anomaly_level: Mapped[str | None] = mapped_column(String(16), nullable=True)

    candle: Mapped[Candle] = relationship(back_populates="rvol")


class StrategySignal(Base):
    """A screener-level candidate worth scoring — e.g. a confirmed TK-cross
    or Kumo breakout. Name/shape matches docs/TRADING_ARCHITECTURE_V2.md §4
    (`StrategySignal`) so a future Consensus Engine can read these directly.
    """

    __tablename__ = "strategy_signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    candle_id: Mapped[str] = mapped_column(ForeignKey("candles.id"), index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(8))
    kind: Mapped[str] = mapped_column(String(16))  # tk_long | tk_short | brk_long | brk_short
    rvol: Mapped[float | None] = mapped_column(Float, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    candle: Mapped[Candle] = relationship(back_populates="signals")
    predictions: Mapped[list["AgentPrediction"]] = relationship(back_populates="signal")
    decisions: Mapped[list["Decision"]] = relationship(back_populates="signal")


class AgentPrediction(Base):
    """One StrategyAgent's output for one StrategySignal. Field names match
    docs/TRADING_ARCHITECTURE_V2.md §3/§4 (`StrategyAgentOutput` /
    `AgentPrediction`) exactly."""

    __tablename__ = "agent_predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    signal_id: Mapped[str] = mapped_column(ForeignKey("strategy_signals.id"), index=True)
    agent: Mapped[str] = mapped_column(String(32))  # "ICHIMOKU_AGENT" | "RVOL_AGENT" | ...
    direction: Mapped[str] = mapped_column(String(8))  # LONG | SHORT | NEUTRAL
    probability: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    expected_value: Mapped[float] = mapped_column(Float)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    invalidation: Mapped[list] = mapped_column(JSON, default=list)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    signal: Mapped[StrategySignal] = relationship(back_populates="predictions")


class Decision(Base):
    """This mission's Decision Engine output (brief §8): explainable,
    traceable, one row per (signal, strategy_version). Shape is a superset
    compatible with the proposed `ConsensusDecision` (direction/probability/
    confidence/agreement/weights_used) so a real multi-agent Consensus
    Engine can take over this table's producer role later without a
    migration — today `agreement`/`weights_used` describe a fixed,
    hardcoded combiner over exactly ICHIMOKU_AGENT + RVOL_AGENT, not a
    general pluggable consensus."""

    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    signal_id: Mapped[str] = mapped_column(ForeignKey("strategy_signals.id"), index=True)
    strategy_version: Mapped[str] = mapped_column(String(32), default="ichimoku_rvol_v1")

    decision: Mapped[str] = mapped_column(String(16))  # STRONG_BUY|BUY|WATCH|WAIT|SELL|STRONG_SELL
    direction: Mapped[str] = mapped_column(String(8))  # LONG | SHORT | NEUTRAL
    probability: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    agreement: Mapped[float] = mapped_column(Float)
    weights_used: Mapped[dict] = mapped_column(JSON, default=dict)

    reasons: Mapped[list] = mapped_column(JSON, default=list)
    risks: Mapped[list] = mapped_column(JSON, default=list)
    invalidation: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    signal: Mapped[StrategySignal] = relationship(back_populates="decisions")


class PaperPosition(Base):
    """A simulated (never real) position, opened and closed purely by
    reading `pipeline.decision` over time -- app/paper/engine.py owns the
    open/close rules. Two origins, tracked side by side via `source`:

    - "auto_watchlist": the background screener cycle opens/closes these
      for every symbol in the default watchlist automatically (crypto +
      biquote-backed forex/métal/index/énergie; Twelve Data equities are
      excluded from the default watchlist to protect its free-tier budget,
      see app/universe/catalog.py::default_watchlist), no user involved --
      "what if I'd just followed the engine everywhere". `user_id` is null.
    - "user_confirmed": opened on request (server calls this engine when a
      user hits "Confirmer" in the Journal) for that one symbol -- "how did
      MY picks do". `user_id` is whatever id the server's own User table
      uses; this engine only stores and filters by it, never validates it.
    """

    __tablename__ = "paper_positions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(8))
    source: Mapped[str] = mapped_column(String(16), index=True)  # auto_watchlist | user_confirmed
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    direction: Mapped[str] = mapped_column(String(8))  # LONG | SHORT
    status: Mapped[str] = mapped_column(String(8), default="OPEN", index=True)  # OPEN | CLOSED

    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    entry_price: Mapped[float] = mapped_column(Float)
    entry_decision: Mapped[str] = mapped_column(String(16))  # pipeline.decision snapshot at entry

    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
