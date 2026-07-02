"""管理员相关路由."""

import io
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import (
    Admin,
    Exam,
    OperationLevel,
    OperationLog,
    Problem,
    Student,
    StudentCode,
    SubmitStatus,
)
from app.schemas import (
    AdminCreate,
    AdminListItem,
    AdminResponse,
    AdminUpdate,
    ChangePasswordRequest,
    ForceChangePasswordRequest,
    ResponseModel,
    StudentDetail,
    StudentImportRequest,
    StudentListItem,
)
from app.services.websocket import ws_manager
from app.utils.auth import (
    get_password_hash,
    require_admin,
    require_admin_management,
    require_student_management,
    verify_password,
)
from app.utils.export import generate_exam_export
from app.utils.student_auth import generate_login_code

router = APIRouter(prefix="/api/admin", tags=["管理"])


def get_dashboard_reference_time(exam_time: datetime) -> datetime:
    """按考试时间字段的时区信息生成可比较的当前时间."""

    if exam_time.tzinfo is None:
        exam_time = exam_time.replace(tzinfo=UTC)

    return datetime.now(exam_time.tzinfo)


def calculate_dashboard_status_and_countdown(
    start_time: datetime, end_time: datetime, exam_status: str | None
) -> tuple[str, int]:
    """兼容本地时间和历史 UTC 时间的仪表盘状态计算."""

    if start_time.tzinfo is not None or end_time.tzinfo is not None:
        now = get_dashboard_reference_time(start_time)
        if now < start_time:
            return "not_started", int((start_time - now).total_seconds())
        if now < end_time:
            return "ongoing", int((end_time - now).total_seconds())
        return "ended", 0

    now_candidates = [datetime.now(), datetime.now(UTC).replace(tzinfo=None)]
    candidate_results: list[tuple[str, int]] = []

    for now in now_candidates:
        if now < start_time:
            candidate_results.append(("not_started", int((start_time - now).total_seconds())))
        elif now < end_time:
            candidate_results.append(("ongoing", int((end_time - now).total_seconds())))
        else:
            candidate_results.append(("ended", 0))

    if exam_status is not None:
        for status, countdown in candidate_results:
            if status == exam_status:
                return status, countdown

    return candidate_results[0]


# ==================== 管理员账号管理（需超级管理员权限）====================


@router.post(
    "/admins",
    response_model=ResponseModel[AdminResponse],
    summary="创建管理员账号",
    description="创建一个新的管理员账号，需要高权限管理员权限。",
    response_description="返回创建的管理员信息",
)
async def create_admin(
    data: AdminCreate,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_admin_management),
) -> ResponseModel[AdminResponse]:
    """创建管理员账号.

    Args:
        data: 创建管理员的请求数据
        db: 数据库会话
        _: 超级管理员权限验证

    Returns:
        包含新创建管理员信息的响应

    Raises:
        HTTPException: 409 - 账号已存在
    """
    # 检查账号是否已存在
    result = await db.execute(select(Admin).where(Admin.username == data.username))
    existing_admin = result.scalar_one_or_none()

    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="管理员账号已存在",
        )

    # 创建新管理员
    admin = Admin(
        username=data.username,
        password_hash=get_password_hash(data.password),
        name=data.name,
        remark=data.remark,
        is_active=True,
    )

    db.add(admin)
    await db.commit()
    await db.refresh(admin)

    return ResponseModel(
        code=200,
        message="创建成功",
        data=AdminResponse.model_validate(admin),
    )


@router.get(
    "/admins",
    response_model=ResponseModel[list[AdminListItem]],
    summary="获取管理员列表",
    description="获取所有管理员账号列表，支持按启用状态筛选，需要高权限管理员权限。",
    response_description="返回管理员列表",
)
async def list_admins(
    is_active: bool | None = Query(None, description="按启用状态筛选"),
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_admin_management),
) -> ResponseModel[list[AdminListItem]]:
    """获取管理员列表.

    Args:
        is_active: 可选的启用状态筛选参数
        db: 数据库会话
        _: 超级管理员权限验证

    Returns:
        包含管理员列表的响应
    """
    query = select(Admin).order_by(Admin.created_at.desc())

    if is_active is not None:
        query = query.where(Admin.is_active == is_active)

    result = await db.execute(query)
    admins = result.scalars().all()

    admin_list = [AdminListItem.model_validate(admin) for admin in admins]

    return ResponseModel(
        code=200,
        message="获取成功",
        data=admin_list,
    )


@router.get(
    "/admins/{admin_id}",
    response_model=ResponseModel[AdminResponse],
    summary="获取管理员详情",
    description="获取指定管理员的详细信息，需要高权限管理员权限。",
    response_description="返回管理员详情",
)
async def get_admin(
    admin_id: int,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_admin_management),
) -> ResponseModel[AdminResponse]:
    """获取管理员详情.

    Args:
        admin_id: 管理员 ID
        db: 数据库会话
        _: 超级管理员权限验证

    Returns:
        包含管理员详情的响应

    Raises:
        HTTPException: 404 - 管理员不存在
    """
    result = await db.execute(select(Admin).where(Admin.id == admin_id))
    admin = result.scalar_one_or_none()

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="管理员不存在",
        )

    return ResponseModel(
        code=200,
        message="获取成功",
        data=AdminResponse.model_validate(admin),
    )


@router.put(
    "/admins/{admin_id}",
    response_model=ResponseModel[AdminResponse],
    summary="修改管理员信息",
    description="修改管理员的信息（名称、备注、启用状态），需要高权限管理员权限。",
    response_description="返回更新后的管理员信息",
)
async def update_admin(
    admin_id: int,
    data: AdminUpdate,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_admin_management),
) -> ResponseModel[AdminResponse]:
    """修改管理员信息.

    Args:
        admin_id: 管理员 ID
        data: 更新数据
        db: 数据库会话
        _: 超级管理员权限验证

    Returns:
        包含更新后管理员信息的响应

    Raises:
        HTTPException: 404 - 管理员不存在
    """
    result = await db.execute(select(Admin).where(Admin.id == admin_id))
    admin = result.scalar_one_or_none()

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="管理员不存在",
        )

    # 更新非 None 的字段
    if data.name is not None:
        admin.name = data.name
    if data.remark is not None:
        admin.remark = data.remark
    if data.is_active is not None:
        admin.is_active = data.is_active

    admin.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(admin)

    return ResponseModel(
        code=200,
        message="更新成功",
        data=AdminResponse.model_validate(admin),
    )


@router.delete(
    "/admins/{admin_id}",
    response_model=ResponseModel[dict],
    summary="删除管理员",
    description="删除管理员账号，需要高权限管理员权限。",
    response_description="返回删除结果",
)
async def delete_admin(
    admin_id: int,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_admin_management),
) -> ResponseModel[dict]:
    """删除管理员.

    Args:
        admin_id: 管理员 ID
        db: 数据库会话
        _: 超级管理员权限验证

    Returns:
        包含删除结果的响应

    Raises:
        HTTPException: 404 - 管理员不存在
    """
    result = await db.execute(select(Admin).where(Admin.id == admin_id))
    admin = result.scalar_one_or_none()

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="管理员不存在",
        )

    await db.delete(admin)
    await db.commit()

    return ResponseModel(
        code=200,
        message="删除成功",
        data={"id": admin_id},
    )


@router.post(
    "/admins/{admin_id}/deactivate",
    response_model=ResponseModel[dict],
    summary="停用管理员",
    description="停用管理员账号，需要高权限管理员权限。",
    response_description="返回停用结果",
)
async def deactivate_admin(
    admin_id: int,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_admin_management),
) -> ResponseModel[dict]:
    """停用管理员.

    Args:
        admin_id: 管理员 ID
        db: 数据库会话
        _: 超级管理员权限验证

    Returns:
        包含停用结果的响应

    Raises:
        HTTPException: 404 - 管理员不存在
    """
    result = await db.execute(select(Admin).where(Admin.id == admin_id))
    admin = result.scalar_one_or_none()

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="管理员不存在",
        )

    admin.is_active = False
    admin.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(admin)

    return ResponseModel(
        code=200,
        message="停用成功",
        data={"id": admin_id, "is_active": False},
    )


@router.post(
    "/admins/{admin_id}/activate",
    response_model=ResponseModel[dict],
    summary="启用管理员",
    description="启用管理员账号，需要高权限管理员权限。",
    response_description="返回启用结果",
)
async def activate_admin(
    admin_id: int,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_admin_management),
) -> ResponseModel[dict]:
    """启用管理员.

    Args:
        admin_id: 管理员 ID
        db: 数据库会话
        _: 超级管理员权限验证

    Returns:
        包含启用结果的响应

    Raises:
        HTTPException: 404 - 管理员不存在
    """
    result = await db.execute(select(Admin).where(Admin.id == admin_id))
    admin = result.scalar_one_or_none()

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="管理员不存在",
        )

    admin.is_active = True
    admin.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(admin)

    return ResponseModel(
        code=200,
        message="启用成功",
        data={"id": admin_id, "is_active": True},
    )


@router.post(
    "/admins/{admin_id}/force-change-password",
    response_model=ResponseModel[dict],
    summary="强制修改密码",
    description="高权限管理员强制修改任何管理员的密码，不需要原密码。",
    response_description="返回修改结果",
)
async def force_change_password(
    admin_id: int,
    data: ForceChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_admin_management),
) -> ResponseModel[dict]:
    """强制修改密码.

    Args:
        admin_id: 管理员 ID
        data: 强制修改密码请求数据
        db: 数据库会话
        _: 超级管理员权限验证

    Returns:
        包含修改结果的响应

    Raises:
        HTTPException: 404 - 管理员不存在
    """
    result = await db.execute(select(Admin).where(Admin.id == admin_id))
    admin = result.scalar_one_or_none()

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="管理员不存在",
        )

    # 更新密码
    admin.password_hash = get_password_hash(data.new_password)
    admin.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(admin)

    return ResponseModel(
        code=200,
        message="密码修改成功",
        data={"id": admin_id},
    )


# ==================== 密码管理（需管理员权限）====================


@router.post(
    "/change-password",
    response_model=ResponseModel[dict],
    summary="修改自己的密码",
    description="管理员修改自己的密码，需要登录权限。",
    response_description="返回修改结果",
)
async def change_password(
    data: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: Admin = Depends(require_admin),
) -> ResponseModel[dict]:
    """修改自己的密码.

    Args:
        data: 修改密码请求数据（含旧密码和新密码）
        db: 数据库会话
        current_admin: 当前登录的管理员

    Returns:
        包含修改结果的响应

    Raises:
        HTTPException: 403 - 旧密码错误
    """
    # 验证旧密码
    if not verify_password(data.old_password, current_admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="原密码错误",
        )

    # 更新密码
    current_admin.password_hash = get_password_hash(data.new_password)
    current_admin.updated_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(current_admin)

    return ResponseModel(
        code=200,
        message="密码修改成功",
        data={"id": current_admin.id},
    )


# ==================== 考生管理（需管理员权限）====================


@router.get(
    "/exams/{exam_id}/students",
    response_model=ResponseModel[list[StudentListItem]],
    summary="获取考生列表",
    description="获取指定考试的所有考生列表，需要高权限管理员权限。",
    response_description="返回考生列表",
)
async def list_students(
    exam_id: int,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_student_management),
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
    description="批量导入考生到指定考试，自动生成登录码，需要高权限管理员权限。",
    response_description="返回导入结果",
)
async def import_students(
    exam_id: int,
    request: StudentImportRequest,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_student_management),
) -> ResponseModel[dict]:
    """批量导入考生.

    Args:
        exam_id: 考试 ID
        request: 批量导入考生请求，包含考生信息列表
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

    students = request.students

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
    description="获取考生的详细信息和操作记录，需要高权限管理员权限。",
    response_description="返回考生详情",
)
async def get_student_detail(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_student_management),
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
    description="强制结束考生的考试，需要高权限管理员权限。",
    response_description="返回强制收卷结果",
)
async def force_submit(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_student_management),
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

    # 通过 WebSocket 发送强制收卷通知
    if ws_manager.is_connected(student_id):
        await ws_manager.send_force_submit(student_id, "管理员强制收卷")

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
    description="删除考生及其相关数据（代码、日志），需要高权限管理员权限。",
    response_description="返回删除结果",
)
async def delete_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_student_management),
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
    result = await db.execute(
        select(Student)
        .where(Student.id == student_id)
        .options(
            selectinload(Student.codes),
            selectinload(Student.logs),
        )
    )
    student = result.scalar_one_or_none()

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考生不存在",
        )

    # 删除相关数据
    for code in student.codes:
        await db.delete(code)
    for log in student.logs:
        await db.delete(log)

    # 删除考生
    await db.delete(student)
    await db.commit()

    return ResponseModel(
        code=200,
        message="删除成功",
        data={"id": student_id},
    )


# ==================== 仪表盘（需管理员权限）====================


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
    _: Admin = Depends(require_admin),
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

    exam_status, countdown = calculate_dashboard_status_and_countdown(
        exam.start_time,
        exam.end_time,
        exam.status.value if exam.status is not None else None,
    )

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


# ==================== 导出（需管理员权限）====================


@router.get(
    "/exams/{exam_id}/export",
    summary="导出考试数据",
    description="导出考试的所有考生代码数据，需要管理员权限。返回 ZIP 文件包含所有考生的代码。",
    response_description="返回 ZIP 文件",
    responses={
        200: {
            "description": "成功返回 ZIP 文件",
            "content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}},
        },
        401: {"description": "未授权，Token 无效或已过期"},
        403: {"description": "禁止访问，账号已被停用"},
        404: {"description": "考试不存在"},
    },
)
async def export_exam(
    exam_id: int,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_admin),
):
    """导出考试数据.

    将考试的所有考生代码打包成 ZIP 文件，目录结构如下：
    - {exam_name}/
      - {student_id}_{student_name}/
        - problem_{order_num}_{title}.c
        - ...
      - export_info.txt (导出信息)

    Args:
        exam_id: 考试 ID
        db: 数据库会话
        _: 管理员权限验证

    Returns:
        FileResponse: ZIP 文件流

    Raises:
        HTTPException: 404 - 考试不存在
    """
    # 查询考试信息
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考试不存在",
        )

    # 查询所有考生
    result = await db.execute(
        select(Student).where(Student.exam_id == exam_id).order_by(Student.student_id)
    )
    students = list(result.scalars().all())

    # 查询所有题目（用于获取题目信息）
    result = await db.execute(
        select(Problem).where(Problem.exam_id == exam_id).order_by(Problem.order_num)
    )
    problems = result.scalars().all()
    problems_map = {p.id: p for p in problems}

    # 查询所有考生的代码
    student_ids = [s.id for s in students]
    student_codes_map: dict[int, list[StudentCode]] = {}
    operation_logs_map: dict[int, list[OperationLog]] = {}

    if student_ids:
        result = await db.execute(
            select(StudentCode).where(StudentCode.student_id.in_(student_ids))
        )
        all_codes = result.scalars().all()

        # 按 student_id 分组
        for code in all_codes:
            if code.student_id not in student_codes_map:
                student_codes_map[code.student_id] = []
            student_codes_map[code.student_id].append(code)

        result = await db.execute(
            select(OperationLog).where(OperationLog.student_id.in_(student_ids))
        )
        all_logs = result.scalars().all()

        for log in all_logs:
            if log.student_id not in operation_logs_map:
                operation_logs_map[log.student_id] = []
            operation_logs_map[log.student_id].append(log)

    # 生成 ZIP 文件
    zip_bytes, zip_filename = generate_exam_export(
        exam=exam,
        students=students,
        student_codes_map=student_codes_map,
        problems_map=problems_map,
        operation_logs_map=operation_logs_map,
    )

    # 返回文件响应
    from urllib.parse import quote

    from fastapi.responses import StreamingResponse

    # 对文件名进行 URL 编码以支持中文
    encoded_filename = quote(zip_filename, safe="")

    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        },
    )


# ==================== 兼容旧接口（已弃用）====================


@router.post(
    "/tokens",
    response_model=ResponseModel[dict],
    summary="创建管理员 Token（已弃用）",
    description="此接口已弃用，请使用 POST /api/admin/admins 创建管理员账号。",
    deprecated=True,
)
async def create_admin_token_deprecated(
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_admin_management),
) -> ResponseModel[dict]:
    """创建管理员 Token（已弃用）."""
    return ResponseModel(
        code=410,
        message="此接口已弃用，请使用 POST /api/admin/admins 创建管理员账号",
        data={},
    )


@router.get(
    "/tokens",
    response_model=ResponseModel[list[dict]],
    summary="获取管理员 Token 列表（已弃用）",
    description="此接口已弃用，请使用 GET /api/admin/admins 获取管理员列表。",
    deprecated=True,
)
async def list_admin_tokens_deprecated(
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_admin_management),
) -> ResponseModel[list[dict]]:
    """获取管理员 Token 列表（已弃用）."""
    return ResponseModel(
        code=410,
        message="此接口已弃用，请使用 GET /api/admin/admins 获取管理员列表",
        data=[],
    )
