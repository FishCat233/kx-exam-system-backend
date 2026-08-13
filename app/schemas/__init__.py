"""Pydantic 模型模块."""

from app.schemas.admin import (
    AdminCreate,
    AdminInfo,
    AdminListItem,
    AdminLoginRequest,
    AdminLoginResponse,
    AdminResponse,
    AdminTokenCreate,
    AdminTokenListItem,
    AdminTokenResponse,
    AdminTokenUpdate,
    AdminUpdate,
    AdminVerifyRequest,
    ChangePasswordRequest,
    ForceChangePasswordRequest,
)
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
from app.schemas.exam import (
    ExamCreate,
    ExamDetailResponse,
    ExamListResponse,
    ExamResponse,
    ExamUpdate,
)
from app.schemas.log import LogCreateRequest, LogListItem, LogResponse, WsReportRequest
from app.schemas.problem import (
    ProblemBrief,
    ProblemCreate,
    ProblemOption,
    ProblemResponse,
    ProblemUpdate,
)
from app.schemas.student import (
    CodeResponse,
    CodeSaveRequest,
    CodeSaveResponse,
    CodeSubmitResponse,
    StudentCreate,
    StudentDetail,
    StudentImportRequest,
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
    # Admin
    "AdminCreate",
    "AdminUpdate",
    "AdminResponse",
    "AdminListItem",
    "AdminLoginRequest",
    "AdminLoginResponse",
    "AdminInfo",
    "ChangePasswordRequest",
    "ForceChangePasswordRequest",
    "AdminTokenCreate",
    "AdminTokenUpdate",
    "AdminTokenResponse",
    "AdminTokenListItem",
    "AdminVerifyRequest",
    # Exam
    "ExamCreate",
    "ExamUpdate",
    "ExamResponse",
    "ExamDetailResponse",
    "ExamListResponse",
    "ExamInfo",
    # Problem
    "ProblemCreate",
    "ProblemUpdate",
    "ProblemResponse",
    "ProblemBrief",
    "ProblemOption",
    # Student
    "StudentCreate",
    "StudentImportRequest",
    "StudentResponse",
    "StudentListItem",
    "StudentDetail",
    "CodeResponse",
    "CodeSaveRequest",
    "CodeSaveResponse",
    "CodeSubmitResponse",
    # Log
    "LogCreateRequest",
    "LogResponse",
    "LogListItem",
    "WsReportRequest",
]
