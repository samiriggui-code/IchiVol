"""Eve Intelligence V1 — dossiers + verdicts (additive, reversible).

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
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timeframe", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("context_json", sa.JSON(), nullable=False),
        sa.Column("modes_json", sa.JSON(), nullable=False),
        sa.Column("jev_json", sa.JSON(), nullable=False),
        sa.Column("coherence_json", sa.JSON(), nullable=False),
        sa.Column("policy_json", sa.JSON(), nullable=False),
        sa.Column("decision_time_json", sa.JSON(), nullable=False),
        sa.Column("outcome_json", sa.JSON(), nullable=True),
        sa.Column("baseline_decision", sa.String(length=32), nullable=True),
        sa.Column("eve_action", sa.String(length=16), nullable=True),
        sa.Column(
            "execution_status",
            sa.String(length=32),
            nullable=False,
            server_default="not_executed",
        ),
        sa.Column("verdict_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_eve_dossiers_symbol", "eve_dossiers", ["symbol"])
    op.create_index("ix_eve_dossiers_timeframe", "eve_dossiers", ["timeframe"])
    op.create_index("ix_eve_dossiers_status", "eve_dossiers", ["status"])
    op.create_index("ix_eve_dossiers_eve_action", "eve_dossiers", ["eve_action"])
    op.create_index("ix_eve_dossiers_verdict_id", "eve_dossiers", ["verdict_id"])
    op.create_index("ix_eve_dossiers_created_at", "eve_dossiers", ["created_at"])

    op.create_table(
        "eve_verdicts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("dossier_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="potential"),
        sa.Column("scenario_retained", sa.String(length=64), nullable=True),
        sa.Column("scenarios_rejected", sa.JSON(), nullable=False),
        sa.Column("reasoning", sa.String(length=2000), nullable=True),
        sa.Column("coherence_score", sa.Float(), nullable=True),
        sa.Column("body_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dossier_id"], ["eve_dossiers.id"]),
    )
    op.create_index("ix_eve_verdicts_dossier_id", "eve_verdicts", ["dossier_id"])
    op.create_index("ix_eve_verdicts_action", "eve_verdicts", ["action"])
    op.create_index("ix_eve_verdicts_status", "eve_verdicts", ["status"])
    op.create_index("ix_eve_verdicts_created_at", "eve_verdicts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_eve_verdicts_created_at", table_name="eve_verdicts")
    op.drop_index("ix_eve_verdicts_status", table_name="eve_verdicts")
    op.drop_index("ix_eve_verdicts_action", table_name="eve_verdicts")
    op.drop_index("ix_eve_verdicts_dossier_id", table_name="eve_verdicts")
    op.drop_table("eve_verdicts")
    op.drop_index("ix_eve_dossiers_created_at", table_name="eve_dossiers")
    op.drop_index("ix_eve_dossiers_verdict_id", table_name="eve_dossiers")
    op.drop_index("ix_eve_dossiers_eve_action", table_name="eve_dossiers")
    op.drop_index("ix_eve_dossiers_status", table_name="eve_dossiers")
    op.drop_index("ix_eve_dossiers_timeframe", table_name="eve_dossiers")
    op.drop_index("ix_eve_dossiers_symbol", table_name="eve_dossiers")
    op.drop_table("eve_dossiers")
