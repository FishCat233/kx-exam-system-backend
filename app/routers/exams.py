"""考试相关路由."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Exam, ExamStatus, Problem
from app.schemas import (
    ExamCreate,
    ExamDetailResponse,
    ExamListResponse,
    ExamResponse,
    ExamUpdate,
    ProblemResponse,
    ResponseModel,
)
from app.utils.auth import require_admin

router = APIRouter(prefix="/api/exams", tags=["考试"])


@router.get("", response_model=ResponseModel[list[ExamListResponse]])
async def list_exams(
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[list[ExamListResponse]]:
    """获取考试列表.

    返回所有考试的列表，不包含承诺书内容。
    """
    result = await db.execute(select(Exam).order_by(Exam.created_at.desc()))
    exams = result.scalars().all()

    # 使用 from_orm 方式序列化
    exam_list = []
    for exam in exams:
        exam_list.append(
            ExamListResponse(
                id=exam.id,
                name=exam.name,
                subject=exam.subject,
                duration=exam.duration,
                start_time=exam.start_time,
                end_time=exam.end_time,
                status=exam.status,
            )
        )

    return ResponseModel(data=exam_list)


@router.get("/{exam_id}", response_model=ResponseModel[ExamDetailResponse])
async def get_exam(
    exam_id: int,
    db: AsyncSession = Depends(get_db),
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
        problems_data.append(
            {
                "id": problem.id,
                "exam_id": problem.exam_id,
                "title": problem.title,
                "content": problem.content,
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
    _: bool = Depends(require_admin),
) -> ResponseModel[dict]:
    """创建考试.

    需要管理员权限。创建新的考试记录。
    """
    # 检查时间范围有效性
    if request.end_time <= request.start_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="End time must be after start time",
        )

    exam = Exam(
        name=request.name,
        subject=request.subject,
        duration=request.duration,
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
    _: bool = Depends(require_admin),
) -> ResponseModel[ExamResponse]:
    """更新考试.

    需要管理员权限。只能更新未开始的考试。
    """
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    # 检查考试状态，已开始或已结束的考试不能修改
    if exam.status != ExamStatus.NOT_STARTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update exam that has already started or ended",
        )

    # 检查时间范围有效性
    new_start_time = request.start_time or exam.start_time
    new_end_time = request.end_time or exam.end_time
    if new_end_time <= new_start_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="End time must be after start time",
        )

    # 更新字段
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(exam, field, value)

    await db.commit()
    await db.refresh(exam)

    # 手动构建响应
    exam_data = ExamResponse(
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
    )

    return ResponseModel(data=exam_data)


@router.delete("/{exam_id}", response_model=ResponseModel[dict])
async def delete_exam(
    exam_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_admin),
) -> ResponseModel[dict]:
    """删除考试.

    需要管理员权限。只能删除未开始的考试，会级联删除关联的题目。
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


@router.get("/{exam_id}/problems", response_model=ResponseModel[list[ProblemResponse]])
async def get_exam_problems(
    exam_id: int,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[list[ProblemResponse]]:
    """获取考试题目列表.

    返回指定考试的所有题目，按 order_num 排序。
    """
    # 检查考试是否存在
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    # 获取题目列表
    result = await db.execute(
        select(Problem).where(Problem.exam_id == exam_id).order_by(Problem.order_num)
    )
    problems = result.scalars().all()

    # 手动构建响应
    problems_data = []
    for problem in problems:
        problems_data.append(
            ProblemResponse(
                id=problem.id,
                exam_id=problem.exam_id,
                title=problem.title,
                content=problem.content,
                order_num=problem.order_num,
                created_at=problem.created_at,
                updated_at=problem.updated_at,
            )
        )

    return ResponseModel(data=problems_data)
