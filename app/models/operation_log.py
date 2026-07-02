"""操作日志模型."""

import enum
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.student import Student


class OperationLevel(enum.StrEnum):
    """操作日志等级枚举."""

    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


class OperationLog(Base):
    """操作日志表."""

    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    operation_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    level: Mapped[OperationLevel] = mapped_column(
        Enum(OperationLevel), default=OperationLevel.NORMAL
    )
    ip_address: Mapped[str | None] = mapped_column(String, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    # 关系
    student: Mapped["Student"] = relationship("Student", back_populates="logs")
