"""考生认证相关工具函数."""

import secrets
import string
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Student

# 定义学生安全方案
student_security = HTTPBearer(
    scheme_name="Bearer",
    description="考生 JWT Token，格式: Bearer {token}",
    auto_error=False,
)


def generate_login_code(length: int = 8) -> str:
    """生成随机登录码.

    Args:
        length: 登录码长度，默认 8 位

    Returns:
        随机字母数字组合的登录码
    """
    characters = string.ascii_letters + string.digits
    return "".join(secrets.choice(characters) for _ in range(length))


def create_student_token(student_id: int, exam_id: int) -> str:
    """创建考生 JWT Token.

    Args:
        student_id: 考生 ID
        exam_id: 考试 ID

    Returns:
        JWT Token 字符串
    """
    from datetime import UTC, datetime, timedelta

    to_encode = {
        "type": "student",
        "student_id": student_id,
        "exam_id": exam_id,
    }
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def decode_student_token(token: str) -> dict | None:
    """解码考生 JWT Token.

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


async def require_student(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(student_security),
    ],
    db: AsyncSession = Depends(get_db),
) -> Student:
    """考生认证依赖.

    Args:
        credentials: HTTP Bearer Token 凭证
        db: 数据库会话

    Returns:
        当前考生对象

    Raises:
        HTTPException: 401 - Token 格式错误或无效
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
    payload = decode_student_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # 3. 检查 payload 中的 type 是否为 "student"
    token_type = payload.get("type")
    if token_type != "student":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    # 4. 获取 student_id 并查询数据库
    student_id = payload.get("student_id")
    if student_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Student not found",
        )

    return student
