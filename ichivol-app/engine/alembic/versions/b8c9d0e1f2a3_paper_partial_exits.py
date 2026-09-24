"""paper_partial_exits — T0-MANAGE-d partial take-profit journal

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-09-23 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "paper_partial_exits",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("portfolio_id", sa.String(length=36), nullable=False),
        sa.Column("position_id", sa.String(length=36), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("r_multiple", sa.Float(), nullable=False),
        sa.Column("fraction", sa.Float(), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("fee", sa.Float(), nullable=False),
        sa.Column("realized_pnl", sa.Float(), nullable=False),
        sa.Column("time_ms", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["paper_portfolios.id"]),
        sa.ForeignKeyConstraint(["position_id"], ["paper_positions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("position_id", "seq", name="uq_paper_partial_position_seq"),
        sa.UniqueConstraint("portfolio_id", "key", name="uq_paper_partial_portfolio_key"),
    )
    op.create_index("ix_paper_partial_exits_portfolio_id", "paper_partial_exits", ["portfolio_id"])
    op.create_index("ix_paper_partial_exits_position_id", "paper_partial_exits", ["position_id"])


def downgrade() -> None:
    op.drop_index("ix_paper_partial_exits_position_id", table_name="paper_partial_exits")
    op.drop_index("ix_paper_partial_exits_portfolio_id", table_name="paper_partial_exits")
    op.drop_table("paper_partial_exits")
