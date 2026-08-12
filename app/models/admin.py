"""管理员模型."""

import enum
from datetime import UTC, datetime

from sqlalchemy import Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, UTCDateTime
from app.models.enum_utils import enum_values


class AdminRole(enum.StrEnum):
    """管理员角色枚举."""

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"


class Admin(Base):
    """管理员表."""

    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[AdminRole] = mapped_column(
        Enum(AdminRole, values_callable=enum_values), default=AdminRole.ADMIN
    )
    remark: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
