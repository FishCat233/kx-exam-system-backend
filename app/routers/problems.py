"""题目相关路由."""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Admin, Exam, ExamStatus, Problem, StudentCode
from app.schemas import (
    ProblemCreate,
    ProblemOption,
    ProblemResponse,
    ProblemUpdate,
    ResponseModel,
)
from app.services.rate_limit import rate_limit
from app.services.websocket import ws_manager
from app.utils.auth import require_problem_management

# 题目管理接口按 token 限流
problem_router_limit = rate_limit(
    scope="problem",
    ip_limit=settings.rate_limit_ip_per_min,
    token_limit=settings.rate_limit_token_per_min,
)

router = APIRouter(prefix="/api", tags=["题目"], dependencies=[Depends(problem_router_limit)])


def parse_options_json(options_json: str | None) -> list[ProblemOption] | None:
    """解析选项JSON字符串."""
    if not options_json:
        return None
    try:
        options_list = json.loads(options_json)
        return [ProblemOption(**opt) for opt in options_list] if options_list else None
    except (json.JSONDecodeError, TypeError):
        return None


def validate_choice_problem(problem_type: str, options: list[ProblemOption] | None) -> None:
    """验证选择题数据."""
    if problem_type in ("single_choice", "multiple_choice"):
        if not options or len(options) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="选择题至少需要2个选项",
            )

        correct_count = sum(1 for opt in options if opt.is_correct)

        if problem_type == "single_choice" and correct_count != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="单选题必须有且只有一个正确答案",
            )

        if problem_type == "multiple_choice" and correct_count < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="多选题至少需要一个正确答案",
            )


@router.get("/exams/{exam_id}/problems", response_model=ResponseModel[list[ProblemResponse]])
async def list_problems(
    exam_id: int,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_problem_management),
) -> ResponseModel[list[ProblemResponse]]:
    """获取考试题目列表."""
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考试不存在",
        )

    result = await db.execute(
        select(Problem).where(Problem.exam_id == exam_id).order_by(Problem.order_num)
    )
    problems = result.scalars().all()

    problems_data = [
        ProblemResponse(
            id=p.id,
            exam_id=p.exam_id,
            title=p.title,
            content=p.content,
            type=p.type,
            options=parse_options_json(p.options),
            order_num=p.order_num,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in problems
    ]

    return ResponseModel(data=problems_data)


@router.post("/exams/{exam_id}/problems", response_model=ResponseModel[dict])
async def create_problem(
    exam_id: int,
    request: ProblemCreate,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_problem_management),
) -> ResponseModel[dict]:
    """添加题目."""
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="考试不存在",
        )

    validate_choice_problem(request.type, request.options)

    problem = Problem(
        exam_id=exam_id,
        title=request.title,
        content=request.content,
        type=request.type,
        options=json.dumps([opt.model_dump() for opt in request.options])
        if request.options
        else None,
        order_num=request.order_num,
    )
    db.add(problem)
    await db.commit()
    await db.refresh(problem)

    if exam.status == ExamStatus.ONGOING:
        await ws_manager.broadcast_new_problem(exam_id, request.title, db)

    return ResponseModel(data={"problem_id": problem.id})


@router.put("/problems/{problem_id}", response_model=ResponseModel[ProblemResponse])
async def update_problem(
    problem_id: int,
    request: ProblemUpdate,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_problem_management),
) -> ResponseModel[ProblemResponse]:
    """修改题目."""
    result = await db.execute(select(Problem).where(Problem.id == problem_id))
    problem = result.scalar_one_or_none()

    if problem is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="题目不存在",
        )

    update_data = request.model_dump(exclude_unset=True)

    if "options" in update_data and update_data["options"] is not None:
        options_list = update_data["options"]
        serialized_options = []
        for opt in options_list:
            if hasattr(opt, "model_dump"):
                serialized_options.append(opt.model_dump())
            else:
                serialized_options.append(opt)
        update_data["options"] = json.dumps(serialized_options)

    new_type = update_data.get("type", problem.type)
    new_options = request.options
    if new_options is None and "options" not in update_data:
        new_options = parse_options_json(problem.options)
    validate_choice_problem(new_type, new_options)

    for field, value in update_data.items():
        setattr(problem, field, value)

    await db.commit()
    await db.refresh(problem)

    response_data = ProblemResponse(
        id=problem.id,
        exam_id=problem.exam_id,
        title=problem.title,
        content=problem.content,
        type=problem.type,
        options=parse_options_json(problem.options),
        order_num=problem.order_num,
        created_at=problem.created_at,
        updated_at=problem.updated_at,
    )

    return ResponseModel(data=response_data)


@router.delete("/problems/{problem_id}", response_model=ResponseModel[dict])
async def delete_problem(
    problem_id: int,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_problem_management),
) -> ResponseModel[dict]:
    """删除题目 — 级联删除关联的考生代码."""
    result = await db.execute(select(Problem).where(Problem.id == problem_id))
    problem = result.scalar_one_or_none()

    if problem is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="题目不存在",
        )

    result = await db.execute(select(StudentCode).where(StudentCode.problem_id == problem_id))
    for code in result.scalars().all():
        await db.delete(code)

    await db.delete(problem)
    await db.commit()

    return ResponseModel(data={"message": "题目已删除"})
