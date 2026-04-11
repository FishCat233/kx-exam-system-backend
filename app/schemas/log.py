"""日志相关 Pydantic 模型."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.operation_log import OperationLevel


class LogCreateRequest(BaseModel):
    """创建日志请求."""

    operation_type: str = Field(..., description="操作类型")
    description: str = Field(..., description="操作描述")
    level: OperationLevel = Field(default=OperationLevel.NORMAL, description="日志级别")


class LogResponse(BaseModel):
    """日志响应."""

    id: int
    student_id: int
    operation_type: str
    description: str
    level: OperationLevel
    ip_address: str | None
    user_agent: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class LogListItem(BaseModel):
    """日志列表项."""

    id: int
    student_name: str
    student_id: str
    operation_type: str
    description: str
    level: OperationLevel
    created_at: datetime

    class Config:
        from_attributes = True
