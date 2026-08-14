"""工具函数包."""

from app.utils.auth import (
    AdminPermission,
    create_access_token,
    decode_token,
    get_password_hash,
    require_admin,
    require_admin_management,
    require_exam_management,
    require_force_submit_students,
    require_problem_management,
    require_role,
    require_student_management,
    require_super_admin_role,
    require_view_students,
    verify_password,
)
from app.utils.exceptions import (
    BadRequestException,
    NotFoundException,
    UnauthorizedException,
)
from app.utils.student_auth import (
    create_student_token,
    decode_student_token,
    generate_login_code,
    require_student,
)

__all__ = [
    # 认证相关
    "create_access_token",
    "decode_token",
    "get_password_hash",
    "verify_password",
    "AdminPermission",
    "require_role",
    "require_super_admin_role",
    "require_admin",
    "require_admin_management",
    "require_exam_management",
    "require_problem_management",
    "require_student_management",
    "require_view_students",
    "require_force_submit_students",
    # 考生认证相关
    "generate_login_code",
    "create_student_token",
    "decode_student_token",
    "require_student",
    # 异常相关
    "BadRequestException",
    "NotFoundException",
    "UnauthorizedException",
]
