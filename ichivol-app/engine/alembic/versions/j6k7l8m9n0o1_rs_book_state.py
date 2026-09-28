"""RS-09 — table rs_book_state (RS-D1 paper live). Additive only.

Revision ID: j6k7l8m9n0o1
Revises: i5j6k7l8m9n0
Create Date: 2026-09-28 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j6k7l8m9n0o1"
down_revision: Union[str, Sequence[str], None] = "i5j6k7l8m9n0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rs_book_state",
        sa.Column("portfolio_code", sa.String(length=64), primary_key=True),
        sa.Column("history_start", sa.BigInteger(), nullable=False),
        sa.Column("last_bar_time", sa.BigInteger(), nullable=True),
        sa.Column("state_json", sa.JSON(), nullable=False),
        sa.Column("refs", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("rs_book_state")
