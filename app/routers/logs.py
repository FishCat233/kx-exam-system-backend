"""日志相关路由."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AdminToken, OperationLevel, OperationLog, Student
from app.schemas import LogCreateRequest, LogListItem, LogResponse, ResponseModel
from app.utils.auth import require_admin
from app.utils.student_auth import decode_student_token

router = APIRouter(prefix="/api", tags=["日志"])


@router.post(
    "/logs",
    response_model=ResponseModel[LogResponse],
    summary="上报操作日志",
    description="考生上报操作日志，自动记录 IP 地址和 User-Agent。",
    response_description="返回创建的日志信息",
)
async def create_log(
    request: LogCreateRequest,
    http_request: Request,
    authorization: Annotated[
        str,
        Header(..., description="Bearer Token, 格式: Bearer <student_token>"),
    ],
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[LogResponse]:
    """上报操作日志.

    Args:
        request: 日志创建请求
        http_request: HTTP 请求对象
        authorization: Authorization 请求头
        db: 数据库会话

    Returns:
        包含创建的日志信息的响应

    Raises:
        HTTPException: 401 - Token 无效
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

    # 3. 获取 IP 地址和 User-Agent
    ip_address = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")

    # 4. 创建日志记录
    log = OperationLog(
        student_id=student_id,
        operation_type=request.operation_type,
        description=request.description,
        level=request.level,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    db.add(log)
    await db.commit()
    await db.refresh(log)

    return ResponseModel(
        code=200,
        message="日志记录成功",
        data=LogResponse.model_validate(log),
    )


@router.get(
    "/admin/exams/{exam_id}/logs",
    response_model=ResponseModel[list[LogListItem]],
    summary="获取考试日志",
    description="获取指定考试的操作日志，支持按级别过滤，需要管理员权限。",
    response_description="返回日志列表",
)
async def list_logs(
    exam_id: int,
    level: OperationLevel | None = None,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    _: AdminToken = Depends(require_admin),
) -> ResponseModel[list[LogListItem]]:
    """获取考试日志.

    Args:
        exam_id: 考试 ID
        level: 日志级别过滤
        limit: 返回数量限制
        db: 数据库会话
        _: 管理员权限验证

    Returns:
        包含日志列表的响应
    """
    # 构建查询
    query = (
        select(OperationLog, Student)
        .join(Student, OperationLog.student_id == Student.id)
        .where(Student.exam_id == exam_id)
    )

    # 应用级别过滤
    if level is not None:
        query = query.where(OperationLog.level == level)

    # 按时间倒序排序并限制数量
    query = query.order_by(OperationLog.created_at.desc()).limit(limit)

    result = await db.execute(query)
    logs = result.all()

    log_list = [
        LogListItem(
            id=log.OperationLog.id,
            student_name=log.Student.name,
            student_id=log.Student.student_id,
            operation_type=log.OperationLog.operation_type,
            description=log.OperationLog.description,
            level=log.OperationLog.level,
            created_at=log.OperationLog.created_at,
        )
        for log in logs
    ]

    return ResponseModel(
        code=200,
        message="获取成功",
        data=log_list,
    )
