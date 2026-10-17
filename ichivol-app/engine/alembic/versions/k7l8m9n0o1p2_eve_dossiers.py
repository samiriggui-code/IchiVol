"""Ève Intelligence V1 — table eve_dossiers (Dossier IchiVol). Additive only.

Revision ID: k7l8m9n0o1p2
Revises: j6k7l8m9n0o1
Create Date: 2026-10-16 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k7l8m9n0o1p2"
down_revision: Union[str, Sequence[str], None] = "j6k7l8m9n0o1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "eve_dossiers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("portfolio_code", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timeframe", sa.String(length=8), nullable=False),
        sa.Column("bar_time", sa.BigInteger(), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("holding", sa.String(length=8), nullable=True),
        sa.Column("battery", sa.String(length=16), nullable=False),
        sa.Column("battery_version", sa.String(length=32), nullable=False),
        sa.Column("call_key", sa.String(length=128), nullable=False),
        sa.Column("reused", sa.Boolean(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=True),
        sa.Column("state_chars", sa.Integer(), nullable=True),
        sa.Column("questions", sa.JSON(), nullable=True),
        sa.Column("answers", sa.JSON(), nullable=True),
        sa.Column("jev_ok", sa.Boolean(), nullable=False),
        sa.Column("jev_error", sa.String(length=64), nullable=True),
        sa.Column("jev_errors", sa.JSON(), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("usage", sa.JSON(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("engine_decision", sa.String(length=16), nullable=True),
        sa.Column("eve_action", sa.String(length=16), nullable=False),
        sa.Column("eve_label", sa.String(length=16), nullable=False),
        sa.Column("decisive", sa.Boolean(), nullable=False),
        sa.Column("coherence", sa.Float(), nullable=True),
        sa.Column("p_up", sa.Float(), nullable=True),
        sa.Column("reasons", sa.JSON(), nullable=True),
        sa.Column("engine_action", sa.String(length=16), nullable=False),
        sa.Column("executed_action", sa.String(length=16), nullable=False),
        sa.Column("decided_by", sa.String(length=16), nullable=False),
        sa.Column("executed_result", sa.String(length=32), nullable=True),
        sa.Column("position_id", sa.String(length=36), nullable=True),
        sa.Column("outcome_bars", sa.Integer(), nullable=True),
        sa.Column("outcome_close", sa.Float(), nullable=True),
        sa.Column("outcome_return", sa.Float(), nullable=True),
        sa.Column("outcome_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("portfolio_code", "symbol", "timeframe", "bar_time", name="uq_eve_dossier_bar"),
    )
    for col in ("created_at", "portfolio_code", "symbol", "bar_time", "call_key", "position_id"):
        op.create_index(f"ix_eve_dossiers_{col}", "eve_dossiers", [col])


def downgrade() -> None:
    op.drop_table("eve_dossiers")
