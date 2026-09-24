"""T11a-bis — candles.volume_type + candles.taker_buy_volume (nullable).

Revision ID: h4i5j6k7l8m9
Revises: g3h4i5j6k7l8
Create Date: 2026-09-24 14:40:00.000000

Old rows stay NULL. In-memory Candle already carries these fields (Binance
taker buy / VolumeType); DB round-trip was dropping them.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h4i5j6k7l8m9"
down_revision: Union[str, Sequence[str], None] = "g3h4i5j6k7l8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "candles",
        sa.Column("volume_type", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "candles",
        sa.Column("taker_buy_volume", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("candles", "taker_buy_volume")
    op.drop_column("candles", "volume_type")
