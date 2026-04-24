"""应用配置管理."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类."""

    # 应用配置
    app_name: str = "KX Exam System Backend"
    debug: bool = False

    # 数据库配置
    database_url: str = "sqlite+aiosqlite:///./exam_system.db"

    # JWT 配置
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24小时

    # 超级管理员配置（管理员体系中的高权限账号）
    super_admin_username: str = "admin"
    super_admin_password: str = "admin123"
    super_admin_name: str = "超级管理员"

    # CORS 配置
    cors_origins: list[str] = ["*"]

    # WebSocket 配置
    ws_host: str = "localhost"
    ws_port: int = 8000
    ws_path: str = "/ws"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
