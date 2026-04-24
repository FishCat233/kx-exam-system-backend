"""认证相关工具函数."""

import enum
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Admin


class AdminPermission(enum.StrEnum):
    """高权限管理员能力枚举."""

    MANAGE_ADMINS = "manage_admins"
    MANAGE_EXAM_SETTINGS = "manage_exam_settings"
    MANAGE_PROBLEMS = "manage_problems"
    MANAGE_STUDENTS = "manage_students"


# 定义安全方案
admin_security = HTTPBearer(
    scheme_name="Bearer",
    description="管理员 JWT Token，格式: Bearer {token}",
    auto_error=False,
)

# 使用 argon2 替代 bcrypt 以避免 72 字节限制
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码.

    Args:
        plain_password: 明文密码
        hashed_password: 哈希密码

    Returns:
        是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """获取密码哈希.

    Args:
        password: 明文密码

    Returns:
        哈希后的密码
    """
    return pwd_context.hash(password)


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """创建 JWT Token.

    Args:
        data: 要编码的数据
        expires_delta: 过期时间增量

    Returns:
        JWT Token 字符串
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def decode_token(token: str) -> dict[str, Any] | None:
    """解码 JWT Token.

    Args:
        token: JWT Token 字符串

    Returns:
        解码后的数据，失败返回 None
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        return None


async def require_role(
    role: str,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(admin_security),
    ],
    db: AsyncSession = Depends(get_db),
) -> Admin:
    """要求特定角色的权限依赖.

    Args:
        role: 要求的角色（"super_admin" 或 "admin"）
        credentials: HTTP Bearer Token 凭证
        db: 数据库会话

    Returns:
        当前管理员对象

    Raises:
        HTTPException: 401 - Token 无效，403 - 权限不足或账号被停用
    """
    from app.models.admin import AdminRole

    # 1. 先验证管理员身份
    admin = await require_admin(credentials, db)

    # 2. 检查角色权限
    if role == "super_admin" and admin.role != AdminRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin permission required",
        )

    return admin


def has_permission(admin: Admin, permission: AdminPermission) -> bool:
    """判断管理员是否拥有指定能力."""
    from app.models.admin import AdminRole

    privileged_permissions = {
        AdminPermission.MANAGE_ADMINS,
        AdminPermission.MANAGE_EXAM_SETTINGS,
        AdminPermission.MANAGE_PROBLEMS,
        AdminPermission.MANAGE_STUDENTS,
    }
    return admin.role == AdminRole.SUPER_ADMIN and permission in privileged_permissions


def permission_required(permission: AdminPermission):
    """生成基于能力的管理员权限依赖."""

    async def dependency(
        credentials: Annotated[
            HTTPAuthorizationCredentials | None,
            Security(admin_security),
        ],
        db: AsyncSession = Depends(get_db),
    ) -> Admin:
        admin = await require_admin(credentials, db)
        if not has_permission(admin, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission.value}",
            )
        return admin

    dependency.__name__ = f"require_{permission.value}"
    return dependency


async def require_super_admin_role(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(admin_security),
    ],
    db: AsyncSession = Depends(get_db),
) -> Admin:
    """超级管理员权限依赖（基于 role 字段）.

    Args:
        credentials: HTTP Bearer Token 凭证
        db: 数据库会话

    Returns:
        当前管理员对象

    Raises:
        HTTPException: 401 - Token 无效，403 - 不是超级管理员或账号被停用
    """
    return await require_role("super_admin", credentials, db)


require_admin_management = permission_required(AdminPermission.MANAGE_ADMINS)
require_exam_management = permission_required(AdminPermission.MANAGE_EXAM_SETTINGS)
require_problem_management = permission_required(AdminPermission.MANAGE_PROBLEMS)
require_student_management = permission_required(AdminPermission.MANAGE_STUDENTS)


async def require_admin(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(admin_security),
    ],
    db: AsyncSession = Depends(get_db),
) -> Admin:
    """管理员权限依赖.

    验证管理员 Token 的有效性。

    Args:
        credentials: HTTP Bearer Token 凭证
        db: 数据库会话

    Returns:
        当前管理员对象

    Raises:
        HTTPException: 401 - Token 无效，403 - 账号被停用
    """
    # 1. 检查凭证是否存在
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # 2. 解码 JWT Token
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # 3. 检查 payload 中的 type 是否为 "admin"
    token_type = payload.get("type")
    if token_type != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    # 4. 获取管理员 ID
    admin_id = payload.get("admin_id")
    if admin_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # 5. 查询数据库验证管理员是否存在
    result = await db.execute(select(Admin).where(Admin.id == admin_id))
    admin = result.scalar_one_or_none()

    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin not found",
        )

    # 6. 检查管理员是否被停用
    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is deactivated",
        )

    return admin
