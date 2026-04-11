"""管理员相关 Pydantic 模型."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field


class AdminTokenCreate(BaseModel):
    """创建管理员 Token 请求."""

    name: str = Field(..., min_length=1, max_length=100, description="Token 名称")
    expires_at: datetime | None = Field(None, description="过期时间")


class AdminTokenUpdate(BaseModel):
    """更新管理员 Token 请求."""

    name: str | None = Field(None, min_length=1, max_length=100, description="Token 名称")
    expires_at: datetime | None = Field(None, description="过期时间")
    is_active: bool | None = Field(None, description="是否启用")


class AdminTokenResponse(BaseModel):
    """管理员 Token 响应（完整信息）."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    token: str = Field(..., description="完整的 JWT Token")
    name: str
    is_active: bool
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AdminTokenListItem(BaseModel):
    """管理员 Token 列表项（隐藏完整 Token）."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def token(self) -> str:
        """只显示 Token 前 10 位."""
        return "***"


class AdminVerifyRequest(BaseModel):
    """管理员验证请求."""

    token: str = Field(..., description="管理员 Token")
