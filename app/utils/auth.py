"""认证相关工具函数."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Admin

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


def verify_super_admin(super_admin_key: str) -> bool:
    """验证超级管理员密钥.

    Args:
        super_admin_key: 超级管理员密钥

    Returns:
        是否验证通过
    """
    return super_admin_key == settings.super_admin_key


async def require_super_admin(
    x_super_admin_key: str = Header(..., alias="X-Super-Admin-Key"),
) -> bool:
    """超级管理员权限依赖.

    Args:
        x_super_admin_key: 请求头中的超级管理员密钥

    Returns:
        True 表示验证通过

    Raises:
        HTTPException: 验证失败时抛出 403 错误
    """
    if not verify_super_admin(x_super_admin_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid super admin key")
    return True


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
