"""paper broker portfolios orders equity journal

Revision ID: a1b2c3d4e5f6
Revises: 3cae25ba04d6
Create Date: 2026-09-18 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "3cae25ba04d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "paper_portfolios",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("valuation_mode", sa.String(length=32), nullable=False),
        sa.Column("initial_cash", sa.Float(), nullable=False),
        sa.Column("cash", sa.Float(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=False),
        sa.Column("strategy_profile", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_paper_portfolios_code"), "paper_portfolios", ["code"], unique=True)

    op.add_column("paper_positions", sa.Column("portfolio_id", sa.String(length=36), nullable=True))
    op.add_column("paper_positions", sa.Column("entry_signal", sa.JSON(), nullable=True))
    op.add_column("paper_positions", sa.Column("exit_signal", sa.JSON(), nullable=True))
    op.add_column("paper_positions", sa.Column("qty", sa.Float(), nullable=True))
    op.add_column("paper_positions", sa.Column("notional", sa.Float(), nullable=True))
    op.add_column("paper_positions", sa.Column("stop_price", sa.Float(), nullable=True))
    op.add_column("paper_positions", sa.Column("take_profit_price", sa.Float(), nullable=True))
    op.add_column("paper_positions", sa.Column("risk_pct", sa.Float(), nullable=True))
    op.add_column("paper_positions", sa.Column("risk_amount", sa.Float(), nullable=True))
    op.add_column("paper_positions", sa.Column("entry_fee", sa.Float(), nullable=True))
    op.add_column("paper_positions", sa.Column("exit_fee", sa.Float(), nullable=True))
    op.add_column("paper_positions", sa.Column("realized_pnl", sa.Float(), nullable=True))
    op.add_column("paper_positions", sa.Column("mfe_pct", sa.Float(), nullable=True))
    op.add_column("paper_positions", sa.Column("mae_pct", sa.Float(), nullable=True))
    op.add_column("paper_positions", sa.Column("highest_price_seen", sa.Float(), nullable=True))
    op.add_column("paper_positions", sa.Column("lowest_price_seen", sa.Float(), nullable=True))
    op.create_foreign_key(
        "fk_paper_positions_portfolio_id",
        "paper_positions",
        "paper_portfolios",
        ["portfolio_id"],
        ["id"],
    )
    op.create_index(op.f("ix_paper_positions_portfolio_id"), "paper_positions", ["portfolio_id"])

    op.create_table(
        "paper_orders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("portfolio_id", sa.String(length=36), nullable=False),
        sa.Column("position_id", sa.String(length=36), nullable=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timeframe", sa.String(length=8), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("order_type", sa.String(length=16), nullable=False),
        sa.Column("requested_price", sa.Float(), nullable=False),
        sa.Column("filled_price", sa.Float(), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("notional", sa.Float(), nullable=False),
        sa.Column("fee", sa.Float(), nullable=False),
        sa.Column("spread_bps", sa.Float(), nullable=False),
        sa.Column("slippage_bps", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["paper_portfolios.id"]),
        sa.ForeignKeyConstraint(["position_id"], ["paper_positions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_paper_orders_portfolio_id"), "paper_orders", ["portfolio_id"])
    op.create_index(op.f("ix_paper_orders_position_id"), "paper_orders", ["position_id"])
    op.create_index(op.f("ix_paper_orders_symbol"), "paper_orders", ["symbol"])
    op.create_index(op.f("ix_paper_orders_created_at"), "paper_orders", ["created_at"])

    op.create_table(
        "paper_equity_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("portfolio_id", sa.String(length=36), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cash", sa.Float(), nullable=False),
        sa.Column("positions_value", sa.Float(), nullable=False),
        sa.Column("equity", sa.Float(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=False),
        sa.Column("unrealized_pnl", sa.Float(), nullable=False),
        sa.Column("drawdown_pct", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["portfolio_id"], ["paper_portfolios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_paper_equity_snapshots_portfolio_id"), "paper_equity_snapshots", ["portfolio_id"]
    )
    op.create_index(
        op.f("ix_paper_equity_snapshots_timestamp"), "paper_equity_snapshots", ["timestamp"]
    )

    op.create_table(
        "paper_journal_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("portfolio_id", sa.String(length=36), nullable=False),
        sa.Column("position_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["paper_portfolios.id"]),
        sa.ForeignKeyConstraint(["position_id"], ["paper_positions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_paper_journal_events_portfolio_id"), "paper_journal_events", ["portfolio_id"]
    )
    op.create_index(
        op.f("ix_paper_journal_events_position_id"), "paper_journal_events", ["position_id"]
    )
    op.create_index(
        op.f("ix_paper_journal_events_event_type"), "paper_journal_events", ["event_type"]
    )
    op.create_index(
        op.f("ix_paper_journal_events_created_at"), "paper_journal_events", ["created_at"]
    )


def downgrade() -> None:
    op.drop_table("paper_journal_events")
    op.drop_table("paper_equity_snapshots")
    op.drop_table("paper_orders")
    op.drop_index(op.f("ix_paper_positions_portfolio_id"), table_name="paper_positions")
    op.drop_constraint("fk_paper_positions_portfolio_id", "paper_positions", type_="foreignkey")
    for col in (
        "lowest_price_seen",
        "highest_price_seen",
        "mae_pct",
        "mfe_pct",
        "realized_pnl",
        "exit_fee",
        "entry_fee",
        "risk_amount",
        "risk_pct",
        "take_profit_price",
        "stop_price",
        "notional",
        "qty",
        "exit_signal",
        "entry_signal",
        "portfolio_id",
    ):
        op.drop_column("paper_positions", col)
    op.drop_index(op.f("ix_paper_portfolios_code"), table_name="paper_portfolios")
    op.drop_table("paper_portfolios")
