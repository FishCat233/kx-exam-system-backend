"""管理员相关路由."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    AdminToken,
    Exam,
    OperationLevel,
    OperationLog,
    Student,
    StudentCode,
    SubmitStatus,
)
from app.schemas import (
    AdminTokenCreate,
    AdminTokenListItem,
    AdminTokenResponse,
    AdminTokenUpdate,
    ResponseModel,
    StudentCreate,
    StudentDetail,
    StudentListItem,
)
from app.utils.auth import create_access_token, require_admin, require_super_admin
from app.utils.student_auth import generate_login_code

router = APIRouter(prefix="/api/admin", tags=["管理"])


@router.get(
    "/exams/{exam_id}/students",
    response_model=ResponseModel[list[StudentListItem]],
    summary="获取考生列表",
    description="获取指定考试的所有考生列表，需要管理员权限。",
    response_description="返回考生列表",
)
async def list_students(
    exam_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminToken = Depends(require_admin),
) -> ResponseModel[list[StudentListItem]]:
    """获取考生列表.

    Args:
        exam_id: 考试 ID
        db: 数据库会话
        _: 管理员权限验证

    Returns:
        包含考生列表的响应
    """
    # 检查考试是否存在
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考试不存在",
        )

    # 查询考生列表
    result = await db.execute(
        select(Student).where(Student.exam_id == exam_id).order_by(Student.student_id)
    )
    students = result.scalars().all()

    student_list = [
        StudentListItem(
            id=s.id,
            student_id=s.student_id,
            name=s.name,
            login_code=s.login_code,
            login_time=s.login_time,
            submit_time=s.submit_time,
            submit_status=s.submit_status,
        )
        for s in students
    ]

    return ResponseModel(
        code=200,
        message="获取成功",
        data=student_list,
    )


@router.post(
    "/exams/{exam_id}/students",
    response_model=ResponseModel[dict],
    summary="批量导入考生",
    description="批量导入考生到指定考试，自动生成登录码，需要管理员权限。",
    response_description="返回导入结果",
)
async def import_students(
    exam_id: int,
    students: list[StudentCreate],
    db: AsyncSession = Depends(get_db),
    _: AdminToken = Depends(require_admin),
) -> ResponseModel[dict]:
    """批量导入考生.

    Args:
        exam_id: 考试 ID
        students: 考生信息列表
        db: 数据库会话
        _: 管理员权限验证

    Returns:
        包含导入结果的响应
    """
    # 检查考试是否存在
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考试不存在",
        )

    # 检查是否有重复学号
    student_ids = [s.student_id for s in students]
    if len(student_ids) != len(set(student_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="导入列表中存在重复的学号",
        )

    # 检查学号是否已存在
    result = await db.execute(
        select(Student).where(
            Student.exam_id == exam_id,
            Student.student_id.in_(student_ids),
        )
    )
    existing_students = result.scalars().all()

    if existing_students:
        existing_ids = [s.student_id for s in existing_students]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"以下学号已存在: {', '.join(existing_ids)}",
        )

    # 生成登录码并创建考生
    imported_count = 0
    for student_data in students:
        # 生成唯一登录码
        while True:
            login_code = generate_login_code()
            result = await db.execute(select(Student).where(Student.login_code == login_code))
            if result.scalar_one_or_none() is None:
                break

        student = Student(
            exam_id=exam_id,
            student_id=student_data.student_id,
            name=student_data.name,
            login_code=login_code,
            login_code_used=False,
            submit_status=SubmitStatus.NOT_STARTED,
        )
        db.add(student)
        imported_count += 1

    await db.commit()

    return ResponseModel(
        code=200,
        message="导入成功",
        data={"imported_count": imported_count},
    )


@router.get(
    "/students/{student_id}",
    response_model=ResponseModel[StudentDetail],
    summary="获取考生详情",
    description="获取考生的详细信息和操作记录，需要管理员权限。",
    response_description="返回考生详情",
)
async def get_student_detail(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminToken = Depends(require_admin),
) -> ResponseModel[StudentDetail]:
    """获取考生详情.

    Args:
        student_id: 考生 ID
        db: 数据库会话
        _: 管理员权限验证

    Returns:
        包含考生详情的响应

    Raises:
        HTTPException: 404 - 考生不存在
    """
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考生不存在",
        )

    # 查询操作记录
    result = await db.execute(
        select(OperationLog)
        .where(OperationLog.student_id == student_id)
        .order_by(OperationLog.created_at.desc())
    )
    logs = result.scalars().all()

    # 查询代码记录
    result = await db.execute(
        select(StudentCode)
        .where(StudentCode.student_id == student_id)
        .order_by(StudentCode.saved_at.desc())
    )
    codes = result.scalars().all()

    # 构建详情响应
    student_detail = {
        "id": student.id,
        "exam_id": student.exam_id,
        "student_id": student.student_id,
        "name": student.name,
        "login_code": student.login_code,
        "login_code_used": student.login_code_used,
        "login_time": student.login_time,
        "submit_time": student.submit_time,
        "submit_status": student.submit_status,
        "is_fullscreen": student.is_fullscreen,
        "created_at": student.created_at,
        "updated_at": student.updated_at,
        "logs": [
            {
                "id": log.id,
                "operation_type": log.operation_type,
                "description": log.description,
                "level": log.level,
                "created_at": log.created_at,
            }
            for log in logs
        ],
        "codes": [
            {
                "id": code.id,
                "problem_id": code.problem_id,
                "saved_at": code.saved_at,
            }
            for code in codes
        ],
    }

    return ResponseModel(
        code=200,
        message="获取成功",
        data=StudentDetail(**student_detail),
    )


@router.post(
    "/students/{student_id}/force-submit",
    response_model=ResponseModel[dict],
    summary="强制收卷",
    description="强制结束考生的考试，需要管理员权限。",
    response_description="返回强制收卷结果",
)
async def force_submit(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminToken = Depends(require_admin),
) -> ResponseModel[dict]:
    """强制收卷.

    Args:
        student_id: 考生 ID
        db: 数据库会话
        _: 管理员权限验证

    Returns:
        包含强制收卷结果的响应

    Raises:
        HTTPException: 404 - 考生不存在
    """
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考生不存在",
        )

    # 更新考生状态
    student.submit_status = SubmitStatus.FORCE_SUBMITTED
    student.submit_time = datetime.now(UTC)

    # 记录操作日志
    log = OperationLog(
        student_id=student_id,
        operation_type="force_submit",
        description="管理员强制收卷",
        level=OperationLevel.NORMAL,
    )
    db.add(log)

    await db.commit()
    await db.refresh(student)

    return ResponseModel(
        code=200,
        message="强制收卷成功",
        data={
            "student_id": student_id,
            "submit_time": student.submit_time,
            "status": student.submit_status,
        },
    )


@router.delete(
    "/students/{student_id}",
    response_model=ResponseModel[dict],
    summary="删除考生",
    description="删除考生及其相关数据（代码、日志），需要管理员权限。",
    response_description="返回删除结果",
)
async def delete_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminToken = Depends(require_admin),
) -> ResponseModel[dict]:
    """删除考生.

    Args:
        student_id: 考生 ID
        db: 数据库会话
        _: 管理员权限验证

    Returns:
        包含删除结果的响应

    Raises:
        HTTPException: 404 - 考生不存在
    """
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考生不存在",
        )

    # 删除相关数据
    await db.execute(select(StudentCode).where(StudentCode.student_id == student_id))
    await db.execute(select(OperationLog).where(OperationLog.student_id == student_id))

    # 删除考生
    await db.delete(student)
    await db.commit()

    return ResponseModel(
        code=200,
        message="删除成功",
        data={"id": student_id},
    )


@router.get(
    "/dashboard/{exam_id}",
    response_model=ResponseModel[dict],
    summary="获取仪表盘数据",
    description="获取考试的仪表盘数据，包括状态、倒计时、交卷人数等，需要管理员权限。",
    response_description="返回仪表盘数据",
)
async def get_dashboard(
    exam_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminToken = Depends(require_admin),
) -> ResponseModel[dict]:
    """获取仪表盘数据.

    Args:
        exam_id: 考试 ID
        db: 数据库会话
        _: 管理员权限验证

    Returns:
        包含仪表盘数据的响应
    """
    # 检查考试是否存在
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考试不存在",
        )

    now = datetime.now(UTC)

    # 确保考试时间是带时区的
    start_time = exam.start_time
    end_time = exam.end_time
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=UTC)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=UTC)

    # 计算考试状态
    if now < start_time:
        exam_status = "not_started"
        countdown = int((start_time - now).total_seconds())
    elif now < end_time:
        exam_status = "in_progress"
        countdown = int((end_time - now).total_seconds())
    else:
        exam_status = "ended"
        countdown = 0

    # 统计交卷人数
    result = await db.execute(
        select(func.count()).where(
            Student.exam_id == exam_id,
            Student.submit_status.in_([SubmitStatus.SUBMITTED, SubmitStatus.FORCE_SUBMITTED]),
        )
    )
    submit_count = result.scalar() or 0

    # 统计总人数
    result = await db.execute(select(func.count()).where(Student.exam_id == exam_id))
    total_count = result.scalar() or 0

    # 获取最近异常记录（最近 10 条 warning 或 critical 级别）
    result = await db.execute(
        select(OperationLog, Student)
        .join(Student, OperationLog.student_id == Student.id)
        .where(
            Student.exam_id == exam_id,
            OperationLog.level.in_([OperationLevel.WARNING, OperationLevel.CRITICAL]),
        )
        .order_by(OperationLog.created_at.desc())
        .limit(10)
    )
    recent_logs = result.all()

    recent_logs_data = [
        {
            "id": log.OperationLog.id,
            "student_name": log.Student.name,
            "student_id": log.Student.student_id,
            "operation_type": log.OperationLog.operation_type,
            "description": log.OperationLog.description,
            "level": log.OperationLog.level,
            "created_at": log.OperationLog.created_at,
        }
        for log in recent_logs
    ]

    dashboard_data = {
        "exam_status": exam_status,
        "countdown": countdown,
        "submit_count": submit_count,
        "total_count": total_count,
        "start_time": exam.start_time,
        "end_time": exam.end_time,
        "actual_start_time": exam.actual_start_time,
        "actual_end_time": exam.actual_end_time,
        "recent_logs": recent_logs_data,
    }

    return ResponseModel(
        code=200,
        message="获取成功",
        data=dashboard_data,
    )


@router.get(
    "/exams/{exam_id}/export",
    summary="导出考试数据",
    description="导出考试的所有考生代码数据，需要管理员权限。",
    response_description="返回 ZIP 文件",
)
async def export_exam(
    exam_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminToken = Depends(require_admin),
):
    """导出考试数据.

    Args:
        exam_id: 考试 ID
        db: 数据库会话
        _: 管理员权限验证

    Returns:
        ZIP 文件流

    Raises:
        HTTPException: 404 - 考试不存在
    """
    # TODO: 实现导出考试数据
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


# ==================== 管理员 Token 管理 ====================


@router.post(
    "/tokens",
    response_model=ResponseModel[AdminTokenResponse],
    summary="创建管理员 Token",
    description="创建一个新的管理员 Token，需要超级管理员权限。",
    response_description="返回创建的管理员 Token 完整信息",
)
async def create_admin_token(
    data: AdminTokenCreate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_super_admin),
) -> ResponseModel[AdminTokenResponse]:
    """创建管理员 Token.

    Args:
        data: 创建 Token 的请求数据
        db: 数据库会话
        _: 超级管理员权限验证

    Returns:
        包含新创建的管理员 Token 的响应
    """
    # 创建 JWT Token payload
    token_payload = {
        "type": "admin",
        "admin_id": None,  # 将在保存到数据库后更新
    }

    # 设置过期时间
    expires_delta = None
    if data.expires_at:
        expires_delta = data.expires_at - datetime.now(UTC)

    # 生成 JWT Token
    jwt_token = create_access_token(token_payload, expires_delta=expires_delta)

    # 创建数据库记录
    admin_token = AdminToken(
        token=jwt_token,
        name=data.name,
        is_active=True,
        expires_at=data.expires_at,
    )

    db.add(admin_token)
    await db.commit()
    await db.refresh(admin_token)

    return ResponseModel(
        code=200,
        message="创建成功",
        data=admin_token,
    )


@router.get(
    "/tokens",
    response_model=ResponseModel[list[AdminTokenListItem]],
    summary="获取管理员 Token 列表",
    description="获取所有管理员 Token 列表，Token 字段只显示前 10 位，需要超级管理员权限。",
    response_description="返回管理员 Token 列表",
)
async def list_admin_tokens(
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_super_admin),
) -> ResponseModel[list[AdminTokenListItem]]:
    """获取管理员 Token 列表.

    Args:
        db: 数据库会话
        _: 超级管理员权限验证

    Returns:
        包含管理员 Token 列表的响应
    """
    result = await db.execute(select(AdminToken).order_by(AdminToken.created_at.desc()))
    tokens = result.scalars().all()

    # 处理 token 字段，只显示前 10 位
    token_list = []
    for token in tokens:
        token_dict = {
            "id": token.id,
            "name": token.name,
            "is_active": token.is_active,
            "expires_at": token.expires_at,
            "created_at": token.created_at,
            "updated_at": token.updated_at,
            "token": token.token[:10] + "..." if len(token.token) > 10 else token.token,
        }
        token_list.append(AdminTokenListItem(**token_dict))

    return ResponseModel(
        code=200,
        message="获取成功",
        data=token_list,
    )


@router.put(
    "/tokens/{token_id}",
    response_model=ResponseModel[AdminTokenResponse],
    summary="修改管理员 Token",
    description="根据 ID 修改管理员 Token 信息，需要超级管理员权限。",
    response_description="返回更新后的管理员 Token 信息",
)
async def update_admin_token(
    token_id: int,
    data: AdminTokenUpdate,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_super_admin),
) -> ResponseModel[AdminTokenResponse]:
    """修改管理员 Token.

    Args:
        token_id: Token ID
        data: 更新数据
        db: 数据库会话
        _: 超级管理员权限验证

    Returns:
        包含更新后的管理员 Token 的响应

    Raises:
        HTTPException: Token 不存在时返回 404
    """
    result = await db.execute(select(AdminToken).where(AdminToken.id == token_id))
    admin_token = result.scalar_one_or_none()

    if not admin_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="管理员 Token 不存在",
        )

    # 更新非 None 的字段
    if data.name is not None:
        admin_token.name = data.name
    if data.expires_at is not None:
        admin_token.expires_at = data.expires_at
    if data.is_active is not None:
        admin_token.is_active = data.is_active

    admin_token.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(admin_token)

    return ResponseModel(
        code=200,
        message="更新成功",
        data=admin_token,
    )


@router.delete(
    "/tokens/{token_id}",
    response_model=ResponseModel[dict],
    summary="删除管理员 Token",
    description="根据 ID 删除管理员 Token，需要超级管理员权限。",
    response_description="返回删除结果",
)
async def delete_admin_token(
    token_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_super_admin),
) -> ResponseModel[dict]:
    """删除管理员 Token.

    Args:
        token_id: Token ID
        db: 数据库会话
        _: 超级管理员权限验证

    Returns:
        包含删除结果的响应

    Raises:
        HTTPException: Token 不存在时返回 404
    """
    result = await db.execute(select(AdminToken).where(AdminToken.id == token_id))
    admin_token = result.scalar_one_or_none()

    if not admin_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="管理员 Token 不存在",
        )

    await db.delete(admin_token)
    await db.commit()

    return ResponseModel(
        code=200,
        message="删除成功",
        data={"id": token_id},
    )


@router.post(
    "/tokens/{token_id}/deactivate",
    response_model=ResponseModel[dict],
    summary="停用管理员 Token",
    description="根据 ID 停用管理员 Token（设置 is_active=False），需要超级管理员权限。",
    response_description="返回停用结果",
)
async def deactivate_admin_token(
    token_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_super_admin),
) -> ResponseModel[dict]:
    """停用管理员 Token.

    Args:
        token_id: Token ID
        db: 数据库会话
        _: 超级管理员权限验证

    Returns:
        包含停用结果的响应

    Raises:
        HTTPException: Token 不存在时返回 404
    """
    result = await db.execute(select(AdminToken).where(AdminToken.id == token_id))
    admin_token = result.scalar_one_or_none()

    if not admin_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="管理员 Token 不存在",
        )

    admin_token.is_active = False
    admin_token.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(admin_token)

    return ResponseModel(
        code=200,
        message="停用成功",
        data={"id": token_id, "is_active": False},
    )
