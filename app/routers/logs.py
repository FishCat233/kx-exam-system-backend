"""日志相关路由."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import ResponseModel

router = APIRouter(prefix="/api", tags=["日志"])


@router.post("/logs", response_model=ResponseModel[dict])
async def create_log(
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[dict]:
    """上报操作日志."""
    # TODO: 实现上报操作日志
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


@router.get("/admin/exams/{exam_id}/logs", response_model=ResponseModel[list[dict]])
async def list_logs(
    exam_id: int,
    level: str | None = None,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[list[dict]]:
    """获取考试日志."""
    # TODO: 实现获取考试日志
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )
