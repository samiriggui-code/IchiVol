"""Add paper_positions.initial_qty — stable entry size (T0-MANAGE-d fix)

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-09-23 23:05:00.000000

``qty`` = remaining open size while OPEN; ``initial_qty`` never shrinks.
On CLOSE, ``qty`` is restored to ``initial_qty`` so fee/ledger consumers that
read ``pos.qty`` after close keep a fixed reference (T0-METRICS class of bug).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "paper_positions",
        sa.Column("initial_qty", sa.Float(), nullable=True),
    )
    # Backfill: existing rows — treat current qty as the entry size.
    op.execute("UPDATE paper_positions SET initial_qty = qty WHERE initial_qty IS NULL AND qty IS NOT NULL")


def downgrade() -> None:
    op.drop_column("paper_positions", "initial_qty")
