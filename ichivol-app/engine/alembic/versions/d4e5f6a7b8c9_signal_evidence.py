"""signal evidence table + paper position evidence linkage

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-19 13:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "signal_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timeframe", sa.String(length=8), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("volume_type", sa.String(length=32), nullable=False),
        sa.Column("asset_class", sa.String(length=16), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column("decision_id", sa.String(length=36), nullable=True),
        sa.Column("paper_position_id", sa.String(length=36), nullable=True),
        sa.Column("context_json", sa.JSON(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("market_snapshot", sa.JSON(), nullable=False),
        sa.Column("outcome_json", sa.JSON(), nullable=True),
        sa.Column("strategy_version", sa.String(length=64), nullable=False),
        sa.Column("feature_version", sa.String(length=64), nullable=False),
        sa.Column("rules_version", sa.String(length=64), nullable=False),
        sa.Column("evidence_engine_version", sa.String(length=64), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False),
        sa.Column("sample_quality", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signal_evidence_symbol", "signal_evidence", ["symbol"])
    op.create_index("ix_signal_evidence_timeframe", "signal_evidence", ["timeframe"])
    op.create_index("ix_signal_evidence_timestamp", "signal_evidence", ["timestamp"])
    op.create_index("ix_signal_evidence_asset_class", "signal_evidence", ["asset_class"])
    op.create_index("ix_signal_evidence_decision", "signal_evidence", ["decision"])
    op.create_index("ix_signal_evidence_decision_id", "signal_evidence", ["decision_id"])
    op.create_index(
        "ix_signal_evidence_paper_position_id", "signal_evidence", ["paper_position_id"]
    )
    op.create_index(
        "ix_signal_evidence_strategy_version", "signal_evidence", ["strategy_version"]
    )
    op.create_index("ix_signal_evidence_created_at", "signal_evidence", ["created_at"])

    op.add_column("paper_positions", sa.Column("decision_id", sa.String(length=36), nullable=True))
    op.add_column("paper_positions", sa.Column("evidence_id", sa.String(length=36), nullable=True))
    op.create_index("ix_paper_positions_decision_id", "paper_positions", ["decision_id"])
    op.create_index("ix_paper_positions_evidence_id", "paper_positions", ["evidence_id"])


def downgrade() -> None:
    op.drop_index("ix_paper_positions_evidence_id", table_name="paper_positions")
    op.drop_index("ix_paper_positions_decision_id", table_name="paper_positions")
    op.drop_column("paper_positions", "evidence_id")
    op.drop_column("paper_positions", "decision_id")

    op.drop_index("ix_signal_evidence_created_at", table_name="signal_evidence")
    op.drop_index("ix_signal_evidence_strategy_version", table_name="signal_evidence")
    op.drop_index("ix_signal_evidence_paper_position_id", table_name="signal_evidence")
    op.drop_index("ix_signal_evidence_decision_id", table_name="signal_evidence")
    op.drop_index("ix_signal_evidence_decision", table_name="signal_evidence")
    op.drop_index("ix_signal_evidence_asset_class", table_name="signal_evidence")
    op.drop_index("ix_signal_evidence_timestamp", table_name="signal_evidence")
    op.drop_index("ix_signal_evidence_timeframe", table_name="signal_evidence")
    op.drop_index("ix_signal_evidence_symbol", table_name="signal_evidence")
    op.drop_table("signal_evidence")
