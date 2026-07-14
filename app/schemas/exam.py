"""考试相关 Pydantic 模型."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.exam import ExamStatus


class ExamCreate(BaseModel):
    """创建考试请求."""

    name: str = Field(..., min_length=1, max_length=100)
    subject: str = Field(..., min_length=1, max_length=50)
    start_time: datetime
    end_time: datetime
    pledge_content: str | None = None


class ExamUpdate(BaseModel):
    """更新考试请求."""

    name: str | None = Field(None, min_length=1, max_length=100)
    subject: str | None = Field(None, min_length=1, max_length=50)
    start_time: datetime | None = None
    end_time: datetime | None = None
    pledge_content: str | None = None
    status: ExamStatus | None = None


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
    pledge_content: str | None
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
    pledge_content: str | None
    created_at: datetime
    updated_at: datetime
