"""AG-S1 — table analyst_snapshot (session cards, observe-only).

Revision ID: i5j6k7l8m9n0
Revises: h4i5j6k7l8m9
Create Date: 2026-09-28 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i5j6k7l8m9n0"
down_revision: Union[str, Sequence[str], None] = "h4i5j6k7l8m9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analyst_snapshot",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("as_of", sa.Integer(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timeframe", sa.String(length=8), nullable=False),
        sa.Column("cards", sa.JSON(), nullable=False),
        sa.Column("engine_version", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "session_id",
            "symbol",
            "timeframe",
            name="uq_analyst_snapshot_session_symbol_tf",
        ),
    )
    op.create_index("ix_analyst_snapshot_session_id", "analyst_snapshot", ["session_id"])
    op.create_index("ix_analyst_snapshot_symbol", "analyst_snapshot", ["symbol"])
    op.create_index("ix_analyst_snapshot_timeframe", "analyst_snapshot", ["timeframe"])
    op.create_index(
        "ix_analyst_snapshot_engine_version", "analyst_snapshot", ["engine_version"]
    )
    op.create_index("ix_analyst_snapshot_created_at", "analyst_snapshot", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_analyst_snapshot_created_at", table_name="analyst_snapshot")
    op.drop_index("ix_analyst_snapshot_engine_version", table_name="analyst_snapshot")
    op.drop_index("ix_analyst_snapshot_timeframe", table_name="analyst_snapshot")
    op.drop_index("ix_analyst_snapshot_symbol", table_name="analyst_snapshot")
    op.drop_index("ix_analyst_snapshot_session_id", table_name="analyst_snapshot")
    op.drop_table("analyst_snapshot")
