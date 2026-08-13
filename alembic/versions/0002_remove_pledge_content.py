"""移除考试的 pledge_content 字段（考前承诺书流程已移除）.

Revision ID: 0002_remove_pledge_content
Revises: 0001_initial
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_remove_pledge_content"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("exams", "pledge_content")


def downgrade() -> None:
    op.add_column("exams", sa.Column("pledge_content", sa.Text(), nullable=True))
