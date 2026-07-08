"""考生相关 Pydantic 模型."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.student import SubmitStatus


class StudentCreate(BaseModel):
    """创建考生请求."""

    student_id: str = Field(..., pattern=r"^\d+$")
    name: str = Field(..., pattern=r"^[\u4e00-\u9fa5a-zA-Z\s]+$")


class StudentImportRequest(BaseModel):
    """批量导入考生请求."""

    students: list[StudentCreate]


class StudentResponse(BaseModel):
    """考生响应模型."""

    model_config = ConfigDict(from_attributes=True)

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


class StudentListItem(BaseModel):
    """考生列表项."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: str
    name: str
    login_code: str
    login_time: datetime | None
    submit_time: datetime | None
    submit_status: SubmitStatus


class StudentOperationLogItem(BaseModel):
    """考生操作日志项."""

    id: int
    operation_type: str
    description: str
    level: str
    created_at: datetime


class StudentCodeItem(BaseModel):
    """考生代码记录项."""

    id: int
    problem_id: int
    saved_at: datetime | None


class StudentDetail(BaseModel):
    """考生详情."""

    model_config = ConfigDict(from_attributes=True)

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
    logs: list[StudentOperationLogItem] = []
    codes: list[StudentCodeItem] = []


class CodeResponse(BaseModel):
    """代码响应."""

    code: str
    saved_at: datetime | None


class CodeSaveRequest(BaseModel):
    """保存代码请求."""

    code: str = Field(..., max_length=50_000)


class CodeSaveResponse(BaseModel):
    """保存代码响应."""

    saved_at: datetime


class CodeSubmitResponse(BaseModel):
    """提交代码（交卷）响应."""

    submit_time: datetime
    status: SubmitStatus
