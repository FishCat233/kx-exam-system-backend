"""通用 Pydantic 模型."""

from typing import Any

from pydantic import BaseModel


class ResponseModel[T](BaseModel):
    """通用响应模型."""

    code: int = 200
    message: str = "success"
    data: T | None = None


class PaginationParams(BaseModel):
    """分页参数."""

    page: int = 1
    page_size: int = 20


class PaginationResponse[T](BaseModel):
    """分页响应模型."""

    total: int
    page: int
    page_size: int
    items: list[T]


class ErrorResponse(BaseModel):
    """错误响应模型."""

    code: int
    message: str
    detail: dict[str, Any] | None = None
