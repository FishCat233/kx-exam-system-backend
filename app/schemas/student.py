"""考生相关 Pydantic 模型."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.student import SubmitStatus


class StudentCreate(BaseModel):
    """创建考生请求."""

    student_id: str = Field(..., pattern=r"^\d+$")
    name: str = Field(..., pattern=r"^[\u4e00-\u9fa5]+$")


class StudentResponse(BaseModel):
    """考生响应模型."""

    id: int
    exam_id: int
    student_id: str
    name: str
    login_code: str
    login_code_used: bool
    login_time: datetime | None
    submit_time: datetime | None
    submit_status: SubmitStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StudentListItem(BaseModel):
    """考生列表项."""

    id: int
    student_id: str
    name: str
    login_code: str
    login_time: datetime | None
    submit_time: datetime | None
    submit_status: SubmitStatus

    class Config:
        from_attributes = True


class StudentDetail(BaseModel):
    """考生详情."""

    id: int
    exam_id: int
    student_id: str
    name: str
    login_code: str
    login_code_used: bool
    login_time: datetime | None
    submit_time: datetime | None
    submit_status: SubmitStatus
    is_fullscreen: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CodeResponse(BaseModel):
    """代码响应."""

    code: str
    saved_at: datetime | None


class CodeSaveRequest(BaseModel):
    """保存代码请求."""

    code: str


class CodeSaveResponse(BaseModel):
    """保存代码响应."""

    saved_at: datetime


class CodeSubmitResponse(BaseModel):
    """提交代码（交卷）响应."""

    submit_time: datetime
    status: SubmitStatus
