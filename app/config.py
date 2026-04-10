"""应用配置管理."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置类."""

    # 应用配置
    app_name: str = "XMN Exam System Backend"
    debug: bool = False

    # 数据库配置
    database_url: str = "sqlite+aiosqlite:///./exam_system.db"

    # JWT 配置
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24小时

    # 超级管理员配置
    super_admin_key: str = "super-admin-secret-key"

    # CORS 配置
    cors_origins: list[str] = ["*"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
