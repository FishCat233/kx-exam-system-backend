"""管理员系统相关测试."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

import app.database as database_module
from app.config import settings
from app.main import init_super_admin
from app.models import Admin, AdminRole, Exam
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
    role: AdminRole = AdminRole.ADMIN,
    remark: str = "Test remark",
) -> Admin:
    """创建测试管理员账号."""
    admin = Admin(
        username=username,
        password_hash=get_password_hash(password),
        name=name,
        is_active=is_active,
        role=role,
        remark=remark,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


# ==================== 超级管理员认证测试 ====================


@pytest.mark.asyncio
async def test_super_admin_auth_success(client: AsyncClient, db_session: AsyncSession):
    """测试超级管理员认证成功."""
    # 创建超级管理员
    super_admin = await create_test_admin(
        db_session,
        username="super_admin_test",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )

    # 使用超级管理员 Token
    token = create_admin_token(super_admin.id)

    response = await client.post(
        "/api/admin/admins",
        headers={"Authorization": f"Bearer {token}"},
        json={"username": "new_admin", "password": "new_password", "name": "New Admin"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_super_admin_auth_failure(client: AsyncClient, db_session: AsyncSession):
    """测试普通管理员无法执行超级管理员操作."""
    # 创建普通管理员
    admin = await create_test_admin(
        db_session,
        username="regular_admin",
        password="password",
        role=AdminRole.ADMIN,
    )

    # 使用普通管理员 Token
    token = create_admin_token(admin.id)

    response = await client.post(
        "/api/admin/admins",
        headers={"Authorization": f"Bearer {token}"},
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
    assert data["data"]["admin"]["role"] == "admin"


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
    # 创建超级管理员
    super_admin = await create_test_admin(
        db_session,
        username="super_admin_for_create",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(super_admin.id)

    response = await client.post(
        "/api/admin/admins",
        headers={"Authorization": f"Bearer {token}"},
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
    assert data["data"]["role"] == "admin"

    # 验证数据库中有记录
    result = await db_session.execute(select(Admin).where(Admin.username == "new_admin"))
    admin = result.scalar_one_or_none()
    assert admin is not None
    assert admin.username == "new_admin"
    assert admin.role == AdminRole.ADMIN
    assert verify_password("new_password", admin.password_hash)


@pytest.mark.asyncio
async def test_create_admin_duplicate_username(client: AsyncClient, db_session: AsyncSession):
    """测试创建重复账号名的管理员."""
    # 先创建一个管理员
    await create_test_admin(db_session, username="duplicate_user")

    # 创建超级管理员
    super_admin = await create_test_admin(
        db_session,
        username="super_for_duplicate",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(super_admin.id)

    # 尝试创建相同账号名的管理员
    response = await client.post(
        "/api/admin/admins",
        headers={"Authorization": f"Bearer {token}"},
        json={"username": "duplicate_user", "password": "password"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_admin_validation_error(client: AsyncClient, db_session: AsyncSession):
    """测试创建管理员参数验证失败."""
    # 创建超级管理员
    super_admin = await create_test_admin(
        db_session,
        username="super_for_validation",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(super_admin.id)

    # 缺少 username
    response = await client.post(
        "/api/admin/admins",
        headers={"Authorization": f"Bearer {token}"},
        json={"password": "password"},
    )
    assert response.status_code == 422

    # 缺少 password
    response = await client.post(
        "/api/admin/admins",
        headers={"Authorization": f"Bearer {token}"},
        json={"username": "test_user"},
    )
    assert response.status_code == 422


# ==================== 获取管理员列表测试 ====================


@pytest.mark.asyncio
async def test_list_admins(client: AsyncClient, db_session: AsyncSession):
    """测试获取管理员列表."""
    # 创建超级管理员
    super_admin = await create_test_admin(
        db_session,
        username="super_for_list",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(super_admin.id)

    # 创建几个管理员
    await create_test_admin(db_session, username="admin1", name="Admin 1")
    await create_test_admin(db_session, username="admin2", name="Admin 2")
    await create_test_admin(db_session, username="admin3", name="Admin 3", is_active=False)

    # 获取列表
    response = await client.get(
        "/api/admin/admins",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert isinstance(data["data"], list)
    assert len(data["data"]) >= 4  # 包含超级管理员和创建的3个


@pytest.mark.asyncio
async def test_list_admins_filter_by_active(client: AsyncClient, db_session: AsyncSession):
    """测试按状态筛选管理员列表."""
    # 创建超级管理员
    super_admin = await create_test_admin(
        db_session,
        username="super_for_filter",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(super_admin.id)

    # 创建管理员
    await create_test_admin(db_session, username="active_admin", is_active=True)
    await create_test_admin(db_session, username="inactive_admin", is_active=False)

    # 获取启用的管理员
    response = await client.get(
        "/api/admin/admins?is_active=true",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert all(admin["is_active"] for admin in data["data"])

    # 获取停用的管理员
    response = await client.get(
        "/api/admin/admins?is_active=false",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert all(not admin["is_active"] for admin in data["data"])


# ==================== 获取管理员详情测试 ====================


@pytest.mark.asyncio
async def test_get_admin_detail(client: AsyncClient, db_session: AsyncSession):
    """测试获取管理员详情."""
    # 创建超级管理员
    super_admin = await create_test_admin(
        db_session,
        username="super_for_detail",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(super_admin.id)

    # 创建管理员
    admin = await create_test_admin(db_session, username="detail_admin", name="Detail Admin")

    # 获取详情
    response = await client.get(
        f"/api/admin/admins/{admin.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["username"] == "detail_admin"
    assert data["data"]["name"] == "Detail Admin"
    assert data["data"]["role"] == "admin"


@pytest.mark.asyncio
async def test_get_admin_detail_not_found(client: AsyncClient, db_session: AsyncSession):
    """测试获取不存在的管理员详情."""
    # 创建超级管理员
    super_admin = await create_test_admin(
        db_session,
        username="super_for_not_found",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(super_admin.id)

    response = await client.get(
        "/api/admin/admins/9999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


# ==================== 修改管理员信息测试 ====================


@pytest.mark.asyncio
async def test_update_admin(client: AsyncClient, db_session: AsyncSession):
    """测试修改管理员信息."""
    # 创建超级管理员
    super_admin = await create_test_admin(
        db_session,
        username="super_for_update",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(super_admin.id)

    # 创建管理员
    admin = await create_test_admin(db_session, username="update_test", name="Original Name")
    admin_id = admin.id

    # 修改信息
    response = await client.put(
        f"/api/admin/admins/{admin_id}",
        headers={"Authorization": f"Bearer {token}"},
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
async def test_update_admin_not_found(client: AsyncClient, db_session: AsyncSession):
    """测试修改不存在的管理员."""
    # 创建超级管理员
    super_admin = await create_test_admin(
        db_session,
        username="super_for_update_not_found",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(super_admin.id)

    response = await client.put(
        "/api/admin/admins/9999",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "New Name"},
    )
    assert response.status_code == 404


# ==================== 删除管理员测试 ====================


@pytest.mark.asyncio
async def test_delete_admin(db_session: AsyncSession, client: AsyncClient):
    """测试删除管理员."""
    # 创建超级管理员
    super_admin = await create_test_admin(
        db_session,
        username="super_for_delete",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(super_admin.id)

    # 创建管理员
    admin = await create_test_admin(db_session, username="delete_test")

    # 删除管理员
    response = await client.delete(
        f"/api/admin/admins/{admin.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200

    # 验证数据库中已删除
    result = await db_session.execute(select(Admin).where(Admin.id == admin.id))
    deleted_admin = result.scalar_one_or_none()
    assert deleted_admin is None


@pytest.mark.asyncio
async def test_delete_admin_not_found(client: AsyncClient, db_session: AsyncSession):
    """测试删除不存在的管理员."""
    # 创建超级管理员
    super_admin = await create_test_admin(
        db_session,
        username="super_for_delete_not_found",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(super_admin.id)

    response = await client.delete(
        "/api/admin/admins/9999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


# ==================== 停用/启用管理员测试 ====================


@pytest.mark.asyncio
async def test_deactivate_admin(client: AsyncClient, db_session: AsyncSession):
    """测试停用管理员."""
    # 创建超级管理员
    super_admin = await create_test_admin(
        db_session,
        username="super_for_deactivate",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(super_admin.id)

    # 创建管理员
    admin = await create_test_admin(db_session, username="deactivate_test", is_active=True)
    admin_id = admin.id

    # 停用管理员
    response = await client.post(
        f"/api/admin/admins/{admin_id}/deactivate",
        headers={"Authorization": f"Bearer {token}"},
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
    # 创建超级管理员
    super_admin = await create_test_admin(
        db_session,
        username="super_for_activate",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(super_admin.id)

    # 创建已停用的管理员
    admin = await create_test_admin(db_session, username="activate_test", is_active=False)
    admin_id = admin.id

    # 启用管理员
    response = await client.post(
        f"/api/admin/admins/{admin_id}/activate",
        headers={"Authorization": f"Bearer {token}"},
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
        json={"old_password": "old_password", "new_password": "new_password"},
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
    # 创建超级管理员
    super_admin = await create_test_admin(
        db_session,
        username="super_for_force_pwd",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )
    super_token = create_admin_token(super_admin.id)

    # 创建管理员
    admin = await create_test_admin(db_session, username="force_pwd_test", password="old_password")
    admin_id = admin.id

    # 强制修改密码
    response = await client.post(
        f"/api/admin/admins/{admin_id}/force-change-password",
        headers={"Authorization": f"Bearer {super_token}"},
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
async def test_force_change_password_not_found(client: AsyncClient, db_session: AsyncSession):
    """测试强制修改不存在的管理员密码."""
    # 创建超级管理员
    super_admin = await create_test_admin(
        db_session,
        username="super_for_force_pwd_not_found",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(super_admin.id)

    response = await client.post(
        "/api/admin/admins/9999/force-change-password",
        headers={"Authorization": f"Bearer {token}"},
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
    assert data["data"]["admin_info"]["role"] == "admin"


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


# ==================== 超级管理员角色登录测试 ====================


@pytest.mark.asyncio
async def test_super_admin_login(client: AsyncClient, db_session: AsyncSession):
    """测试超级管理员登录."""
    # 创建超级管理员
    await create_test_admin(
        db_session,
        username="super_login_test",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )

    # 登录
    response = await client.post(
        "/api/auth/admin/login",
        json={"username": "super_login_test", "password": "super_password"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "token" in data["data"]
    assert data["data"]["admin"]["username"] == "super_login_test"
    assert data["data"]["admin"]["role"] == "super_admin"


@pytest.mark.asyncio
async def test_init_super_admin_uses_configured_credentials(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """测试启动时会根据配置初始化高权限管理员账号."""
    testing_session_local = sessionmaker(
        db_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    monkeypatch.setattr(database_module, "AsyncSessionLocal", testing_session_local)
    monkeypatch.setattr(settings, "super_admin_username", "configured_admin")
    monkeypatch.setattr(settings, "super_admin_password", "configured_password")
    monkeypatch.setattr(settings, "super_admin_name", "配置超级管理员")

    await init_super_admin()

    result = await db_session.execute(select(Admin).where(Admin.username == "configured_admin"))
    admin = result.scalar_one_or_none()

    assert admin is not None
    assert admin.role == AdminRole.SUPER_ADMIN
    assert admin.name == "配置超级管理员"
    assert admin.is_active is True
    assert verify_password("configured_password", admin.password_hash)


# ==================== 高级管理员角色测试 ====================


@pytest.mark.asyncio
async def test_create_admin_with_senior_role(client: AsyncClient, db_session: AsyncSession):
    """测试创建高级管理员（senior_admin）账号."""
    super_admin = await create_test_admin(
        db_session,
        username="super_for_senior_create",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(super_admin.id)

    response = await client.post(
        "/api/admin/admins",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "username": "senior_new",
            "password": "senior_password",
            "name": "高级管理员",
            "role": "senior_admin",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["role"] == "senior_admin"

    result = await db_session.execute(select(Admin).where(Admin.username == "senior_new"))
    created = result.scalar_one()
    assert created.role == AdminRole.SENIOR_ADMIN


@pytest.mark.asyncio
async def test_update_admin_role(client: AsyncClient, db_session: AsyncSession):
    """测试修改管理员角色（升级为高级管理员）."""
    super_admin = await create_test_admin(
        db_session,
        username="super_for_role_update",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(super_admin.id)
    admin = await create_test_admin(db_session, username="role_update_target")
    admin_id = admin.id

    response = await client.put(
        f"/api/admin/admins/{admin_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "senior_admin"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["role"] == "senior_admin"

    await db_session.rollback()
    result = await db_session.execute(select(Admin).where(Admin.id == admin_id))
    updated = result.scalar_one()
    assert updated.role == AdminRole.SENIOR_ADMIN


@pytest.mark.asyncio
async def test_senior_admin_cannot_manage_admins(client: AsyncClient, db_session: AsyncSession):
    """测试高级管理员不能管理管理员账号."""
    senior_admin = await create_test_admin(
        db_session,
        username="senior_no_admin_manage",
        password="senior_password",
        role=AdminRole.SENIOR_ADMIN,
    )
    token = create_admin_token(senior_admin.id)

    response = await client.post(
        "/api/admin/admins",
        headers={"Authorization": f"Bearer {token}"},
        json={"username": "should_fail", "password": "password123"},
    )
    assert response.status_code == 403

    response = await client.get(
        "/api/admin/admins",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_senior_admin_can_create_exam(client: AsyncClient, db_session: AsyncSession):
    """测试高级管理员可以创建考试."""
    senior_admin = await create_test_admin(
        db_session,
        username="senior_can_exam",
        password="senior_password",
        role=AdminRole.SENIOR_ADMIN,
    )
    token = create_admin_token(senior_admin.id)

    start_time = datetime.now(UTC) + timedelta(minutes=60)
    end_time = datetime.now(UTC) + timedelta(minutes=180)
    response = await client.post(
        "/api/exams",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "高级管理员创建的考试",
            "subject": "C语言",
            "duration": 120,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        },
    )
    assert response.status_code == 200
    assert response.json()["code"] == 200


@pytest.mark.asyncio
async def test_senior_admin_can_import_students(client: AsyncClient, db_session: AsyncSession):
    """测试高级管理员可以导入考生."""
    senior_admin = await create_test_admin(
        db_session,
        username="senior_can_students",
        password="senior_password",
        role=AdminRole.SENIOR_ADMIN,
    )
    token = create_admin_token(senior_admin.id)

    exam = Exam(
        name="考生导入测试考试",
        subject="C语言",
        duration=120,
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC) + timedelta(hours=2),
    )
    db_session.add(exam)
    await db_session.commit()
    await db_session.refresh(exam)

    response = await client.post(
        f"/api/admin/exams/{exam.id}/students",
        headers={"Authorization": f"Bearer {token}"},
        json={"students": [{"student_id": "2024101", "name": "测试考生"}]},
    )
    assert response.status_code == 200
    assert response.json()["code"] == 200


# ==================== 超级管理员自保护测试 ====================


@pytest.mark.asyncio
async def test_cannot_deactivate_self(client: AsyncClient, db_session: AsyncSession):
    """测试超级管理员不能停用自己."""
    super_admin = await create_test_admin(
        db_session,
        username="super_self_deactivate",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(super_admin.id)

    response = await client.post(
        f"/api/admin/admins/{super_admin.id}/deactivate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert "不能停用自己" in response.json()["message"]

    response = await client.put(
        f"/api/admin/admins/{super_admin.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"is_active": False},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_cannot_delete_self(client: AsyncClient, db_session: AsyncSession):
    """测试超级管理员不能删除自己."""
    super_admin = await create_test_admin(
        db_session,
        username="super_self_delete",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(super_admin.id)

    response = await client.delete(
        f"/api/admin/admins/{super_admin.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert "不能删除自己" in response.json()["message"]


@pytest.mark.asyncio
async def test_cannot_demote_last_super_admin(client: AsyncClient, db_session: AsyncSession):
    """测试不能降级最后一个超级管理员."""
    super_admin = await create_test_admin(
        db_session,
        username="super_last_one",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(super_admin.id)

    response = await client.put(
        f"/api/admin/admins/{super_admin.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "admin"},
    )
    assert response.status_code == 400
    assert "最后一个超级管理员" in response.json()["message"]


@pytest.mark.asyncio
async def test_can_demote_super_admin_when_multiple(client: AsyncClient, db_session: AsyncSession):
    """测试存在多个超级管理员时可以降级其中一个."""
    super_admin = await create_test_admin(
        db_session,
        username="super_demote_self",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )
    other_super = await create_test_admin(
        db_session,
        username="super_demote_other",
        password="super_password",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(super_admin.id)

    response = await client.put(
        f"/api/admin/admins/{other_super.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "senior_admin"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["role"] == "senior_admin"
