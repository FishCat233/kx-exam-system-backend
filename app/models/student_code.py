"""考生代码模型."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UTCDateTime

if TYPE_CHECKING:
    from app.models.problem import Problem
    from app.models.student import Student


class StudentCode(Base):
    """考生代码表 — 一个考生一题最多一条记录."""

    __tablename__ = "student_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id"), nullable=False)
    code: Mapped[str] = mapped_column(Text, default="")
    saved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint("student_id", "problem_id", name="uq_student_code_per_problem"),
    )

    # 关系
    student: Mapped["Student"] = relationship("Student", back_populates="codes")
    problem: Mapped["Problem"] = relationship("Problem", back_populates="codes")
