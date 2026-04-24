"""题目相关 Pydantic 模型."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProblemCreate(BaseModel):
    """创建题目请求."""

    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    order_num: int = Field(default=0)


class ProblemUpdate(BaseModel):
    """更新题目请求."""

    title: str | None = Field(None, min_length=1, max_length=200)
    content: str | None = Field(None, min_length=1)
    order_num: int | None = None


class ProblemResponse(BaseModel):
    """题目响应模型."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    exam_id: int
    title: str
    content: str
    order_num: int
    created_at: datetime
    updated_at: datetime


class ProblemBrief(BaseModel):
    """题目简要信息."""

    id: int
    title: str
    order_num: int
