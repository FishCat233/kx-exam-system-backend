"""认证相关路由."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import AdminToken, Exam, Problem, Student, SubmitStatus
from app.schemas import (
    AdminVerifyResponse,
    ExamInfo,
    FullscreenRequest,
    FullscreenResponse,
    LoginRequest,
    LoginResponse,
    ProblemBrief,
    ResponseModel,
)
from app.utils.auth import decode_token
from app.utils.student_auth import create_student_token, decode_student_token

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post(
    "/student/login",
    response_model=ResponseModel[LoginResponse],
    summary="考生登录",
    description="考生使用学号、姓名和登录码登录系统。",
    response_description="返回考生 Token 和考试信息",
)
async def student_login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[LoginResponse]:
    """考生登录.

    验证考生的学号、姓名和登录码，返回考生 Token 和考试信息。

    Args:
        request: 登录请求数据
        db: 数据库会话

    Returns:
        包含考生 Token 和考试信息的响应

    Raises:
        HTTPException: 401 - 登录信息错误，400 - 登录码已使用
    """
    # 1. 查询考试是否存在
    result = await db.execute(select(Exam).where(Exam.id == request.exam_id))
    exam = result.scalar_one_or_none()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考试不存在",
        )

    # 2. 查询考生信息
    result = await db.execute(
        select(Student).where(
            Student.exam_id == request.exam_id,
            Student.student_id == request.student_id,
            Student.name == request.name,
            Student.login_code == request.login_code,
        )
    )
    student = result.scalar_one_or_none()

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录信息错误",
        )

    # 3. 检查登录码是否已使用
    if student.login_code_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="登录码已使用",
        )

    # 4. 标记登录码为已使用并记录登录时间
    student.login_code_used = True
    student.login_time = datetime.now(UTC)
    student.submit_status = SubmitStatus.IN_PROGRESS

    await db.commit()
    await db.refresh(student)

    # 5. 生成考生 JWT Token
    student_token = create_student_token(student.id, exam.id)

    # 6. 获取考试题目列表
    result = await db.execute(
        select(Problem).where(Problem.exam_id == exam.id).order_by(Problem.order_num)
    )
    problems = result.scalars().all()

    # 7. 构建响应数据
    exam_info = ExamInfo(
        id=exam.id,
        name=exam.name,
        subject=exam.subject,
        duration=exam.duration,
        start_time=exam.start_time,
        end_time=exam.end_time,
        status=exam.status,
        pledge_content=exam.pledge_content,
    )

    problem_list = [
        ProblemBrief(
            id=p.id,
            title=p.title,
            order_num=p.order_num,
        )
        for p in problems
    ]

    login_response = LoginResponse(
        student_token=student_token,
        exam_info=exam_info,
        problems=problem_list,
    )

    return ResponseModel(
        code=200,
        message="登录成功",
        data=login_response,
    )


@router.post(
    "/student/fullscreen",
    response_model=ResponseModel[FullscreenResponse],
    summary="全屏状态上报",
    description="考生登录后上报全屏状态，成功则返回 WebSocket 连接信息。",
    response_description="返回 WebSocket Token 和连接地址",
)
async def report_fullscreen(
    request: FullscreenRequest,
    authorization: Annotated[
        str,
        Header(..., description="Bearer Token, 格式: Bearer <student_token>"),
    ],
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[FullscreenResponse]:
    """上报全屏状态.

    考生进入全屏后上报状态，成功后获取 WebSocket 连接信息。

    Args:
        request: 全屏状态上报请求
        authorization: Authorization 请求头
        db: 数据库会话

    Returns:
        包含 WebSocket Token 和连接地址的响应

    Raises:
        HTTPException: 401 - Token 无效，400 - 全屏失败
    """
    # 1. 验证考生 Token
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
        )

    token = authorization[7:]
    payload = decode_student_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    student_id = payload.get("student_id")
    if student_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # 2. 查询考生信息
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Student not found",
        )

    # 3. 处理全屏失败情况
    if not request.success:
        # 记录失败原因到操作日志
        from app.models import OperationLevel, OperationLog

        log = OperationLog(
            student_id=student.id,
            operation_type="fullscreen_failed",
            description=f"全屏进入失败: {request.reason or '未知原因'}",
            level=OperationLevel.CRITICAL,
        )
        db.add(log)
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"全屏进入失败: {request.reason or '未知原因'}",
        )

    # 4. 全屏成功，生成 WebSocket Token
    import secrets

    websocket_token = secrets.token_urlsafe(32)
    student.websocket_token = websocket_token
    student.is_fullscreen = True

    await db.commit()

    # 5. 构建响应
    ws_url = f"ws://{settings.ws_host}:{settings.ws_port}{settings.ws_path}?token={websocket_token}"

    fullscreen_response = FullscreenResponse(
        websocket_token=websocket_token,
        ws_url=ws_url,
    )

    return ResponseModel(
        code=200,
        message="全屏状态上报成功",
        data=fullscreen_response,
    )


@router.post(
    "/admin/verify",
    response_model=ResponseModel[AdminVerifyResponse],
    summary="验证管理员 Token",
    description="验证管理员 Token 的有效性。",
    response_description="返回验证结果",
)
async def verify_admin(
    authorization: Annotated[
        str, Header(..., description="Bearer Token, 格式: Bearer <admin_token>")
    ],
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[AdminVerifyResponse]:
    """验证管理员 Token.

    验证管理员 Token 的有效性，包括 JWT 签名验证、Token 是否存在、是否启用以及是否过期。

    Args:
        authorization: Authorization 请求头，格式为 "Bearer <admin_token>"
        db: 数据库会话

    Returns:
        ResponseModel[AdminVerifyResponse]: 验证结果
        - valid: Token 是否有效
        - admin_info: 管理员信息（仅当 valid 为 True 时返回）

    Raises:
        HTTPException: 401 - Token 格式错误或无效

    Example:
        ```
        Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
        ```
    """
    # 1. 从 Authorization 头中提取 Bearer Token
    if not authorization.startswith("Bearer "):
        return ResponseModel(
            code=401,
            message="Invalid authorization header format. Expected 'Bearer <token>'",
            data=AdminVerifyResponse(valid=False, admin_info=None),
        )

    token = authorization[7:]  # 去掉 "Bearer " 前缀

    # 2. 使用 decode_token 解码 JWT
    payload = decode_token(token)
    if payload is None:
        return ResponseModel(
            code=401,
            message="Invalid or expired token",
            data=AdminVerifyResponse(valid=False, admin_info=None),
        )

    # 3. 检查 payload 中的 type 是否为 "admin"
    token_type = payload.get("type")
    if token_type != "admin":
        return ResponseModel(
            code=401,
            message="Invalid token type",
            data=AdminVerifyResponse(valid=False, admin_info=None),
        )

    # 4. 查询数据库验证 Token 是否存在且 is_active=True
    result = await db.execute(
        select(AdminToken).where(AdminToken.token == token, AdminToken.is_active.is_(True))
    )
    admin_token = result.scalar_one_or_none()

    if admin_token is None:
        return ResponseModel(
            code=401,
            message="Token not found or inactive",
            data=AdminVerifyResponse(valid=False, admin_info=None),
        )

    # 5. 检查 Token 是否过期（比较 expires_at 与当前时间）
    if admin_token.expires_at is not None and admin_token.expires_at < datetime.now():
        return ResponseModel(
            code=401,
            message="Token has expired",
            data=AdminVerifyResponse(valid=False, admin_info=None),
        )

    # 6. 返回验证结果
    admin_info = {
        "id": admin_token.id,
        "name": admin_token.name,
        "expires_at": admin_token.expires_at.isoformat() if admin_token.expires_at else None,
        "created_at": admin_token.created_at.isoformat() if admin_token.created_at else None,
        "updated_at": admin_token.updated_at.isoformat() if admin_token.updated_at else None,
    }

    return ResponseModel(
        code=200,
        message="Token is valid",
        data=AdminVerifyResponse(valid=True, admin_info=admin_info),
    )
