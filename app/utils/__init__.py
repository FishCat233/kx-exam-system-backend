"""工具函数包."""

from app.utils.auth import (
    create_access_token,
    decode_token,
    get_password_hash,
    require_admin,
    require_super_admin,
    verify_password,
    verify_super_admin,
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
    "verify_super_admin",
    "require_super_admin",
    "require_admin",
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
