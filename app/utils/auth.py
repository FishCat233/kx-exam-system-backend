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
from app.models import AdminToken

# 定义安全方案
admin_security = HTTPBearer(
    scheme_name="Bearer",
    description="管理员 JWT Token，格式: Bearer {token}",
    auto_error=False,
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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
) -> AdminToken:
    """管理员权限依赖.

    验证管理员 Token 的有效性。

    Args:
        credentials: HTTP Bearer Token 凭证
        db: 数据库会话

    Returns:
        当前管理员 Token 对象

    Raises:
        HTTPException: 401 - Token 无效，403 - Token 被停用或过期
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

    # 4. 查询数据库验证 Token 是否存在且 is_active=True
    result = await db.execute(
        select(AdminToken).where(AdminToken.token == token, AdminToken.is_active.is_(True))
    )
    admin_token = result.scalar_one_or_none()

    if admin_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token not found or inactive",
        )

    # 5. 检查 Token 是否过期
    if admin_token.expires_at is not None:
        # 确保 expires_at 是带时区的
        expires_at = admin_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
            )

    return admin_token
