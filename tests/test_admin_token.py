"""管理员 Token 相关测试."""

from datetime import UTC

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AdminToken

# ==================== 超级管理员认证测试 ====================


@pytest.mark.asyncio
async def test_super_admin_auth_success(client: AsyncClient):
    """测试超级管理员认证成功."""
    response = await client.post(
        "/api/admin/tokens",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
        json={"name": "Test Token"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_super_admin_auth_failure(client: AsyncClient):
    """测试超级管理员认证失败."""
    response = await client.post(
        "/api/admin/tokens",
        headers={"X-Super-Admin-Key": "wrong-key"},
        json={"name": "Test Token"},
    )
    assert response.status_code == 403


# ==================== 创建管理员 Token 测试 ====================


@pytest.mark.asyncio
async def test_create_admin_token(client: AsyncClient, db_session: AsyncSession):
    """测试创建管理员 Token."""
    response = await client.post(
        "/api/admin/tokens",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
        json={"name": "Test Token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "token" in data["data"]
    assert data["data"]["name"] == "Test Token"

    # 验证数据库中有记录
    result = await db_session.execute(select(AdminToken).where(AdminToken.name == "Test Token"))
    token_record = result.scalar_one_or_none()
    assert token_record is not None
    assert token_record.name == "Test Token"
    assert token_record.is_active is True


@pytest.mark.asyncio
async def test_create_admin_token_with_expires(client: AsyncClient):
    """测试创建带过期时间的 Token."""
    # 使用时区感知的 ISO 格式时间（带 Z 表示 UTC）
    response = await client.post(
        "/api/admin/tokens",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
        json={"name": "Test Token", "expires_at": "2025-12-31T23:59:59Z"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "token" in data["data"]
    assert data["data"]["expires_at"] is not None


@pytest.mark.asyncio
async def test_create_admin_token_validation_error(client: AsyncClient):
    """测试创建 Token 参数验证失败."""
    response = await client.post(
        "/api/admin/tokens",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
        json={},  # 缺少 name
    )
    assert response.status_code == 422


# ==================== 获取 Token 列表测试 ====================


@pytest.mark.asyncio
async def test_list_admin_tokens(client: AsyncClient, db_session: AsyncSession):
    """测试获取管理员 Token 列表."""
    # 先创建几个 Token（使用不同的过期时间确保 JWT token 不同）
    from datetime import datetime, timedelta

    for i in range(3):
        expires_at = (datetime.now(UTC) + timedelta(days=i + 1)).isoformat()
        await client.post(
            "/api/admin/tokens",
            headers={"X-Super-Admin-Key": settings.super_admin_key},
            json={"name": f"Token {i}", "expires_at": expires_at},
        )

    # 获取列表
    response = await client.get(
        "/api/admin/tokens",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert isinstance(data["data"], list)
    assert len(data["data"]) >= 3


# ==================== 修改 Token 测试 ====================


@pytest.mark.asyncio
async def test_update_admin_token(client: AsyncClient, db_session: AsyncSession):
    """测试修改管理员 Token."""
    # 先创建一个 Token
    create_response = await client.post(
        "/api/admin/tokens",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
        json={"name": "Original Name"},
    )
    token_id = create_response.json()["data"]["id"]

    # 修改 Token
    response = await client.put(
        f"/api/admin/tokens/{token_id}",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
        json={"name": "Updated Name"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["name"] == "Updated Name"

    # 验证数据库已更新
    result = await db_session.execute(select(AdminToken).where(AdminToken.id == token_id))
    token_record = result.scalar_one()
    assert token_record.name == "Updated Name"


@pytest.mark.asyncio
async def test_update_admin_token_not_found(client: AsyncClient):
    """测试修改不存在的 Token."""
    response = await client.put(
        "/api/admin/tokens/9999",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
        json={"name": "Updated Name"},
    )
    assert response.status_code == 404


# ==================== 删除 Token 测试 ====================


@pytest.mark.asyncio
async def test_delete_admin_token(client: AsyncClient, db_session: AsyncSession):
    """测试删除管理员 Token."""
    # 先创建一个 Token
    create_response = await client.post(
        "/api/admin/tokens",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
        json={"name": "Token to Delete"},
    )
    token_id = create_response.json()["data"]["id"]

    # 删除 Token
    response = await client.delete(
        f"/api/admin/tokens/{token_id}",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200

    # 验证数据库中已删除
    result = await db_session.execute(select(AdminToken).where(AdminToken.id == token_id))
    token_record = result.scalar_one_or_none()
    assert token_record is None


# ==================== 停用 Token 测试 ====================


@pytest.mark.asyncio
async def test_deactivate_admin_token(client: AsyncClient, db_session: AsyncSession):
    """测试停用管理员 Token."""
    # 先创建一个 Token
    create_response = await client.post(
        "/api/admin/tokens",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
        json={"name": "Token to Deactivate"},
    )
    token_id = create_response.json()["data"]["id"]

    # 停用 Token
    response = await client.post(
        f"/api/admin/tokens/{token_id}/deactivate",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["is_active"] is False

    # 验证数据库已更新
    result = await db_session.execute(select(AdminToken).where(AdminToken.id == token_id))
    token_record = result.scalar_one()
    assert token_record.is_active is False


# ==================== 验证 Token 测试 ====================


@pytest.mark.asyncio
async def test_verify_admin_token_success(client: AsyncClient):
    """测试验证有效的管理员 Token."""
    # 先创建一个 Token，获取 token 值
    create_response = await client.post(
        "/api/admin/tokens",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
        json={"name": "Token to Verify"},
    )
    token_value = create_response.json()["data"]["token"]

    # 验证 Token
    response = await client.post(
        "/api/auth/admin/verify",
        headers={"Authorization": f"Bearer {token_value}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["valid"] is True
    assert data["data"]["admin_info"] is not None
    assert data["data"]["admin_info"]["name"] == "Token to Verify"


@pytest.mark.asyncio
async def test_verify_admin_token_invalid(client: AsyncClient):
    """测试验证无效的 Token."""
    response = await client.post(
        "/api/auth/admin/verify",
        headers={"Authorization": "Bearer invalid_token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 401
    assert data["data"]["valid"] is False


@pytest.mark.asyncio
async def test_verify_admin_token_inactive(client: AsyncClient):
    """测试验证已停用的 Token."""
    # 创建 Token
    create_response = await client.post(
        "/api/admin/tokens",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
        json={"name": "Inactive Token"},
    )
    token_id = create_response.json()["data"]["id"]
    token_value = create_response.json()["data"]["token"]

    # 停用 Token
    await client.post(
        f"/api/admin/tokens/{token_id}/deactivate",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
    )

    # 验证已停用的 Token
    response = await client.post(
        "/api/auth/admin/verify",
        headers={"Authorization": f"Bearer {token_value}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 401
    assert data["data"]["valid"] is False
