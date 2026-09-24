"""Add kill switch + daily loss lock columns on paper_portfolios (T13c).

Revision ID: g3h4i5j6k7l8
Revises: f2a3b4c5d6e7
Create Date: 2026-09-24 14:15:00.000000

Persisted entry locks. Defaults False — no tighter risk until armed / latched.
Never auto-cleared by code (human disarm/unlock only).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g3h4i5j6k7l8"
down_revision: Union[str, Sequence[str], None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "paper_portfolios",
        sa.Column("kill_switch_armed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "paper_portfolios",
        sa.Column("kill_switch_armed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "paper_portfolios",
        sa.Column("daily_loss_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "paper_portfolios",
        sa.Column("daily_loss_locked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("paper_portfolios", "daily_loss_locked_at")
    op.drop_column("paper_portfolios", "daily_loss_locked")
    op.drop_column("paper_portfolios", "kill_switch_armed_at")
    op.drop_column("paper_portfolios", "kill_switch_armed")
