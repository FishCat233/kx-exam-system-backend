"""题目相关路由."""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Admin, Exam, ExamStatus, Problem, StudentCode
from app.schemas import (
    ProblemCreate,
    ProblemOption,
    ProblemResponse,
    ProblemUpdate,
    ResponseModel,
)
from app.services.websocket import ws_manager
from app.utils.auth import require_problem_management

router = APIRouter(prefix="/api", tags=["题目"])


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
    """获取考试题目列表.

    返回指定考试的所有题目，按 order_num 排序。
    """
    # 1. 检查考试是否存在
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    # 2. 获取题目列表
    result = await db.execute(
        select(Problem).where(Problem.exam_id == exam_id).order_by(Problem.order_num)
    )
    problems = result.scalars().all()

    # 3. 构建响应数据
    problems_data = []
    for problem in problems:
        problems_data.append(
            ProblemResponse(
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
        )

    return ResponseModel(data=problems_data)


@router.post("/exams/{exam_id}/problems", response_model=ResponseModel[dict])
async def create_problem(
    exam_id: int,
    request: ProblemCreate,
    db: AsyncSession = Depends(get_db),
    admin_token: Admin = Depends(require_problem_management),
) -> ResponseModel[dict]:
    """添加题目.

    需要高权限管理员权限。为指定考试添加一道新题目。

    Args:
        exam_id: 考试ID
        request: 题目创建请求，包含标题、内容和排序号
        db: 数据库会话
        admin_token: 管理员Token（通过依赖注入验证）

    Returns:
        包含新创建题目ID的响应

    Raises:
        HTTPException 404: 考试不存在
        HTTPException 401: 未提供管理员Token或Token无效
    """
    # 1. 检查考试是否存在
    result = await db.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found",
        )

    # 2. 验证选择题数据
    validate_choice_problem(request.type, request.options)

    # 3. 创建题目
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

    # 4. 如果考试正在进行，向所有在线考生广播新题目通知
    if exam.status == ExamStatus.ONGOING:
        await ws_manager.broadcast_new_problem(exam_id, request.title, db)

    return ResponseModel(data={"problem_id": problem.id})


@router.put("/problems/{problem_id}", response_model=ResponseModel[ProblemResponse])
async def update_problem(
    problem_id: int,
    request: ProblemUpdate,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(require_problem_management),
) -> ResponseModel[ProblemResponse]:
    """修改题目.

    需要高权限管理员权限。支持部分字段更新，只更新请求中提供的字段。

    Args:
        problem_id: 题目ID
        request: 题目更新请求，可包含标题、内容、排序号中的任意字段
        db: 数据库会话
        admin: 管理员Token（通过依赖注入验证）

    Returns:
        包含更新后题目信息的响应

    Raises:
        HTTPException 404: 题目不存在
        HTTPException 401: 未提供管理员Token或Token无效
    """
    # 1. 查询题目是否存在
    result = await db.execute(select(Problem).where(Problem.id == problem_id))
    problem = result.scalar_one_or_none()

    if problem is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Problem not found",
        )

    # 2. 使用 exclude_unset=True 支持部分字段更新
    update_data = request.model_dump(exclude_unset=True)

    # 3. 处理选项数据转换
    if "options" in update_data and update_data["options"] is not None:
        options_list = update_data["options"]
        # 处理可能是 dict 或 ProblemOption 对象的情况
        serialized_options = []
        for opt in options_list:
            if hasattr(opt, "model_dump"):
                serialized_options.append(opt.model_dump())
            else:
                serialized_options.append(opt)
        update_data["options"] = json.dumps(serialized_options)

    # 4. 验证选择题数据（如果更新了类型或选项）
    new_type = update_data.get("type", problem.type)
    new_options = request.options
    if new_options is None and "options" not in update_data:
        new_options = parse_options_json(problem.options)
    validate_choice_problem(new_type, new_options)

    # 5. 更新字段
    for field, value in update_data.items():
        setattr(problem, field, value)

    # 6. 提交到数据库
    await db.commit()
    await db.refresh(problem)

    # 7. 构建响应数据
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

    # 8. 返回更新后的数据
    return ResponseModel(data=response_data)


@router.delete("/problems/{problem_id}", response_model=ResponseModel[dict])
async def delete_problem(
    problem_id: int,
    db: AsyncSession = Depends(get_db),
    _: Admin = Depends(require_problem_management),
) -> ResponseModel[dict]:
    """删除题目.

    需要高权限管理员权限。删除题目时会级联删除关联的所有考生代码。

    Args:
        problem_id: 题目ID
        db: 数据库会话
        _: 管理员Token（通过依赖注入验证）

    Returns:
        包含删除成功消息的响应

    Raises:
        HTTPException 404: 题目不存在
        HTTPException 401: 未提供管理员Token或Token无效
    """
    # 查询题目是否存在
    result = await db.execute(select(Problem).where(Problem.id == problem_id))
    problem = result.scalar_one_or_none()

    if problem is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Problem not found",
        )

    # 级联删除关联的考生代码
    result = await db.execute(select(StudentCode).where(StudentCode.problem_id == problem_id))
    student_codes = result.scalars().all()
    for code in student_codes:
        await db.delete(code)

    # 删除题目
    await db.delete(problem)
    await db.commit()

    return ResponseModel(data={"message": "Problem deleted successfully"})
