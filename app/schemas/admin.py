"""管理员相关 Pydantic 模型."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AdminCreate(BaseModel):
    """创建管理员请求."""

    username: str = Field(..., min_length=3, max_length=50, description="管理员账号")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    name: str | None = Field(None, max_length=100, description="显示名称")
    remark: str | None = Field(None, max_length=500, description="备注")


class AdminUpdate(BaseModel):
    """更新管理员请求."""

    name: str | None = Field(None, max_length=100, description="显示名称")
    remark: str | None = Field(None, max_length=500, description="备注")
    is_active: bool | None = Field(None, description="是否启用")


class AdminResponse(BaseModel):
    """管理员响应（不含密码）."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    name: str | None
    is_active: bool
    remark: str | None
    created_at: datetime
    updated_at: datetime


class AdminListItem(BaseModel):
    """管理员列表项."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    name: str | None
    is_active: bool
    remark: str | None
    created_at: datetime
    updated_at: datetime


class AdminLoginRequest(BaseModel):
    """管理员登录请求."""

    username: str = Field(..., description="管理员账号")
    password: str = Field(..., description="密码")


class AdminInfo(BaseModel):
    """管理员信息（用于登录响应）."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    name: str | None
    is_active: bool


class AdminLoginResponse(BaseModel):
    """管理员登录响应."""

    token: str = Field(..., description="JWT Token")
    admin: AdminInfo


class ChangePasswordRequest(BaseModel):
    """修改密码请求（管理员自己修改）."""

    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")


class ForceChangePasswordRequest(BaseModel):
    """强制修改密码请求（超级管理员使用）."""

    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")


# 保留旧模型以保持兼容性（用于其他引用的地方）
class AdminTokenCreate(BaseModel):
    """创建管理员 Token 请求（已弃用，保留兼容性）."""

    name: str = Field(..., min_length=1, max_length=100, description="Token 名称")
    expires_at: datetime | None = Field(None, description="过期时间")


class AdminTokenUpdate(BaseModel):
    """更新管理员 Token 请求（已弃用，保留兼容性）."""

    name: str | None = Field(None, min_length=1, max_length=100, description="Token 名称")
    expires_at: datetime | None = Field(None, description="过期时间")
    is_active: bool | None = Field(None, description="是否启用")


class AdminTokenResponse(BaseModel):
    """管理员 Token 响应（已弃用，保留兼容性）."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    token: str = Field(..., description="完整的 JWT Token")
    name: str
    is_active: bool
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AdminTokenListItem(BaseModel):
    """管理员 Token 列表项（已弃用，保留兼容性）."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_active: bool
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @property
    def token(self) -> str:
        """只显示 Token 前 10 位."""
        return "***"


class AdminVerifyRequest(BaseModel):
    """管理员验证请求."""

    token: str = Field(..., description="管理员 Token")
