"""数据库配置."""

from collections.abc import AsyncGenerator
from datetime import UTC

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

from app.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy 模型基类."""

    pass


class UTCDateTime(TypeDecorator):
    """UTC 时间列：存储 naive UTC，读写时与 aware UTC 互转.

    PostgreSQL 迁移后，`timestamp without time zone` 列只接受 naive datetime，
    而代码统一使用 `datetime.now(UTC)`（aware）。此类型在写入时剥掉时区，
    读出时补上 UTC 时区，保证代码侧始终拿到 aware datetime。
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is not None:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return value.replace(tzinfo=UTC)
        return value


# 创建异步引擎（PostgreSQL + asyncpg，配置连接池）
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=20,
    max_overflow=30,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话依赖.

    Yields:
        AsyncSession: 数据库会话
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
