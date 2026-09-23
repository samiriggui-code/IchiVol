"""chart_object_overlays for USER/CLAUDE persistence (T2b)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-23 10:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chart_object_overlays",
        sa.Column("id", sa.String(length=24), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timeframe", sa.String(length=8), nullable=False),
        sa.Column("points", sa.JSON(), nullable=False),
        sa.Column("price_low", sa.Float(), nullable=True),
        sa.Column("price_high", sa.Float(), nullable=True),
        sa.Column("side", sa.String(length=16), nullable=True),
        sa.Column("label", sa.String(length=256), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("as_of", sa.Integer(), nullable=False),
        sa.Column("origin", sa.JSON(), nullable=False),
        sa.Column("subtype", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chart_object_overlays_symbol", "chart_object_overlays", ["symbol"])
    op.create_index("ix_chart_object_overlays_timeframe", "chart_object_overlays", ["timeframe"])
    op.create_index("ix_chart_object_overlays_source", "chart_object_overlays", ["source"])
    op.create_index(
        "ix_chart_object_overlays_symbol_tf",
        "chart_object_overlays",
        ["symbol", "timeframe"],
    )


def downgrade() -> None:
    op.drop_index("ix_chart_object_overlays_symbol_tf", table_name="chart_object_overlays")
    op.drop_index("ix_chart_object_overlays_source", table_name="chart_object_overlays")
    op.drop_index("ix_chart_object_overlays_timeframe", table_name="chart_object_overlays")
    op.drop_index("ix_chart_object_overlays_symbol", table_name="chart_object_overlays")
    op.drop_table("chart_object_overlays")
