"""限流相关测试."""

import asyncio

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.services.rate_limit import limiter, rate_limit


@pytest.mark.asyncio
async def test_limiter_allows_up_to_limit():
    """限流器允许窗口内前 N 次请求通过."""
    key = "ip:test"
    assert limiter.check(key, limit=3, window=60)
    assert limiter.check(key, limit=3, window=60)
    assert limiter.check(key, limit=3, window=60)
    assert not limiter.check(key, limit=3, window=60)


@pytest.mark.asyncio
async def test_limiter_window_resets():
    """窗口过期后计数重置."""
    key = "ip:test-window"
    assert limiter.check(key, limit=2, window=0.01)
    assert limiter.check(key, limit=2, window=0.01)
    assert not limiter.check(key, limit=2, window=0.01)

    # 等待窗口过期
    await asyncio.sleep(0.02)
    assert limiter.check(key, limit=2, window=0.01)


@pytest.mark.asyncio
async def test_limiter_scope_isolation():
    """不同 scope 的 key 互不干扰."""
    assert limiter.check("a:ip:1", limit=1, window=60)
    assert limiter.check("b:ip:1", limit=1, window=60)
    assert not limiter.check("a:ip:1", limit=1, window=60)


@pytest.mark.asyncio
async def test_limiter_reset():
    """reset 清空所有窗口."""
    key = "ip:reset"
    assert limiter.check(key, limit=1, window=60)
    assert not limiter.check(key, limit=1, window=60)
    limiter.reset()
    assert limiter.check(key, limit=1, window=60)


@pytest.fixture
def rate_limited_app():
    """构造带限流依赖的测试应用."""
    app = FastAPI()
    limit_dep = rate_limit(
        scope="test",
        ip_limit=2,
        token_limit=3,
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.status_code, "message": exc.detail, "data": None},
            headers=exc.headers,
        )

    @app.get("/test")
    async def test_endpoint(_: None = Depends(limit_dep)):
        """测试端点."""
        return {"ok": True}

    return app


@pytest.fixture
async def rate_limited_client(rate_limited_app):
    """创建限流测试客户端."""
    transport = ASGITransport(app=rate_limited_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_ip_rate_limit_rejects_after_limit(rate_limited_client: AsyncClient):
    """IP 限流：同一 IP 超过限制后返回 429."""
    responses = [await rate_limited_client.get("/test") for _ in range(3)]
    statuses = [r.status_code for r in responses]
    assert statuses == [200, 200, 429]


@pytest.mark.asyncio
async def test_token_rate_limit_rejects_after_limit(rate_limited_client: AsyncClient):
    """token 限流：同一 token 超过限制后返回 429."""
    headers = {"Authorization": "Bearer test-token"}
    responses = [await rate_limited_client.get("/test", headers=headers) for _ in range(4)]
    statuses = [r.status_code for r in responses]
    # IP 限流为 2，token 限流为 3，IP 先触发
    assert statuses == [200, 200, 429, 429]


@pytest.mark.asyncio
async def test_rate_limit_disabled(rate_limited_client: AsyncClient):
    """关闭限流后所有请求放行."""
    settings.rate_limit_enabled = False
    try:
        responses = [await rate_limited_client.get("/test") for _ in range(5)]
        assert all(r.status_code == 200 for r in responses)
    finally:
        settings.rate_limit_enabled = True


@pytest.mark.asyncio
async def test_429_response_shape(rate_limited_client: AsyncClient):
    """429 响应体与统一格式一致，并携带 Retry-After 头."""
    await rate_limited_client.get("/test")
    await rate_limited_client.get("/test")
    response = await rate_limited_client.get("/test")
    assert response.status_code == 429
    assert response.headers.get("retry-after") == "60"
    body = response.json()
    assert body["code"] == 429
    assert "频繁" in body["message"]
    assert body["data"] is None
