"""应用配置管理."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类."""

    # 应用配置
    app_name: str = "KX Exam System Backend"
    debug: bool = False

    # 数据库配置 — PostgreSQL
    database_url: str = "postgresql+asyncpg://exam:exam123@localhost:5432/exam_system"

    # JWT 配置
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24小时

    # 超级管理员配置
    super_admin_username: str = "admin"
    super_admin_password: str = "admin123"
    super_admin_name: str = "超级管理员"

    # CORS 配置
    cors_origins: list[str] = ["*"]

    # WebSocket 配置
    ws_scheme: str = "ws"
    ws_host: str = "localhost"
    ws_port: int = 8000
    ws_path: str = "/ws"

    # 限流配置
    rate_limit_enabled: bool = True
    # 通用每 IP 每分钟请求上限（登录接口的 NAT 场景已单独放宽）
    rate_limit_ip_per_min: int = 120
    # 考生登录每 IP 每分钟上限（同一机房 NAT 共享 IP 时需足够宽裕）
    rate_limit_login_per_min: int = 120
    # 管理员登录每 IP 每分钟上限（管理端登录频率极低，可从严）
    rate_limit_admin_login_per_min: int = 10
    # 通用每 token 每分钟请求上限
    rate_limit_token_per_min: int = 60
    # 保存代码每考生每分钟上限（前端自动保存约每分钟 12 次，留足余量）
    rate_limit_save_code_per_min: int = 60
    # 交卷每考生每分钟上限（交卷只应发生一次）
    rate_limit_submit_per_min: int = 5
    # WebSocket 每 IP 每分钟新连接数上限
    rate_limit_ws_connect_per_min: int = 30
    # 全局并发请求数上限（超出直接返回 429，防止高并发洪水打垮服务）
    max_concurrent_requests: int = 100

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
