"""代码相关路由."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import (
    CodeResponse,
    CodeSaveRequest,
    CodeSaveResponse,
    ResponseModel,
)

router = APIRouter(prefix="/api/code", tags=["代码"])


@router.get("/{problem_id}", response_model=ResponseModel[CodeResponse])
async def get_code(
    problem_id: int,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[CodeResponse]:
    """获取题目代码."""
    # TODO: 实现获取代码
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


@router.post("/{problem_id}", response_model=ResponseModel[CodeSaveResponse])
async def save_code(
    problem_id: int,
    request: CodeSaveRequest,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[CodeSaveResponse]:
    """保存代码."""
    # TODO: 实现保存代码
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


@router.post("/{problem_id}/submit", response_model=ResponseModel[dict])
async def submit_code(
    problem_id: int,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[dict]:
    """提交代码（交卷）."""
    # TODO: 实现提交代码
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )
