"""考试相关路由."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Admin, Exam, ExamStatus
from app.schemas import (
    ExamCreate,
    ExamDetailResponse,
    ExamListResponse,
    ExamResponse,
    ExamUpdate,
    ResponseModel,
)
from app.utils.auth import require_exam_management

router = APIRouter(prefix="/api/exams", tags=["考试"])


def calculate_duration_minutes(start_time: datetime, end_time: datetime) -> int:
    """根据开始和结束时间计算考试时长（分钟）."""

    return int((end_time - start_time).total_seconds() // 60)


@router.get("", response_model=ResponseModel[list[ExamListResponse]])
async def list_exams(
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[list[ExamListResponse]]:
    """获取考试列表.

    返回所有考试的列表。
    """
    result = await db.execute(select(Exam).order_by(Exam.created_at.desc()))
    exams = result.scalars().all()

    exam_list = [ExamListResponse.model_validate(exam) for exam in exams]

    return ResponseModel(data=exam_list)


@router.get("/{exam_id}", response_model=ResponseModel[ExamDetailResponse])
async def get_exam(
    exam_id: int,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_exam_management),
) -> ResponseModel[ExamDetailResponse]:
    """获取考试详情.

    返回指定考试的详细信息，包括关联的题目列表。
    """
    result = await db.execute(
        select(Exam).where(Exam.id == exam_id).options(selectinload(Exam.problems))
    )
    exam = result.scalar_one_or_none()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    # 手动构建响应数据，包含 problems
    problems_data = []
    for problem in exam.problems:
        from app.routers.problems import parse_options_json

        problems_data.append(
            {
                "id": problem.id,
                "exam_id": problem.exam_id,
                "title": problem.title,
                "content": problem.content,
                "type": problem.type,
                "options": parse_options_json(problem.options),
                "order_num": problem.order_num,
                "created_at": problem.created_at.isoformat() if problem.created_at else None,
                "updated_at": problem.updated_at.isoformat() if problem.updated_at else None,
            }
        )

    exam_data = ExamDetailResponse(
        id=exam.id,
        name=exam.name,
        subject=exam.subject,
        duration=exam.duration,
        start_time=exam.start_time,
        end_time=exam.end_time,
        actual_start_time=exam.actual_start_time,
        actual_end_time=exam.actual_end_time,
        status=exam.status,
        pledge_content=exam.pledge_content,
        created_at=exam.created_at,
        updated_at=exam.updated_at,
        problems=problems_data,
    )

    return ResponseModel(data=exam_data)


@router.post("", response_model=ResponseModel[dict])
async def create_exam(
    request: ExamCreate,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_exam_management),
) -> ResponseModel[dict]:
    """创建考试.

    需要高权限管理员权限。创建新的考试记录。
    """
    # 检查时间范围有效性
    if request.end_time <= request.start_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="End time must be after start time",
        )

    exam = Exam(
        name=request.name,
        subject=request.subject,
        duration=calculate_duration_minutes(request.start_time, request.end_time),
        start_time=request.start_time,
        end_time=request.end_time,
        pledge_content=request.pledge_content,
        status=ExamStatus.NOT_STARTED,
    )

    db.add(exam)
    await db.commit()
    await db.refresh(exam)

    return ResponseModel(data={"exam_id": exam.id})


@router.put("/{exam_id}", response_model=ResponseModel[ExamResponse])
async def update_exam(
    exam_id: int,
    request: ExamUpdate,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_exam_management),
) -> ResponseModel[ExamResponse]:
    """更新考试.

    需要高权限管理员权限。
    - 未开始的考试：可以修改所有字段
    - 进行中的考试：只能修改状态（用于开启/结束考试）和承诺书
    - 已结束的考试：只能修改承诺书
    """
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    # 获取需要更新的字段
    update_data = request.model_dump(exclude_unset=True)

    # 如果尝试更新除 status 和 pledge_content 之外的字段
    # 而考试已经开始或结束，则拒绝
    if exam.status != ExamStatus.NOT_STARTED:
        editable_fields = {"status", "pledge_content"}
        other_fields = set(update_data.keys()) - editable_fields
        if other_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update exam details after it has started or ended. Only status and pledge_content can be modified.",
            )

    # 检查时间范围有效性（仅当时间字段被更新时）
    if "start_time" in update_data or "end_time" in update_data:
        new_start_time = update_data.get("start_time", exam.start_time)
        new_end_time = update_data.get("end_time", exam.end_time)
        if new_end_time <= new_start_time:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="End time must be after start time",
            )
        update_data["duration"] = calculate_duration_minutes(new_start_time, new_end_time)

    # 处理状态变更
    if "status" in update_data:
        new_status = update_data["status"]
        # 当状态变为进行中时，设置实际开始时间
        if new_status == ExamStatus.ONGOING and exam.actual_start_time is None:
            exam.actual_start_time = datetime.now(UTC)
        # 当状态变为结束时，设置实际结束时间
        elif new_status == ExamStatus.ENDED and exam.actual_end_time is None:
            exam.actual_end_time = datetime.now(UTC)

    # 更新字段
    for field, value in update_data.items():
        setattr(exam, field, value)

    await db.commit()
    await db.refresh(exam)

    return ResponseModel(data=ExamResponse.model_validate(exam))


@router.delete("/{exam_id}", response_model=ResponseModel[dict])
async def delete_exam(
    exam_id: int,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_exam_management),
) -> ResponseModel[dict]:
    """删除考试.

    需要高权限管理员权限。只能删除未开始的考试，会级联删除关联的题目。
    """
    result = await db.execute(
        select(Exam).where(Exam.id == exam_id).options(selectinload(Exam.problems))
    )
    exam = result.scalar_one_or_none()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    # 检查考试状态，已开始或已结束的考试不能删除
    if exam.status != ExamStatus.NOT_STARTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete exam that has already started or ended",
        )

    # 先删除关联的题目
    for problem in exam.problems:
        await db.delete(problem)

    await db.delete(exam)
    await db.commit()

    return ResponseModel(data={"message": "Exam deleted successfully"})
