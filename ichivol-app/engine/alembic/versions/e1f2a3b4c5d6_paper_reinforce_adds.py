"""Add paper_reinforce_adds — T0-MANAGE-f scale-in journal

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-09-24 06:15:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, Sequence[str], None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "paper_reinforce_adds",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("portfolio_id", sa.String(length=36), sa.ForeignKey("paper_portfolios.id"), nullable=False),
        sa.Column("position_id", sa.String(length=36), sa.ForeignKey("paper_positions.id"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("r_multiple", sa.Float(), nullable=False),
        sa.Column("fraction", sa.Float(), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("fee", sa.Float(), nullable=False, server_default="0"),
        sa.Column("stop_after", sa.Float(), nullable=True),
        sa.Column("avg_entry_after", sa.Float(), nullable=True),
        sa.Column("open_risk_after", sa.Float(), nullable=True),
        sa.Column("clamped", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("time_ms", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_paper_reinforce_adds_portfolio_id", "paper_reinforce_adds", ["portfolio_id"])
    op.create_index("ix_paper_reinforce_adds_position_id", "paper_reinforce_adds", ["position_id"])
    op.create_unique_constraint(
        "uq_paper_reinforce_position_seq", "paper_reinforce_adds", ["position_id", "seq"]
    )
    op.create_unique_constraint(
        "uq_paper_reinforce_portfolio_key", "paper_reinforce_adds", ["portfolio_id", "key"]
    )


def downgrade() -> None:
    op.drop_table("paper_reinforce_adds")
