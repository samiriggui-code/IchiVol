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
  `RiskCalculation`, `StrategyCalibration`, full Consensus layer — those
  belong to a separate mandate. `StrategyLabExperiment` (Phase 4 Performance
  DB) is the research-store exception: persisted ruleset studies, not a live
  gate voter.
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

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
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


class PaperPortfolio(Base):
    """Virtual broker account (never real money). Phase 1 seeds
    ICHIVOL_BASELINE_V1 at 5000 EUR; later A–F portfolios share this table."""

    __tablename__ = "paper_portfolios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(128))
    currency: Mapped[str] = mapped_column(String(8), default="EUR")
    valuation_mode: Mapped[str] = mapped_column(String(32), default="USDT_AS_EUR_PROXY")
    initial_cash: Mapped[float] = mapped_column(Float, default=5000.0)
    cash: Mapped[float] = mapped_column(Float, default=5000.0)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    strategy_profile: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class PaperPosition(Base):
    """A simulated (never real) position. Phase 1 PaperBroker fields
    (qty, stop, fees, MFE/MAE, …) are nullable so legacy rows remain valid."""

    __tablename__ = "paper_positions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    portfolio_id: Mapped[str | None] = mapped_column(
        ForeignKey("paper_portfolios.id"), nullable=True, index=True
    )
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(8))
    source: Mapped[str] = mapped_column(String(16), index=True)  # auto_watchlist | user_confirmed
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    direction: Mapped[str] = mapped_column(String(8))  # LONG | SHORT
    status: Mapped[str] = mapped_column(String(8), default="OPEN", index=True)  # OPEN | CLOSED

    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    entry_price: Mapped[float] = mapped_column(Float)
    entry_decision: Mapped[str] = mapped_column(String(16))
    entry_signal: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    exit_signal: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    qty: Mapped[float | None] = mapped_column(Float, nullable=True)
    notional: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_fee: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_fee: Mapped[float | None] = mapped_column(Float, nullable=True)
    realized_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    mfe_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    mae_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    highest_price_seen: Mapped[float | None] = mapped_column(Float, nullable=True)
    lowest_price_seen: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class PaperOrder(Base):
    """Virtual fill log for the paper broker (never sent to a real venue)."""

    __tablename__ = "paper_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    portfolio_id: Mapped[str] = mapped_column(ForeignKey("paper_portfolios.id"), index=True)
    position_id: Mapped[str | None] = mapped_column(
        ForeignKey("paper_positions.id"), nullable=True, index=True
    )
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(8))
    side: Mapped[str] = mapped_column(String(8))  # BUY | SELL
    order_type: Mapped[str] = mapped_column(String(16), default="MARKET")
    requested_price: Mapped[float] = mapped_column(Float)
    filled_price: Mapped[float] = mapped_column(Float)
    qty: Mapped[float] = mapped_column(Float)
    notional: Mapped[float] = mapped_column(Float)
    fee: Mapped[float] = mapped_column(Float, default=0.0)
    spread_bps: Mapped[float] = mapped_column(Float, default=0.0)
    slippage_bps: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(16), default="FILLED")
    reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


class PaperEquitySnapshot(Base):
    """Periodic mark of portfolio equity — needed for honest max drawdown."""

    __tablename__ = "paper_equity_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    portfolio_id: Mapped[str] = mapped_column(ForeignKey("paper_portfolios.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    cash: Mapped[float] = mapped_column(Float)
    positions_value: Mapped[float] = mapped_column(Float, default=0.0)
    equity: Mapped[float] = mapped_column(Float)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    drawdown_pct: Mapped[float | None] = mapped_column(Float, nullable=True)


class PaperJournalEvent(Base):
    """Append-only explainability trail for paper broker events."""

    __tablename__ = "paper_journal_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    portfolio_id: Mapped[str] = mapped_column(ForeignKey("paper_portfolios.id"), index=True)
    position_id: Mapped[str | None] = mapped_column(
        ForeignKey("paper_positions.id"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


class BacktestSnapshot(Base):
    """One experiment's metrics from one automated evidence-collection run
    (CDC "condition 1" for the live broker gate, docs/CAHIER-DES-CHARGES.md
    §5 V3: "un vrai edge de rendement prouvé"). Written only by
    `app/backtest/evidence.py`'s scheduled job -- it logs `experiments.compare()`
    results over time so a trend becomes visible without anyone re-running
    scripts by hand. This table is purely observational: nothing reads it to
    make a decision, nothing here ever flips a pipeline gate on its own --
    promoting a gate stays a reviewed call, same as ADX/Donchian/Wyckoff.
    """

    __tablename__ = "backtest_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(8), index=True)
    experiment: Mapped[str] = mapped_column(String(32), index=True)  # ICHIMOKU_ONLY | PIPELINE | ...
    strategy_version: Mapped[str] = mapped_column(String(64))

    n_bars: Mapped[int] = mapped_column(Integer)
    num_trades: Mapped[int] = mapped_column(Integer)
    total_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    cagr: Mapped[float | None] = mapped_column(Float, nullable=True)
    sharpe: Mapped[float | None] = mapped_column(Float, nullable=True)
    sortino: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[float | None] = mapped_column(Float, nullable=True)
    exposure: Mapped[float | None] = mapped_column(Float, nullable=True)
    win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    expectancy: Mapped[float | None] = mapped_column(Float, nullable=True)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


class StrategyLabExperiment(Base):
    """Persisted Strategy Lab run (Phase 4 Performance DB).

    Stores a ruleset hypothesis + event-study + ATR backtest metrics so
    experiments are not recomputed forever. Observational research store —
    nothing here auto-promotes a live pipeline gate.
    """

    __tablename__ = "strategy_lab_experiments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    ruleset_id: Mapped[str] = mapped_column(String(128), index=True)
    ruleset_version: Mapped[str] = mapped_column(String(32))
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(8), index=True)
    market_regime: Mapped[str] = mapped_column(String(32), default="GLOBAL", index=True)

    date_range_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date_range_end: Mapped[int | None] = mapped_column(Integer, nullable=True)

    rules_json: Mapped[dict] = mapped_column(JSON)
    entry_rule: Mapped[str] = mapped_column(String(64))
    exit_rule: Mapped[str] = mapped_column(String(64))
    stop_rule: Mapped[str] = mapped_column(String(64))
    target_rule: Mapped[str] = mapped_column(String(64))

    n_bars: Mapped[int] = mapped_column(Integer)
    n_signals: Mapped[int] = mapped_column(Integer)
    n_matching_bars: Mapped[int] = mapped_column(Integer)
    number_of_trades: Mapped[int] = mapped_column(Integer, default=0)

    win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    profit_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    expectancy: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[float | None] = mapped_column(Float, nullable=True)
    sharpe: Mapped[float | None] = mapped_column(Float, nullable=True)
    sortino: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    cagr: Mapped[float | None] = mapped_column(Float, nullable=True)
    exposure: Mapped[float | None] = mapped_column(Float, nullable=True)

    mean_mfe_atr: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean_mae_atr: Mapped[float | None] = mapped_column(Float, nullable=True)
    median_mfe_atr: Mapped[float | None] = mapped_column(Float, nullable=True)
    median_mae_atr: Mapped[float | None] = mapped_column(Float, nullable=True)
    pct_hit_plus_r_before_minus_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    n_resolved_r: Mapped[int] = mapped_column(Integer, default=0)

    exit_reasons_json: Mapped[dict] = mapped_column(JSON, default=dict)
    event_study_json: Mapped[dict] = mapped_column(JSON, default=dict)
    parameters_json: Mapped[dict] = mapped_column(JSON, default=dict)

    dataset_version: Mapped[str] = mapped_column(String(128))
    engine_version: Mapped[str] = mapped_column(String(64), index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
