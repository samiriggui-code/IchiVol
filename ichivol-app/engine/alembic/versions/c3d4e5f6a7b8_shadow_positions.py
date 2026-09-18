"""add shadow_positions for ShadowBroker Phase 5

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-19 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shadow_positions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("portfolio_id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timeframe", sa.String(length=8), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("stop_price", sa.Float(), nullable=False),
        sa.Column("take_profit_price", sa.Float(), nullable=False),
        sa.Column("stop_distance", sa.Float(), nullable=False),
        sa.Column("risk_pct", sa.Float(), nullable=False),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("exit_reason", sa.String(length=32), nullable=True),
        sa.Column("pnl_r", sa.Float(), nullable=True),
        sa.Column("pnl_pct", sa.Float(), nullable=True),
        sa.Column("block_source", sa.String(length=32), nullable=False),
        sa.Column("block_reason", sa.String(length=256), nullable=True),
        sa.Column("raw_decision", sa.String(length=16), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["paper_portfolios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shadow_positions_portfolio_id", "shadow_positions", ["portfolio_id"])
    op.create_index("ix_shadow_positions_symbol", "shadow_positions", ["symbol"])
    op.create_index("ix_shadow_positions_status", "shadow_positions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_shadow_positions_status", table_name="shadow_positions")
    op.drop_index("ix_shadow_positions_symbol", table_name="shadow_positions")
    op.drop_index("ix_shadow_positions_portfolio_id", table_name="shadow_positions")
    op.drop_table("shadow_positions")
