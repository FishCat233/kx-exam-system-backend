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

# 状态机：严格单向流转
_VALID_TRANSITIONS: dict[ExamStatus, set[ExamStatus]] = {
    ExamStatus.NOT_STARTED: {ExamStatus.ONGOING},
    ExamStatus.ONGOING: {ExamStatus.ENDED},
    ExamStatus.ENDED: set(),
}


def calculate_duration_minutes(start_time: datetime, end_time: datetime) -> int:
    """根据开始和结束时间计算考试时长（分钟）."""
    return int((end_time - start_time).total_seconds() // 60)


@router.get("", response_model=ResponseModel[list[ExamListResponse]])
async def list_exams(
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[list[ExamListResponse]]:
    """获取考试列表 — 排除已软删除的考试."""
    result = await db.execute(
        select(Exam).where(Exam.is_deleted == False).order_by(Exam.created_at.desc())  # noqa: E712
    )
    exams = result.scalars().all()

    exam_list = [ExamListResponse.model_validate(exam) for exam in exams]

    return ResponseModel(data=exam_list)


@router.get("/{exam_id}", response_model=ResponseModel[ExamDetailResponse])
async def get_exam(
    exam_id: int,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_exam_management),
) -> ResponseModel[ExamDetailResponse]:
    """获取考试详情."""
    result = await db.execute(
        select(Exam)
        .where(Exam.id == exam_id, Exam.is_deleted == False)  # noqa: E712
        .options(selectinload(Exam.problems))
    )
    exam = result.scalar_one_or_none()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考试不存在",
        )

    from app.routers.problems import parse_options_json

    problems_data = [
        {
            "id": p.id,
            "exam_id": p.exam_id,
            "title": p.title,
            "content": p.content,
            "type": p.type,
            "options": parse_options_json(p.options),
            "order_num": p.order_num,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        }
        for p in exam.problems
    ]

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
    """创建考试 — 创建时间必须在未来."""
    now = datetime.now(UTC)

    if request.start_time <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="考试开始时间必须在当前时间之后",
        )

    if request.end_time <= request.start_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="考试结束时间必须在开始时间之后",
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
    """更新考试 — 状态流转严格单向."""
    result = await db.execute(
        select(Exam).where(Exam.id == exam_id, Exam.is_deleted == False)  # noqa: E712
    )
    exam = result.scalar_one_or_none()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考试不存在",
        )

    update_data = request.model_dump(exclude_unset=True)

    # 已开始的考试只能改状态和承诺书
    if exam.status != ExamStatus.NOT_STARTED:
        editable_fields = {"status", "pledge_content"}
        other_fields = set(update_data.keys()) - editable_fields
        if other_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="考试开始后只能修改状态和承诺书",
            )

    # 处理状态变更 — 严格单向
    if "status" in update_data:
        new_status = update_data["status"]
        allowed = _VALID_TRANSITIONS.get(exam.status, set())
        if new_status not in allowed:
            status_descriptions = {
                ExamStatus.NOT_STARTED: "未开始",
                ExamStatus.ONGOING: "进行中",
                ExamStatus.ENDED: "已结束",
            }
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"不允许从「{status_descriptions.get(exam.status, exam.status.value)}」"
                    f"变更为「{status_descriptions.get(new_status, new_status.value)}」"
                ),
            )
        if new_status == ExamStatus.ONGOING and exam.actual_start_time is None:
            exam.actual_start_time = datetime.now(UTC)
        elif new_status == ExamStatus.ENDED and exam.actual_end_time is None:
            exam.actual_end_time = datetime.now(UTC)

    # 处理时间变更
    if "start_time" in update_data or "end_time" in update_data:
        new_start_time = update_data.get("start_time", exam.start_time)
        new_end_time = update_data.get("end_time", exam.end_time)
        if new_end_time <= new_start_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="考试结束时间必须在开始时间之后",
            )
        update_data["duration"] = calculate_duration_minutes(new_start_time, new_end_time)

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
    """软删除考试."""
    result = await db.execute(
        select(Exam).where(Exam.id == exam_id, Exam.is_deleted == False)  # noqa: E712
    )
    exam = result.scalar_one_or_none()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考试不存在",
        )

    exam.is_deleted = True
    await db.commit()

    return ResponseModel(data={"message": "考试已删除"})
