"""T13d — paper order lifecycle columns + events + CLOSING.

Revision ID: i5j6k7l8m9n0
Revises: h4i5j6k7l8m9
Create Date: 2026-09-24 16:00:00.000000

No accounting change. Backfill existing FILLED rows with legacy client_order_id
and a single birth→FILLED event dated created_at.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i5j6k7l8m9n0"
down_revision: Union[str, Sequence[str], None] = "h4i5j6k7l8m9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "paper_positions",
        sa.Column("close_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column(
        "paper_positions",
        "status",
        existing_type=sa.String(length=8),
        type_=sa.String(length=16),
        existing_nullable=False,
    )

    op.add_column("paper_orders", sa.Column("client_order_id", sa.String(length=160), nullable=True))
    op.add_column(
        "paper_orders",
        sa.Column("filled_qty", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column("paper_orders", sa.Column("avg_fill_price", sa.Float(), nullable=True))
    op.add_column(
        "paper_orders",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("paper_orders", sa.Column("intent_ref", sa.String(length=128), nullable=True))
    op.create_index("ix_paper_orders_client_order_id", "paper_orders", ["client_order_id"])

    op.create_table(
        "paper_order_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("order_id", sa.String(length=36), sa.ForeignKey("paper_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(length=16), nullable=True),
        sa.Column("to_status", sa.String(length=16), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(length=128), nullable=True),
        sa.Column("codes", sa.JSON(), nullable=True),
    )
    op.create_index("ix_paper_order_events_order_id", "paper_order_events", ["order_id"])
    op.create_index("ix_paper_order_events_at", "paper_order_events", ["at"])
    op.create_unique_constraint(
        "uq_paper_order_event_seq", "paper_order_events", ["order_id", "seq"]
    )

    # Backfill legacy fill-log rows
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, qty, filled_price, created_at, status FROM paper_orders")).fetchall()
    import uuid

    for row in rows:
        oid, qty, filled_price, created_at, status = row
        coid = f"legacy-{oid}"
        fq = float(qty or 0.0) if (status or "").upper() == "FILLED" else 0.0
        avg = float(filled_price) if filled_price is not None and fq > 0 else None
        conn.execute(
            sa.text(
                "UPDATE paper_orders SET client_order_id = :c, filled_qty = :fq, avg_fill_price = :avg "
                "WHERE id = :id"
            ),
            {"c": coid, "fq": fq, "avg": avg, "id": oid},
        )
        conn.execute(
            sa.text(
                "INSERT INTO paper_order_events (id, order_id, seq, from_status, to_status, at, reason, codes) "
                "VALUES (:id, :oid, 1, NULL, :st, :at, 'legacy_backfill', :codes)"
            ),
            {
                "id": str(uuid.uuid4()),
                "oid": oid,
                "st": status or "FILLED",
                "at": created_at,
                "codes": "[]",
            },
        )

    op.create_unique_constraint(
        "uq_paper_order_client", "paper_orders", ["portfolio_id", "client_order_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_paper_order_client", "paper_orders", type_="unique")
    op.drop_table("paper_order_events")
    op.drop_index("ix_paper_orders_client_order_id", table_name="paper_orders")
    op.drop_column("paper_orders", "intent_ref")
    op.drop_column("paper_orders", "expires_at")
    op.drop_column("paper_orders", "avg_fill_price")
    op.drop_column("paper_orders", "filled_qty")
    op.drop_column("paper_orders", "client_order_id")
    op.alter_column(
        "paper_positions",
        "status",
        existing_type=sa.String(length=16),
        type_=sa.String(length=8),
        existing_nullable=False,
    )
    op.drop_column("paper_positions", "close_requested_at")
