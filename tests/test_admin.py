"""管理员系统相关测试."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Admin
from app.utils.auth import create_access_token, get_password_hash, verify_password

# ==================== 辅助函数 ====================


def create_admin_token(admin_id: int) -> str:
    """创建管理员 JWT Token."""
    token_payload = {"type": "admin", "admin_id": admin_id}
    return create_access_token(token_payload)


async def create_test_admin(
    db_session: AsyncSession,
    username: str = "test_admin",
    password: str = "test_password",
    name: str = "Test Admin",
    is_active: bool = True,
    remark: str = "Test remark",
) -> Admin:
    """创建测试管理员账号."""
    admin = Admin(
        username=username,
        password_hash=get_password_hash(password),
        name=name,
        is_active=is_active,
        remark=remark,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


# ==================== 超级管理员认证测试 ====================


@pytest.mark.asyncio
async def test_super_admin_auth_success(client: AsyncClient):
    """测试超级管理员认证成功."""
    response = await client.post(
        "/api/admin/admins",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
        json={"username": "new_admin", "password": "new_password", "name": "New Admin"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_super_admin_auth_failure(client: AsyncClient):
    """测试超级管理员认证失败."""
    response = await client.post(
        "/api/admin/admins",
        headers={"X-Super-Admin-Key": "wrong-key"},
        json={"username": "new_admin", "password": "new_password"},
    )
    assert response.status_code == 403


# ==================== 管理员账号密码登录测试 ====================


@pytest.mark.asyncio
async def test_admin_login_success(client: AsyncClient, db_session: AsyncSession):
    """测试管理员登录成功."""
    # 创建测试管理员
    await create_test_admin(db_session, username="login_test", password="correct_password")

    # 登录
    response = await client.post(
        "/api/auth/admin/login",
        json={"username": "login_test", "password": "correct_password"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "token" in data["data"]
    assert data["data"]["admin"]["username"] == "login_test"


@pytest.mark.asyncio
async def test_admin_login_wrong_password(client: AsyncClient, db_session: AsyncSession):
    """测试管理员登录密码错误."""
    # 创建测试管理员
    await create_test_admin(db_session, username="login_test2", password="correct_password")

    # 使用错误密码登录
    response = await client.post(
        "/api/auth/admin/login",
        json={"username": "login_test2", "password": "wrong_password"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_login_nonexistent_user(client: AsyncClient):
    """测试登录不存在的账号."""
    response = await client.post(
        "/api/auth/admin/login",
        json={"username": "nonexistent", "password": "some_password"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_login_deactivated_account(client: AsyncClient, db_session: AsyncSession):
    """测试登录已停用的账号."""
    # 创建已停用的管理员
    await create_test_admin(
        db_session,
        username="deactivated_admin",
        password="password",
        is_active=False,
    )

    # 尝试登录
    response = await client.post(
        "/api/auth/admin/login",
        json={"username": "deactivated_admin", "password": "password"},
    )
    assert response.status_code == 403


# ==================== 创建管理员账号测试 ====================


@pytest.mark.asyncio
async def test_create_admin_success(client: AsyncClient, db_session: AsyncSession):
    """测试创建管理员账号成功."""
    response = await client.post(
        "/api/admin/admins",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
        json={
            "username": "new_admin",
            "password": "new_password",
            "name": "New Admin",
            "remark": "Test remark",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["username"] == "new_admin"
    assert data["data"]["name"] == "New Admin"
    assert data["data"]["remark"] == "Test remark"
    assert data["data"]["is_active"] is True

    # 验证数据库中有记录
    result = await db_session.execute(select(Admin).where(Admin.username == "new_admin"))
    admin = result.scalar_one_or_none()
    assert admin is not None
    assert admin.username == "new_admin"
    assert verify_password("new_password", admin.password_hash)


@pytest.mark.asyncio
async def test_create_admin_duplicate_username(client: AsyncClient, db_session: AsyncSession):
    """测试创建重复账号名的管理员."""
    # 先创建一个管理员
    await create_test_admin(db_session, username="duplicate_user")

    # 尝试创建相同账号名的管理员
    response = await client.post(
        "/api/admin/admins",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
        json={"username": "duplicate_user", "password": "password"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_admin_validation_error(client: AsyncClient):
    """测试创建管理员参数验证失败."""
    # 缺少 username
    response = await client.post(
        "/api/admin/admins",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
        json={"password": "password"},
    )
    assert response.status_code == 422

    # 缺少 password
    response = await client.post(
        "/api/admin/admins",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
        json={"username": "test_user"},
    )
    assert response.status_code == 422


# ==================== 获取管理员列表测试 ====================


@pytest.mark.asyncio
async def test_list_admins(client: AsyncClient, db_session: AsyncSession):
    """测试获取管理员列表."""
    # 创建几个管理员
    await create_test_admin(db_session, username="admin1", name="Admin 1")
    await create_test_admin(db_session, username="admin2", name="Admin 2")
    await create_test_admin(db_session, username="admin3", name="Admin 3", is_active=False)

    # 获取列表
    response = await client.get(
        "/api/admin/admins",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert isinstance(data["data"], list)
    assert len(data["data"]) >= 3


@pytest.mark.asyncio
async def test_list_admins_filter_by_active(client: AsyncClient, db_session: AsyncSession):
    """测试按状态筛选管理员列表."""
    # 创建管理员
    await create_test_admin(db_session, username="active_admin", is_active=True)
    await create_test_admin(db_session, username="inactive_admin", is_active=False)

    # 获取启用的管理员
    response = await client.get(
        "/api/admin/admins?is_active=true",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
    )
    assert response.status_code == 200
    data = response.json()
    assert all(admin["is_active"] for admin in data["data"])

    # 获取停用的管理员
    response = await client.get(
        "/api/admin/admins?is_active=false",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
    )
    assert response.status_code == 200
    data = response.json()
    assert all(not admin["is_active"] for admin in data["data"])


# ==================== 获取管理员详情测试 ====================


@pytest.mark.asyncio
async def test_get_admin_detail(client: AsyncClient, db_session: AsyncSession):
    """测试获取管理员详情."""
    # 创建管理员
    admin = await create_test_admin(db_session, username="detail_admin", name="Detail Admin")

    # 获取详情
    response = await client.get(
        f"/api/admin/admins/{admin.id}",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["username"] == "detail_admin"
    assert data["data"]["name"] == "Detail Admin"


@pytest.mark.asyncio
async def test_get_admin_detail_not_found(client: AsyncClient):
    """测试获取不存在的管理员详情."""
    response = await client.get(
        "/api/admin/admins/9999",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
    )
    assert response.status_code == 404


# ==================== 修改管理员信息测试 ====================


@pytest.mark.asyncio
async def test_update_admin(client: AsyncClient, db_session: AsyncSession):
    """测试修改管理员信息."""
    # 创建管理员
    admin = await create_test_admin(db_session, username="update_test", name="Original Name")
    admin_id = admin.id

    # 修改信息
    response = await client.put(
        f"/api/admin/admins/{admin_id}",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
        json={"name": "Updated Name", "remark": "Updated remark"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["name"] == "Updated Name"
    assert data["data"]["remark"] == "Updated remark"

    # 验证数据库已更新（需要刷新会话）
    await db_session.rollback()
    result = await db_session.execute(select(Admin).where(Admin.id == admin_id))
    updated_admin = result.scalar_one()
    assert updated_admin.name == "Updated Name"
    assert updated_admin.remark == "Updated remark"


@pytest.mark.asyncio
async def test_update_admin_not_found(client: AsyncClient):
    """测试修改不存在的管理员."""
    response = await client.put(
        "/api/admin/admins/9999",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
        json={"name": "New Name"},
    )
    assert response.status_code == 404


# ==================== 删除管理员测试 ====================


@pytest.mark.asyncio
async def test_delete_admin(db_session: AsyncSession, client: AsyncClient):
    """测试删除管理员."""
    # 创建管理员
    admin = await create_test_admin(db_session, username="delete_test")

    # 删除管理员
    response = await client.delete(
        f"/api/admin/admins/{admin.id}",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200

    # 验证数据库中已删除
    result = await db_session.execute(select(Admin).where(Admin.id == admin.id))
    deleted_admin = result.scalar_one_or_none()
    assert deleted_admin is None


@pytest.mark.asyncio
async def test_delete_admin_not_found(client: AsyncClient):
    """测试删除不存在的管理员."""
    response = await client.delete(
        "/api/admin/admins/9999",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
    )
    assert response.status_code == 404


# ==================== 停用/启用管理员测试 ====================


@pytest.mark.asyncio
async def test_deactivate_admin(client: AsyncClient, db_session: AsyncSession):
    """测试停用管理员."""
    # 创建管理员
    admin = await create_test_admin(db_session, username="deactivate_test", is_active=True)
    admin_id = admin.id

    # 停用管理员
    response = await client.post(
        f"/api/admin/admins/{admin_id}/deactivate",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["is_active"] is False

    # 验证数据库已更新（需要刷新会话）
    await db_session.rollback()
    result = await db_session.execute(select(Admin).where(Admin.id == admin_id))
    updated_admin = result.scalar_one()
    assert updated_admin.is_active is False


@pytest.mark.asyncio
async def test_activate_admin(client: AsyncClient, db_session: AsyncSession):
    """测试启用管理员."""
    # 创建已停用的管理员
    admin = await create_test_admin(db_session, username="activate_test", is_active=False)
    admin_id = admin.id

    # 启用管理员
    response = await client.post(
        f"/api/admin/admins/{admin_id}/activate",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["is_active"] is True

    # 验证数据库已更新（需要刷新会话）
    await db_session.rollback()
    result = await db_session.execute(select(Admin).where(Admin.id == admin_id))
    updated_admin = result.scalar_one()
    assert updated_admin.is_active is True


# ==================== 修改密码测试 ====================


@pytest.mark.asyncio
async def test_change_password(client: AsyncClient, db_session: AsyncSession):
    """测试管理员修改自己的密码."""
    # 创建管理员
    admin = await create_test_admin(db_session, username="change_pwd_test", password="old_password")
    admin_id = admin.id

    # 生成 Token
    token = create_admin_token(admin_id)

    # 修改密码
    response = await client.post(
        "/api/admin/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"new_password": "new_password"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200

    # 验证密码已更新（需要刷新会话）
    await db_session.rollback()
    result = await db_session.execute(select(Admin).where(Admin.id == admin_id))
    updated_admin = result.scalar_one()
    assert verify_password("new_password", updated_admin.password_hash)

    # 验证旧密码无法登录
    response = await client.post(
        "/api/auth/admin/login",
        json={"username": "change_pwd_test", "password": "old_password"},
    )
    assert response.status_code == 401

    # 验证新密码可以登录
    response = await client.post(
        "/api/auth/admin/login",
        json={"username": "change_pwd_test", "password": "new_password"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_change_password_unauthorized(client: AsyncClient):
    """测试未登录修改密码."""
    response = await client.post(
        "/api/admin/change-password",
        json={"new_password": "new_password"},
    )
    assert response.status_code == 401


# ==================== 超级管理员强制修改密码测试 ====================


@pytest.mark.asyncio
async def test_force_change_password(client: AsyncClient, db_session: AsyncSession):
    """测试超级管理员强制修改密码."""
    # 创建管理员
    admin = await create_test_admin(db_session, username="force_pwd_test", password="old_password")
    admin_id = admin.id

    # 强制修改密码
    response = await client.post(
        f"/api/admin/admins/{admin_id}/force-change-password",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
        json={"new_password": "forced_new_password"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200

    # 验证密码已更新（需要刷新会话）
    await db_session.rollback()
    result = await db_session.execute(select(Admin).where(Admin.id == admin_id))
    updated_admin = result.scalar_one()
    assert verify_password("forced_new_password", updated_admin.password_hash)

    # 验证新密码可以登录
    response = await client.post(
        "/api/auth/admin/login",
        json={"username": "force_pwd_test", "password": "forced_new_password"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_force_change_password_not_found(client: AsyncClient):
    """测试强制修改不存在的管理员密码."""
    response = await client.post(
        "/api/admin/admins/9999/force-change-password",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
        json={"new_password": "new_password"},
    )
    assert response.status_code == 404


# ==================== 验证管理员 Token 测试 ====================


@pytest.mark.asyncio
async def test_verify_admin_token_success(client: AsyncClient, db_session: AsyncSession):
    """测试验证有效的管理员 Token."""
    # 创建管理员
    admin = await create_test_admin(db_session, username="verify_test", name="Verify Test")

    # 生成 Token
    token = create_admin_token(admin.id)

    # 验证 Token
    response = await client.post(
        "/api/auth/admin/verify",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["valid"] is True
    assert data["data"]["admin_info"] is not None
    assert data["data"]["admin_info"]["username"] == "verify_test"


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
async def test_verify_admin_token_deactivated(client: AsyncClient, db_session: AsyncSession):
    """测试验证已停用管理员的 Token."""
    # 创建已停用的管理员
    admin = await create_test_admin(db_session, username="deactivated_verify", is_active=False)

    # 生成 Token
    token = create_admin_token(admin.id)

    # 验证 Token
    response = await client.post(
        "/api/auth/admin/verify",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 403
    assert data["data"]["valid"] is False


@pytest.mark.asyncio
async def test_verify_admin_token_missing_header(client: AsyncClient):
    """测试缺少 Authorization 头."""
    response = await client.post("/api/auth/admin/verify")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_verify_admin_token_wrong_format(client: AsyncClient):
    """测试错误的 Authorization 格式."""
    response = await client.post(
        "/api/auth/admin/verify",
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 401
    assert data["data"]["valid"] is False
