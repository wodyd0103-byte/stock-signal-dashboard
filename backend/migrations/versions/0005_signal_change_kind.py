"""signal_changes.kind — 등급 전환과 점수 이동을 구분

Revision ID: 0005_signal_change_kind
Revises: 0004_signal_changes
Create Date: 2026-08-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_signal_change_kind"
down_revision: Union[str, None] = "0004_signal_changes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("signal_changes")}
    if "kind" in columns:
        return
    # 기존 행은 전부 등급 전환이다 — 그때는 그것만 기록했다.
    op.add_column(
        "signal_changes",
        sa.Column("kind", sa.String(length=8), nullable=False, server_default="signal"),
    )
    op.create_index("ix_signal_changes_kind", "signal_changes", ["kind"])


def downgrade() -> None:
    op.drop_index("ix_signal_changes_kind", table_name="signal_changes")
    op.drop_column("signal_changes", "kind")
