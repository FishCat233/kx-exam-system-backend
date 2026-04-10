"""认证相关路由."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import (
    AdminVerifyResponse,
    FullscreenRequest,
    FullscreenResponse,
    LoginRequest,
    LoginResponse,
    ResponseModel,
)

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/student/login", response_model=ResponseModel[LoginResponse])
async def student_login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[LoginResponse]:
    """考生登录."""
    # TODO: 实现登录逻辑
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


@router.post("/student/fullscreen", response_model=ResponseModel[FullscreenResponse])
async def report_fullscreen(
    request: FullscreenRequest,
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[FullscreenResponse]:
    """上报全屏状态."""
    # TODO: 实现全屏状态上报
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )


@router.post("/admin/verify", response_model=ResponseModel[AdminVerifyResponse])
async def verify_admin(
    db: AsyncSession = Depends(get_db),
) -> ResponseModel[AdminVerifyResponse]:
    """验证管理员 Token."""
    # TODO: 实现管理员验证
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Not implemented",
    )
