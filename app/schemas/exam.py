"""考试相关 Pydantic 模型."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.exam import ExamStatus


def _ensure_utc(value: datetime) -> datetime:
    """把无时区时间按本地时区解释并转成 UTC，统一为 aware datetime."""
    if value.tzinfo is None:
        return value.astimezone(UTC)
    return value.astimezone(UTC)


class ExamCreate(BaseModel):
    """创建考试请求."""

    name: str = Field(..., min_length=1, max_length=100)
    subject: str = Field(..., min_length=1, max_length=50)
    start_time: datetime
    end_time: datetime

    @field_validator("start_time", "end_time")
    @classmethod
    def _normalize_time(cls, value: datetime) -> datetime:
        return _ensure_utc(value)


class ExamUpdate(BaseModel):
    """更新考试请求."""

    name: str | None = Field(None, min_length=1, max_length=100)
    subject: str | None = Field(None, min_length=1, max_length=50)
    start_time: datetime | None = None
    end_time: datetime | None = None
    status: ExamStatus | None = None

    @field_validator("start_time", "end_time")
    @classmethod
    def _normalize_time(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _ensure_utc(value)


class ExamResponse(BaseModel):
    """考试响应模型."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    subject: str
    duration: int
    start_time: datetime
    end_time: datetime
    actual_start_time: datetime | None
    actual_end_time: datetime | None
    status: ExamStatus
    created_at: datetime
    updated_at: datetime


class ExamDetailResponse(ExamResponse):
    """考试详情响应模型（包含题目列表）."""

    problems: list[dict[str, Any]] = []


class ExamListResponse(BaseModel):
    """考试列表项."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    subject: str
    duration: int
    start_time: datetime
    end_time: datetime
    actual_start_time: datetime | None
    actual_end_time: datetime | None
    status: ExamStatus
    created_at: datetime
    updated_at: datetime
