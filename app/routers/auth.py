"""认证相关路由."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import (
    Admin,
    Exam,
    ExamStatus,
    OperationLevel,
    OperationLog,
    Problem,
    Student,
    SubmitStatus,
)
from app.schemas import (
    AdminInfo,
    AdminLoginRequest,
    AdminLoginResponse,
    AdminVerifyResponse,
    AuthProblemBrief,
    ExamInfo,
    FullscreenRequest,
    FullscreenResponse,
    LoginRequest,
    LoginResponse,
    ResponseModel,
)
from app.utils.auth import create_access_token, decode_token, verify_password
from app.utils.student_auth import create_student_token, require_student

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
    """考生登录."""
    # 1. 查询考试
    result = await db.execute(select(Exam).where(Exam.id == request.exam_id))
    exam = result.scalar_one_or_none()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考试不存在",
        )

    if exam.status != ExamStatus.ONGOING:
        status_messages = {
            ExamStatus.NOT_STARTED: "考试尚未开始",
            ExamStatus.ENDED: "考试已结束",
        }
        detail = status_messages.get(exam.status, "考试状态异常")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )

    # 2. 查询考生
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

    if student.login_code_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="登录码已使用",
        )

    # 3. 标记登录
    now = datetime.now(UTC)
    student.login_code_used = True
    student.login_time = now
    student.submit_status = SubmitStatus.IN_PROGRESS

    await db.commit()
    await db.refresh(student)

    # 4. 记录登录操作日志
    login_log = OperationLog(
        student_id=student.id,
        operation_type="login",
        description="考生登录成功",
        level=OperationLevel.NORMAL,
    )
    db.add(login_log)
    await db.commit()

    # 5. 生成 Token
    student_token = create_student_token(student.id, exam.id)

    # 6. 获取题目列表
    result = await db.execute(
        select(Problem).where(Problem.exam_id == exam.id).order_by(Problem.order_num)
    )
    problems = result.scalars().all()

    # 7. 构建响应
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
        AuthProblemBrief(
            id=p.id,
            title=p.title,
            order_num=p.order_num,
        )
        for p in problems
    ]

    return ResponseModel(
        code=200,
        message="登录成功",
        data=LoginResponse(
            student_token=student_token,
            exam_info=exam_info,
            problems=problem_list,
        ),
    )


@router.post(
    "/student/fullscreen",
    response_model=ResponseModel[FullscreenResponse],
    summary="全屏状态上报",
    description="考生登录后上报全屏状态，成功则返回 WebSocket 连接信息。",
)
async def report_fullscreen(
    request: FullscreenRequest,
    student: Student = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[FullscreenResponse]:
    """上报全屏状态."""
    if not request.success:
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

    import secrets

    websocket_token = secrets.token_urlsafe(32)
    student.websocket_token = websocket_token
    student.is_fullscreen = True

    await db.commit()

    ws_url = f"{settings.ws_scheme}://{settings.ws_host}:{settings.ws_port}{settings.ws_path}?token={websocket_token}"

    return ResponseModel(
        code=200,
        message="全屏状态上报成功",
        data=FullscreenResponse(
            websocket_token=websocket_token,
            ws_url=ws_url,
        ),
    )


@router.post(
    "/admin/login",
    response_model=ResponseModel[AdminLoginResponse],
    summary="管理员登录",
    description="管理员使用账号和密码登录系统。",
)
async def admin_login(
    request: AdminLoginRequest,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[AdminLoginResponse]:
    """管理员登录."""
    result = await db.execute(select(Admin).where(Admin.username == request.username))
    admin = result.scalar_one_or_none()

    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误",
        )

    if not verify_password(request.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误",
        )

    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已停用",
        )

    token_payload = {
        "type": "admin",
        "admin_id": admin.id,
        "username": admin.username,
    }
    token = create_access_token(token_payload)

    admin_info = AdminInfo(
        id=admin.id,
        username=admin.username,
        name=admin.name,
        is_active=admin.is_active,
        role=admin.role,
    )

    return ResponseModel(
        code=200,
        message="登录成功",
        data=AdminLoginResponse(
            token=token,
            admin=admin_info,
        ),
    )


@router.post(
    "/admin/verify",
    response_model=ResponseModel[AdminVerifyResponse],
    summary="验证管理员 Token",
    description="验证管理员 Token 的有效性。",
)
async def verify_admin(
    authorization: Annotated[
        str, Header(..., description="Bearer Token, 格式: Bearer <admin_token>")
    ],
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[AdminVerifyResponse]:
    """验证管理员 Token."""

    if not authorization.startswith("Bearer "):
        return ResponseModel(
            code=401,
            message="无效的 Authorization 格式，应为 'Bearer <token>'",
            data=AdminVerifyResponse(valid=False, admin_info=None),
        )

    token = authorization[7:]
    payload = decode_token(token)
    if payload is None:
        return ResponseModel(
            code=401,
            message="Token 无效或已过期",
            data=AdminVerifyResponse(valid=False, admin_info=None),
        )

    token_type = payload.get("type")
    if token_type != "admin":
        return ResponseModel(
            code=401,
            message="无效的 Token 类型",
            data=AdminVerifyResponse(valid=False, admin_info=None),
        )

    admin_id = payload.get("admin_id")
    if admin_id is None:
        return ResponseModel(
            code=401,
            message="无效的 Token 载荷",
            data=AdminVerifyResponse(valid=False, admin_info=None),
        )

    result = await db.execute(select(Admin).where(Admin.id == admin_id))
    admin = result.scalar_one_or_none()

    if admin is None:
        return ResponseModel(
            code=401,
            message="管理员不存在",
            data=AdminVerifyResponse(valid=False, admin_info=None),
        )

    if not admin.is_active:
        return ResponseModel(
            code=403,
            message="管理员账号已停用",
            data=AdminVerifyResponse(valid=False, admin_info=None),
        )

    admin_info = {
        "id": admin.id,
        "username": admin.username,
        "name": admin.name,
        "is_active": admin.is_active,
        "role": admin.role,
    }

    return ResponseModel(
        code=200,
        message="Token 有效",
        data=AdminVerifyResponse(valid=True, admin_info=admin_info),
    )
