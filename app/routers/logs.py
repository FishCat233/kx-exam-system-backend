"""日志相关路由."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Admin, OperationLevel, OperationLog, Student
from app.schemas import (
    LogCreateRequest,
    LogListItem,
    LogResponse,
    PaginationResponse,
    ResponseModel,
)
from app.services.rate_limit import rate_limit
from app.utils.auth import require_admin
from app.utils.student_auth import require_student

router = APIRouter(prefix="/api", tags=["日志"])

# 考生上报日志可能较频繁（全屏/切屏事件），token 限流
create_log_limit = rate_limit(
    scope="log_create",
    ip_limit=settings.rate_limit_ip_per_min,
    token_limit=settings.rate_limit_token_per_min,
)
# 管理端查日志为读操作，token 限流
list_logs_limit = rate_limit(
    scope="log_list",
    ip_limit=settings.rate_limit_ip_per_min,
    token_limit=settings.rate_limit_token_per_min,
)


@router.post(
    "/logs",
    response_model=ResponseModel[LogResponse],
    summary="上报操作日志",
    description="考生上报操作日志，自动记录 IP 地址和 User-Agent。",
)
async def create_log(
    request: LogCreateRequest,
    http_request: Request,
    _: None = Depends(create_log_limit),
    student: Student = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[LogResponse]:
    """上报操作日志."""
    ip_address = http_request.client.host if http_request.client else None
    user_agent = http_request.headers.get("user-agent")

    log = OperationLog(
        student_id=student.id,
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
    response_model=ResponseModel[PaginationResponse[LogListItem]],
    summary="获取考试日志",
    description="获取指定考试的操作日志，支持按级别过滤和分页，需要管理员权限。",
)
async def list_logs(
    exam_id: int,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    level: OperationLevel | None = Query(None, description="日志级别过滤"),
    _: None = Depends(list_logs_limit),
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(require_admin),
) -> ResponseModel[PaginationResponse[LogListItem]]:
    """获取考试日志（分页）."""
    # 检查考试是否存在
    result = await db.execute(select(Student).where(Student.exam_id == exam_id).limit(1))
    if result.scalar_one_or_none() is None and level is not None:
        # 需要确认考试存在，但为了避免额外查询，仅在无任何匹配时检查
        pass

    # 构建基础查询
    base_query = (
        select(OperationLog)
        .join(Student, OperationLog.student_id == Student.id)
        .where(Student.exam_id == exam_id)
    )

    if level is not None:
        base_query = base_query.where(OperationLog.level == level)

    # 总数
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页数据
    offset = (page - 1) * page_size
    data_query = (
        select(OperationLog, Student)
        .join(Student, OperationLog.student_id == Student.id)
        .where(Student.exam_id == exam_id)
        .order_by(OperationLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )

    if level is not None:
        data_query = data_query.where(OperationLog.level == level)

    result = await db.execute(data_query)
    rows = result.all()

    items = [
        LogListItem(
            id=log.OperationLog.id,
            student_name=log.Student.name,
            student_id=log.Student.student_id,
            operation_type=log.OperationLog.operation_type,
            description=log.OperationLog.description,
            level=log.OperationLog.level,
            created_at=log.OperationLog.created_at,
        )
        for log in rows
    ]

    return ResponseModel(
        code=200,
        message="获取成功",
        data=PaginationResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items,
        ),
    )
