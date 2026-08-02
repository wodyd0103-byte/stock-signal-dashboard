"""initial schema — watchlist + recommendations

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing = set(insp.get_table_names())

    if "watchlist_items" not in existing:
        op.create_table(
            "watchlist_items",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("ticker", sa.String(length=32), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("ticker", name="uq_watchlist_ticker"),
        )
        op.create_index("ix_watchlist_items_ticker", "watchlist_items", ["ticker"])
        op.create_index("ix_watchlist_items_id", "watchlist_items", ["id"])

    if "recommendations" not in existing:
        op.create_table(
            "recommendations",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("ticker", sa.String(length=32), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=True),
            sa.Column("market", sa.String(length=8), nullable=True),
            sa.Column("signal", sa.String(length=20), nullable=False),
            sa.Column("buy_score", sa.Integer(), nullable=True),
            sa.Column("risk_score", sa.Integer(), nullable=True),
            sa.Column("price_at_rec", sa.Float(), nullable=False),
            sa.Column("recommended_at", sa.DateTime(), nullable=True),
            sa.Column("evaluated_at", sa.DateTime(), nullable=True),
            sa.Column("price_after", sa.Float(), nullable=True),
            sa.Column("return_pct", sa.Float(), nullable=True),
            sa.Column("horizon_days", sa.Integer(), nullable=True),
            sa.Column("hit", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=True),
        )
        op.create_index("ix_recommendations_ticker", "recommendations", ["ticker"])
        op.create_index("ix_recommendations_recommended_at", "recommendations", ["recommended_at"])
        op.create_index("ix_recommendations_status", "recommendations", ["status"])
        op.create_index("ix_recommendations_id", "recommendations", ["id"])


def downgrade() -> None:
    op.drop_table("recommendations")
    op.drop_table("watchlist_items")
