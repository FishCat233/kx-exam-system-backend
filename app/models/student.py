"""考生模型."""

import enum
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SubmitStatus(str, enum.Enum):
    """交卷状态枚举."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    FORCE_SUBMITTED = "force_submitted"


class Student(Base):
    """考生表."""

    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"), nullable=False)
    student_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    login_code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    login_code_used: Mapped[bool] = mapped_column(Boolean, default=False)
    login_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submit_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submit_status: Mapped[SubmitStatus] = mapped_column(
        Enum(SubmitStatus), default=SubmitStatus.NOT_STARTED
    )
    websocket_token: Mapped[str | None] = mapped_column(String, nullable=True)
    is_fullscreen: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # 关系
    exam: Mapped["Exam"] = relationship("Exam", back_populates="students")  # noqa: F821
    codes: Mapped[list["StudentCode"]] = relationship("StudentCode", back_populates="student")  # noqa: F821
    logs: Mapped[list["OperationLog"]] = relationship("OperationLog", back_populates="student")  # noqa: F821
