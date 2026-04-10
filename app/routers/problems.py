"""题目相关路由."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import (
    ProblemCreate,
    ProblemResponse,
    ProblemUpdate,
    ResponseModel,
)

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
) -> ResponseModel[dict]:
    """添加题目."""
    # TODO: 实现添加题目
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


@router.put("/problems/{problem_id}", response_model=ResponseModel[ProblemResponse])
async def update_problem(
    problem_id: int,
    request: ProblemUpdate,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[ProblemResponse]:
    """修改题目."""
    # TODO: 实现修改题目
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


@router.delete("/problems/{problem_id}", response_model=ResponseModel[dict])
async def delete_problem(
    problem_id: int,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[dict]:
    """删除题目."""
    # TODO: 实现删除题目
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )
