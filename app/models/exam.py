"""考试模型."""

import enum
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UTCDateTime
from app.models.enum_utils import enum_values

if TYPE_CHECKING:
    from app.models.problem import Problem
    from app.models.student import Student


class ExamStatus(enum.StrEnum):
    """考试状态枚举 — 严格单向: not_started → ongoing → ended."""

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
    start_time: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    end_time: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    actual_start_time: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    actual_end_time: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    status: Mapped[ExamStatus] = mapped_column(
        Enum(ExamStatus, values_callable=enum_values), default=ExamStatus.NOT_STARTED
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # 关系
    problems: Mapped[list["Problem"]] = relationship(
        "Problem", back_populates="exam", cascade="all, delete-orphan"
    )
    students: Mapped[list["Student"]] = relationship(
        "Student", back_populates="exam", cascade="all, delete-orphan"
    )
