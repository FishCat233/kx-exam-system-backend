"""新增高级管理员角色（senior_admin）.

高级管理员拥有除管理管理员外的全部权限：考试管理、题目管理、考生管理（导入/删除/查看/强制收卷）。
PostgreSQL 原生枚举需 ALTER TYPE 追加新值。

Revision ID: 0003_add_senior_admin_role
Revises: 0002_remove_pledge_content
Create Date: 2026-08-14
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_add_senior_admin_role"
down_revision: str | None = "0002_remove_pledge_content"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE adminrole ADD VALUE 'senior_admin'")


def downgrade() -> None:
    op.execute("ALTER TYPE adminrole DROP VALUE 'senior_admin'")
