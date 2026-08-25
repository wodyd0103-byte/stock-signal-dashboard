"""signal_changes table (digest signal history)

Revision ID: 0004_signal_changes
Revises: 0003_holdings
Create Date: 2026-08-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_signal_changes"
down_revision: Union[str, None] = "0003_holdings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if "signal_changes" in set(sa.inspect(bind).get_table_names()):
        return
    op.create_table(
        "signal_changes",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("previous_signal", sa.String(length=16), nullable=True),
        sa.Column("current_signal", sa.String(length=16), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("buy_score", sa.Integer(), nullable=True),
        sa.Column("risk_score", sa.Integer(), nullable=True),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=True),
    )
    # id 는 컬럼 정의의 index=True 로 이미 인덱스가 붙는다. 여기서 또 만들면
    # "index ix_signal_changes_id already exists" 로 죽는다.
    op.create_index("ix_signal_changes_ticker", "signal_changes", ["ticker"])
    op.create_index("ix_signal_changes_recorded_at", "signal_changes", ["recorded_at"])


def downgrade() -> None:
    op.drop_table("signal_changes")
