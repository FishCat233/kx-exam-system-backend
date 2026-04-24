"""考试模型."""

import enum
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ExamStatus(enum.StrEnum):
    """考试状态枚举."""

    NOT_STARTED = "not_started"
    ONGOING = "ongoing"
    ENDED = "ended"


class Exam(Base):
    """考试表."""

    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)  # 分钟
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    actual_start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    actual_end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[ExamStatus] = mapped_column(Enum(ExamStatus), default=ExamStatus.NOT_STARTED)
    pledge_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # 关系
    problems: Mapped[list["Problem"]] = relationship("Problem", back_populates="exam")  # noqa: F821
    students: Mapped[list["Student"]] = relationship("Student", back_populates="exam")  # noqa: F821
