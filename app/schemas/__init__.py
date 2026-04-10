"""Pydantic 模型模块."""

from app.schemas.auth import (
    AdminVerifyResponse,
    ExamInfo,
    FullscreenRequest,
    FullscreenResponse,
    LoginRequest,
    LoginResponse,
    TokenPayload,
)
from app.schemas.auth import (
    ProblemBrief as AuthProblemBrief,
)
from app.schemas.common import (
    ErrorResponse,
    PaginationParams,
    PaginationResponse,
    ResponseModel,
)
from app.schemas.exam import ExamCreate, ExamListResponse, ExamResponse, ExamUpdate
from app.schemas.problem import (
    ProblemBrief,
    ProblemCreate,
    ProblemResponse,
    ProblemUpdate,
)
from app.schemas.student import (
    CodeResponse,
    CodeSaveRequest,
    CodeSaveResponse,
    StudentCreate,
    StudentDetail,
    StudentListItem,
    StudentResponse,
)

__all__ = [
    # Common
    "ResponseModel",
    "PaginationParams",
    "PaginationResponse",
    "ErrorResponse",
    # Auth
    "TokenPayload",
    "LoginRequest",
    "LoginResponse",
    "FullscreenRequest",
    "FullscreenResponse",
    "AdminVerifyResponse",
    "AuthProblemBrief",
    # Exam
    "ExamCreate",
    "ExamUpdate",
    "ExamResponse",
    "ExamListResponse",
    "ExamInfo",
    # Problem
    "ProblemCreate",
    "ProblemUpdate",
    "ProblemResponse",
    "ProblemBrief",
    # Student
    "StudentCreate",
    "StudentResponse",
    "StudentListItem",
    "StudentDetail",
    "CodeResponse",
    "CodeSaveRequest",
    "CodeSaveResponse",
]
