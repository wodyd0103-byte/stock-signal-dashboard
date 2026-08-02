"""drop dead live-trading tables (feature removed)

Revision ID: 0002_drop_live
Revises: 0001_initial
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_drop_live"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DEAD = ["trades", "orders", "positions", "equity_snapshots", "strategy_modes", "trading_settings"]


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for t in _DEAD:
        if t in existing:
            op.drop_table(t)


def downgrade() -> None:
    pass  # 죽은 테이블 복원 안 함
