"""Add hypothesis_id to strategy_lab_experiments (T10b).

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-09-24 08:35:00.000000

Nullable lineage tag for the trial counter (compteur d'essais). Multiple
rows may share the same hypothesis_id — not UNIQUE. Complexity stays
computed (display-only); no auto-reject.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "strategy_lab_experiments",
        sa.Column("hypothesis_id", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_strategy_lab_experiments_hypothesis_id",
        "strategy_lab_experiments",
        ["hypothesis_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_strategy_lab_experiments_hypothesis_id",
        table_name="strategy_lab_experiments",
    )
    op.drop_column("strategy_lab_experiments", "hypothesis_id")
