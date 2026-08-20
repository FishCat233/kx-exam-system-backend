"""Pytest 配置和 fixtures."""

import asyncio
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

# 使用内存数据库进行测试
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """覆盖数据库依赖，使用测试数据库."""
    async with TestingSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def clean_ws_manager():
    """每个测试前清理全局 ws_manager 状态，避免相互污染."""
    from app.services.rate_limit import limiter
    from app.services.websocket import ws_manager

    ws_manager.active_connections.clear()
    ws_manager.token_to_student_id.clear()
    ws_manager.student_id_to_token.clear()
    ws_manager.connection_info.clear()
    ws_manager.ever_connected_students.clear()
    limiter.reset()
    yield
    ws_manager.active_connections.clear()
    ws_manager.token_to_student_id.clear()
    ws_manager.student_id_to_token.clear()
    ws_manager.connection_info.clear()
    ws_manager.ever_connected_students.clear()
    limiter.reset()


@pytest_asyncio.fixture(scope="session")
def event_loop():
    """创建事件循环."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """创建测试数据库会话.

    Yields:
        AsyncSession: 数据库会话
    """
    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    # 清理表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """创建测试客户端.

    Args:
        db_session: 数据库会话

    Yields:
        AsyncClient: HTTP 客户端
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
