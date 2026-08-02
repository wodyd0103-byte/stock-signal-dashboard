"""holdings table (portfolio)

Revision ID: 0003_holdings
Revises: 0002_drop_live
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_holdings"
down_revision: Union[str, None] = "0002_drop_live"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if "holdings" in set(sa.inspect(bind).get_table_names()):
        return
    op.create_table(
        "holdings",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("avg_price", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("ticker", name="uq_holding_ticker"),
    )
    op.create_index("ix_holdings_ticker", "holdings", ["ticker"])
    op.create_index("ix_holdings_id", "holdings", ["id"])


def downgrade() -> None:
    op.drop_table("holdings")
