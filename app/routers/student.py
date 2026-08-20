"""考生侧路由."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Exam, Problem, Student
from app.routers.problems import parse_options_json
from app.schemas import (
    ProblemOption,
    ProblemResponse,
    ResponseModel,
)
from app.services.rate_limit import rate_limit
from app.utils import require_student

router = APIRouter(prefix="/api/student", tags=["考生"])

# 获取题目列表为读操作，token 限流
get_problems_limit = rate_limit(
    scope="student_problems",
    ip_limit=settings.rate_limit_ip_per_min,
    token_limit=settings.rate_limit_token_per_min,
)


def strip_correct_flags(options: list[ProblemOption] | None) -> list[ProblemOption] | None:
    """移除选项中的 is_correct 标记，防止答案泄露."""
    if options is None:
        return None
    return [ProblemOption(id=opt.id, content=opt.content, is_correct=False) for opt in options]


@router.get(
    "/exam/problems",
    response_model=ResponseModel[dict],
    summary="获取考试题目（考生）",
    description="根据考生 token 自动确定所属考试，返回考试信息和题目列表。",
)
async def get_student_problems(
    _: None = Depends(get_problems_limit),
    student: Student = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[dict]:
    """获取当前考生所属考试的题目列表.

    Args:
        student: 当前考生对象
        db: 数据库会话

    Returns:
        包含 exam_info 和 problems 的响应（选项不含 is_correct）
    """
    if student.exam_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="考生未关联任何考试",
        )

    exam_result = await db.execute(select(Exam).where(Exam.id == student.exam_id))
    exam = exam_result.scalar_one_or_none()
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考试不存在",
        )

    problem_result = await db.execute(
        select(Problem).where(Problem.exam_id == student.exam_id).order_by(Problem.order_num)
    )
    problems = problem_result.scalars().all()

    problems_data = [
        ProblemResponse(
            id=p.id,
            exam_id=p.exam_id,
            title=p.title,
            content=p.content,
            type=p.type,
            options=strip_correct_flags(parse_options_json(p.options)),
            order_num=p.order_num,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in problems
    ]

    return ResponseModel(
        data={
            "exam_info": {
                "id": exam.id,
                "name": exam.name,
                "subject": exam.subject,
                "duration": exam.duration,
                "start_time": exam.start_time.isoformat(),
                "end_time": exam.end_time.isoformat(),
                "status": exam.status,
            },
            "problems": [p.model_dump(mode="json") for p in problems_data],
        }
    )
