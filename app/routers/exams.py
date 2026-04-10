"""考试相关路由."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import (
    ExamCreate,
    ExamListResponse,
    ExamResponse,
    ExamUpdate,
    ResponseModel,
)

router = APIRouter(prefix="/api/exams", tags=["考试"])


@router.get("", response_model=ResponseModel[list[ExamListResponse]])
async def list_exams(
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[list[ExamListResponse]]:
    """获取考试列表."""
    # TODO: 实现获取考试列表
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


@router.get("/{exam_id}", response_model=ResponseModel[ExamResponse])
async def get_exam(
    exam_id: int,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[ExamResponse]:
    """获取考试详情."""
    # TODO: 实现获取考试详情
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


@router.post("", response_model=ResponseModel[dict])
async def create_exam(
    request: ExamCreate,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[dict]:
    """创建考试."""
    # TODO: 实现创建考试
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


@router.put("/{exam_id}", response_model=ResponseModel[ExamResponse])
async def update_exam(
    exam_id: int,
    request: ExamUpdate,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[ExamResponse]:
    """更新考试."""
    # TODO: 实现更新考试
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


@router.delete("/{exam_id}", response_model=ResponseModel[dict])
async def delete_exam(
    exam_id: int,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[dict]:
    """删除考试."""
    # TODO: 实现删除考试
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )
