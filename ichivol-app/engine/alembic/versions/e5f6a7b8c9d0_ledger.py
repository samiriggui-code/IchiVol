"""append-only accounting ledger for the virtual broker

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-20 18:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ledger_transactions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("portfolio_id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("ref", sa.String(length=64), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["paper_portfolios.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("portfolio_id", "key", name="uq_ledger_portfolio_key"),
    )
    op.create_index("ix_ledger_transactions_portfolio_id", "ledger_transactions", ["portfolio_id"])
    op.create_index("ix_ledger_transactions_ref", "ledger_transactions", ["ref"])
    op.create_index("ix_ledger_transactions_ts", "ledger_transactions", ["ts"])
    op.create_table(
        "ledger_legs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("transaction_id", sa.String(length=36), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("amount", sa.Numeric(28, 8), nullable=False),
        sa.Column("cause", sa.String(length=16), nullable=False),
        sa.Column("memo", sa.String(length=255), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(["transaction_id"], ["ledger_transactions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transaction_id", "seq", name="uq_ledger_leg_tx_seq"),
    )
    op.create_index("ix_ledger_legs_transaction_id", "ledger_legs", ["transaction_id"])


def downgrade() -> None:
    op.drop_table("ledger_legs")
    op.drop_table("ledger_transactions")
