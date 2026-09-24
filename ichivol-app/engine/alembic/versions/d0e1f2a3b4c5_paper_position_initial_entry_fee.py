"""Add paper_positions.initial_entry_fee — stable entry commission (T0-MANAGE-d)

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-09-24 05:30:00.000000

``entry_fee`` shrinks with partial scale-outs while OPEN; ``initial_entry_fee``
never shrinks. On CLOSE, ``entry_fee`` is restored to ``initial_entry_fee``
(same contract as ``qty`` / ``initial_qty``).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "paper_positions",
        sa.Column("initial_entry_fee", sa.Float(), nullable=True),
    )
    op.execute(
        "UPDATE paper_positions SET initial_entry_fee = entry_fee "
        "WHERE initial_entry_fee IS NULL AND entry_fee IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("paper_positions", "initial_entry_fee")
