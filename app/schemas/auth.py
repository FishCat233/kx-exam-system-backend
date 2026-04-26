"""认证相关 Pydantic 模型."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.exam import ExamStatus


class TokenPayload(BaseModel):
    """Token 载荷."""

    sub: str | None = None
    exp: datetime | None = None
    type: str | None = None


class LoginRequest(BaseModel):
    """考生登录请求."""

    student_id: str = Field(..., pattern=r"^\d+$", description="学号，纯数字")
    name: str = Field(..., pattern=r"^[\u4e00-\u9fa5a-zA-Z\s]+$", description="姓名，中文或英文")
    login_code: str = Field(..., pattern=r"^[a-zA-Z0-9]+$", description="登录码，数字字母组成")
    exam_id: int = Field(..., description="考试ID")


class ExamInfo(BaseModel):
    """考试信息."""

    id: int
    name: str
    subject: str
    duration: int
    start_time: datetime
    end_time: datetime
    status: ExamStatus
    pledge_content: str | None = None


class ProblemBrief(BaseModel):
    """题目简要信息."""

    id: int
    title: str
    order_num: int


class LoginResponse(BaseModel):
    """考生登录响应."""

    student_token: str
    exam_info: ExamInfo
    problems: list[ProblemBrief]


class FullscreenRequest(BaseModel):
    """全屏状态上报请求."""

    success: bool
    reason: str | None = None


class FullscreenResponse(BaseModel):
    """全屏状态上报响应."""

    websocket_token: str
    ws_url: str


class AdminVerifyResponse(BaseModel):
    """管理员验证响应."""

    valid: bool
    admin_info: dict[str, Any] | None = None
