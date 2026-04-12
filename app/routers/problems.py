"""题目相关路由."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Admin, Exam, Problem, StudentCode
from app.schemas import (
    ProblemCreate,
    ProblemResponse,
    ProblemUpdate,
    ResponseModel,
)
from app.utils.auth import require_admin

router = APIRouter(prefix="/api", tags=["题目"])


@router.get("/exams/{exam_id}/problems", response_model=ResponseModel[list[ProblemResponse]])
async def list_problems(
    exam_id: int,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[list[ProblemResponse]]:
    """获取考试题目列表."""
    # TODO: 实现获取题目列表
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


@router.post("/exams/{exam_id}/problems", response_model=ResponseModel[dict])
async def create_problem(
    exam_id: int,
    request: ProblemCreate,
    db: AsyncSession = Depends(get_db),
    admin_token: Admin = Depends(require_admin),
) -> ResponseModel[dict]:
    """添加题目.

    需要管理员权限。为指定考试添加一道新题目。

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

    # 2. 创建题目
    problem = Problem(
        exam_id=exam_id,
        title=request.title,
        content=request.content,
        order_num=request.order_num,
    )
    db.add(problem)
    await db.commit()
    await db.refresh(problem)

    return ResponseModel(data={"problem_id": problem.id})


@router.put("/problems/{problem_id}", response_model=ResponseModel[ProblemResponse])
async def update_problem(
    problem_id: int,
    request: ProblemUpdate,
    db: AsyncSession = Depends(get_db),
    admin: Admin = Depends(require_admin),
) -> ResponseModel[ProblemResponse]:
    """修改题目.

    需要管理员权限。支持部分字段更新，只更新请求中提供的字段。

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

    # 3. 更新字段
    for field, value in update_data.items():
        setattr(problem, field, value)

    # 4. 提交到数据库
    await db.commit()
    await db.refresh(problem)

    # 5. 返回更新后的数据
    return ResponseModel(data=ProblemResponse.model_validate(problem))


@router.delete("/problems/{problem_id}", response_model=ResponseModel[dict])
async def delete_problem(
    problem_id: int,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(require_admin),
) -> ResponseModel[dict]:
    """删除题目.

    需要管理员权限。删除题目时会级联删除关联的所有考生代码。

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
