"""add strategy_lab_experiments performance db

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-18 22:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "strategy_lab_experiments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("ruleset_id", sa.String(length=128), nullable=False),
        sa.Column("ruleset_version", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("timeframe", sa.String(length=8), nullable=False),
        sa.Column("market_regime", sa.String(length=32), nullable=False),
        sa.Column("date_range_start", sa.Integer(), nullable=True),
        sa.Column("date_range_end", sa.Integer(), nullable=True),
        sa.Column("rules_json", sa.JSON(), nullable=False),
        sa.Column("entry_rule", sa.String(length=64), nullable=False),
        sa.Column("exit_rule", sa.String(length=64), nullable=False),
        sa.Column("stop_rule", sa.String(length=64), nullable=False),
        sa.Column("target_rule", sa.String(length=64), nullable=False),
        sa.Column("n_bars", sa.Integer(), nullable=False),
        sa.Column("n_signals", sa.Integer(), nullable=False),
        sa.Column("n_matching_bars", sa.Integer(), nullable=False),
        sa.Column("number_of_trades", sa.Integer(), nullable=False),
        sa.Column("win_rate", sa.Float(), nullable=True),
        sa.Column("profit_factor", sa.Float(), nullable=True),
        sa.Column("expectancy", sa.Float(), nullable=True),
        sa.Column("max_drawdown", sa.Float(), nullable=True),
        sa.Column("sharpe", sa.Float(), nullable=True),
        sa.Column("sortino", sa.Float(), nullable=True),
        sa.Column("total_return", sa.Float(), nullable=True),
        sa.Column("cagr", sa.Float(), nullable=True),
        sa.Column("exposure", sa.Float(), nullable=True),
        sa.Column("mean_mfe_atr", sa.Float(), nullable=True),
        sa.Column("mean_mae_atr", sa.Float(), nullable=True),
        sa.Column("median_mfe_atr", sa.Float(), nullable=True),
        sa.Column("median_mae_atr", sa.Float(), nullable=True),
        sa.Column("pct_hit_plus_r_before_minus_r", sa.Float(), nullable=True),
        sa.Column("n_resolved_r", sa.Integer(), nullable=False),
        sa.Column("exit_reasons_json", sa.JSON(), nullable=False),
        sa.Column("event_study_json", sa.JSON(), nullable=False),
        sa.Column("parameters_json", sa.JSON(), nullable=False),
        sa.Column("dataset_version", sa.String(length=128), nullable=False),
        sa.Column("engine_version", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_strategy_lab_experiments_ruleset_id", "strategy_lab_experiments", ["ruleset_id"])
    op.create_index("ix_strategy_lab_experiments_symbol", "strategy_lab_experiments", ["symbol"])
    op.create_index("ix_strategy_lab_experiments_timeframe", "strategy_lab_experiments", ["timeframe"])
    op.create_index("ix_strategy_lab_experiments_market_regime", "strategy_lab_experiments", ["market_regime"])
    op.create_index("ix_strategy_lab_experiments_engine_version", "strategy_lab_experiments", ["engine_version"])
    op.create_index("ix_strategy_lab_experiments_created_at", "strategy_lab_experiments", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_strategy_lab_experiments_created_at", table_name="strategy_lab_experiments")
    op.drop_index("ix_strategy_lab_experiments_engine_version", table_name="strategy_lab_experiments")
    op.drop_index("ix_strategy_lab_experiments_market_regime", table_name="strategy_lab_experiments")
    op.drop_index("ix_strategy_lab_experiments_timeframe", table_name="strategy_lab_experiments")
    op.drop_index("ix_strategy_lab_experiments_symbol", table_name="strategy_lab_experiments")
    op.drop_index("ix_strategy_lab_experiments_ruleset_id", table_name="strategy_lab_experiments")
    op.drop_table("strategy_lab_experiments")
