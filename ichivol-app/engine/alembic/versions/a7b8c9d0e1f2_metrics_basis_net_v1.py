"""Add metrics_basis to strategy_lab_experiments and backtest_snapshots (T0-METRICS).

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-09-23 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "strategy_lab_experiments",
        sa.Column("metrics_basis", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "backtest_snapshots",
        sa.Column("metrics_basis", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("backtest_snapshots", "metrics_basis")
    op.drop_column("strategy_lab_experiments", "metrics_basis")
