"""管理员相关路由."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import (
    ResponseModel,
    StudentCreate,
    StudentDetail,
    StudentListItem,
)

router = APIRouter(prefix="/api/admin", tags=["管理"])


@router.get("/exams/{exam_id}/students", response_model=ResponseModel[list[StudentListItem]])
async def list_students(
    exam_id: int,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[list[StudentListItem]]:
    """获取考生列表."""
    # TODO: 实现获取考生列表
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


@router.post("/exams/{exam_id}/students", response_model=ResponseModel[dict])
async def import_students(
    exam_id: int,
    students: list[StudentCreate],
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[dict]:
    """批量导入考生."""
    # TODO: 实现批量导入考生
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


@router.get("/students/{student_id}", response_model=ResponseModel[StudentDetail])
async def get_student_detail(
    student_id: int,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[StudentDetail]:
    """获取考生详情."""
    # TODO: 实现获取考生详情
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


@router.post("/students/{student_id}/force-submit", response_model=ResponseModel[dict])
async def force_submit(
    student_id: int,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[dict]:
    """强制收卷."""
    # TODO: 实现强制收卷
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


@router.delete("/students/{student_id}", response_model=ResponseModel[dict])
async def delete_student(
    student_id: int,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[dict]:
    """删除考生."""
    # TODO: 实现删除考生
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


@router.get("/dashboard/{exam_id}", response_model=ResponseModel[dict])
async def get_dashboard(
    exam_id: int,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[dict]:
    """获取仪表盘数据."""
    # TODO: 实现获取仪表盘数据
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


@router.get("/exams/{exam_id}/export")
async def export_exam(
    exam_id: int,
    db: AsyncSession = Depends(get_db),
):
    """导出考试数据."""
    # TODO: 实现导出考试数据
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


# 管理员 Token 管理
@router.get("/tokens", response_model=ResponseModel[list[dict]])
async def list_admin_tokens(
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[list[dict]]:
    """获取管理员 Token 列表."""
    # TODO: 实现获取管理员 Token 列表
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


@router.post("/tokens", response_model=ResponseModel[dict])
async def create_admin_token(
    name: str,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[dict]:
    """创建管理员 Token."""
    # TODO: 实现创建管理员 Token
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


@router.put("/tokens/{token_id}", response_model=ResponseModel[dict])
async def update_admin_token(
    token_id: int,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[dict]:
    """修改管理员 Token."""
    # TODO: 实现修改管理员 Token
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


@router.delete("/tokens/{token_id}", response_model=ResponseModel[dict])
async def delete_admin_token(
    token_id: int,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[dict]:
    """删除管理员 Token."""
    # TODO: 实现删除管理员 Token
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


@router.post("/tokens/{token_id}/deactivate", response_model=ResponseModel[dict])
async def deactivate_admin_token(
    token_id: int,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[dict]:
    """停用管理员 Token."""
    # TODO: 实现停用管理员 Token
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )
