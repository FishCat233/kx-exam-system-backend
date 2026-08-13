"""考试相关功能测试."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Admin, AdminRole, Exam
from app.utils.auth import create_access_token, get_password_hash


async def create_test_admin(
    db_session: AsyncSession,
    username: str = "test_admin",
    password: str = "test_password",
    role: AdminRole = AdminRole.ADMIN,
) -> Admin:
    """创建测试管理员账号."""
    admin = Admin(
        username=username,
        password_hash=get_password_hash(password),
        name="Test Admin",
        is_active=True,
        role=role,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


def create_admin_token(admin_id: int) -> str:
    """创建管理员 JWT Token."""
    token_payload = {"type": "admin", "admin_id": admin_id}
    return create_access_token(token_payload)


async def create_test_exam(
    client: AsyncClient,
    db_session: AsyncSession,
    name: str = "Test Exam",
    start_offset_minutes: int = 60,
    end_offset_minutes: int = 180,
) -> int:
    """创建测试考试并返回考试 ID."""
    admin = await create_test_admin(
        db_session,
        username=f"admin_{name.replace(' ', '_')}",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(admin.id)
    start_time = datetime.now(UTC) + timedelta(minutes=start_offset_minutes)
    end_time = datetime.now(UTC) + timedelta(minutes=end_offset_minutes)
    response = await client.post(
        "/api/exams",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": name,
            "subject": "C Programming",
            "duration": 120,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["exam_id"]


@pytest.mark.asyncio
async def test_list_exams_empty(client: AsyncClient):
    """测试获取空考试列表."""
    response = await client.get("/api/exams")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"] == []


@pytest.mark.asyncio
async def test_list_exams_with_data(client: AsyncClient, db_session: AsyncSession):
    """测试获取有数据的考试列表."""
    exam1_id = await create_test_exam(client, db_session, "Exam 1")
    exam2_id = await create_test_exam(client, db_session, "Exam 2")
    response = await client.get("/api/exams")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert len(data["data"]) >= 2
    exam_ids = [exam["id"] for exam in data["data"]]
    assert exam1_id in exam_ids
    assert exam2_id in exam_ids


@pytest.mark.asyncio
async def test_get_exam_detail(client: AsyncClient, db_session: AsyncSession):
    """测试获取考试详情."""
    exam_id = await create_test_exam(client, db_session, "Detail Exam")
    admin = await create_test_admin(db_session, username="detail_admin", role=AdminRole.SUPER_ADMIN)
    token = create_admin_token(admin.id)
    response = await client.get(
        f"/api/exams/{exam_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["id"] == exam_id
    assert data["data"]["name"] == "Detail Exam"


@pytest.mark.asyncio
async def test_get_exam_detail_not_found(client: AsyncClient, db_session: AsyncSession):
    """测试获取不存在的考试详情."""
    admin = await create_test_admin(
        db_session, username="detail_404_admin", role=AdminRole.SUPER_ADMIN
    )
    token = create_admin_token(admin.id)
    response = await client.get("/api/exams/9999", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_exam_success(client: AsyncClient, db_session: AsyncSession):
    """测试成功创建考试."""
    admin = await create_test_admin(
        db_session,
        username="create_exam_admin",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(admin.id)
    start_time = datetime.now(UTC) + timedelta(hours=1)
    end_time = datetime.now(UTC) + timedelta(hours=3)
    response = await client.post(
        "/api/exams",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "New Exam",
            "subject": "C Programming",
            "duration": 120,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "exam_id" in data["data"]
    result = await db_session.execute(select(Exam).where(Exam.id == data["data"]["exam_id"]))
    exam = result.scalar_one_or_none()
    assert exam is not None
    assert exam.name == "New Exam"
    assert exam.duration == 120


@pytest.mark.asyncio
async def test_create_exam_duration_is_derived_from_time_range(
    client: AsyncClient, db_session: AsyncSession
):
    """测试创建考试时长由开始结束时间自动计算."""
    admin = await create_test_admin(
        db_session,
        username="derived_duration_admin",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(admin.id)
    start_time = datetime.now(UTC) + timedelta(hours=1)
    end_time = start_time + timedelta(minutes=95)

    response = await client.post(
        "/api/exams",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Derived Duration Exam",
            "subject": "C Programming",
            "duration": 1,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        },
    )

    assert response.status_code == 200
    exam_id = response.json()["data"]["exam_id"]
    result = await db_session.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()
    assert exam is not None
    assert exam.duration == 95


@pytest.mark.asyncio
async def test_create_exam_invalid_time_range(client: AsyncClient, db_session: AsyncSession):
    """测试创建考试时间范围无效."""
    admin = await create_test_admin(
        db_session,
        username="invalid_time_admin",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(admin.id)
    start_time = datetime.now(UTC) + timedelta(hours=3)
    end_time = datetime.now(UTC) + timedelta(hours=1)
    response = await client.post(
        "/api/exams",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Invalid Exam",
            "subject": "C Programming",
            "duration": 120,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert "考试结束时间必须在开始时间之后" in data["message"]


@pytest.mark.asyncio
async def test_create_exam_validation_error(client: AsyncClient, db_session: AsyncSession):
    """测试创建考试参数验证失败."""
    admin = await create_test_admin(
        db_session,
        username="validation_admin",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(admin.id)
    response = await client.post(
        "/api/exams",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Invalid Exam"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_exam_forbidden_for_regular_admin(
    client: AsyncClient, db_session: AsyncSession
):
    """测试普通管理员不能创建考试."""
    admin = await create_test_admin(db_session, username="regular_exam_admin")
    token = create_admin_token(admin.id)
    start_time = datetime.now(UTC) + timedelta(hours=1)
    end_time = datetime.now(UTC) + timedelta(hours=3)

    response = await client.post(
        "/api/exams",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Forbidden Exam",
            "subject": "C Programming",
            "duration": 120,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_exam_duration_is_derived_from_time_range(
    client: AsyncClient, db_session: AsyncSession
):
    """测试更新考试时间范围时会自动刷新时长."""
    admin = await create_test_admin(
        db_session,
        username="update_exam_duration_admin",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(admin.id)
    exam_id = await create_test_exam(client, db_session, "Update Duration Exam")
    start_time = datetime.now(UTC) + timedelta(hours=2)
    end_time = start_time + timedelta(minutes=150)

    response = await client.put(
        f"/api/exams/{exam_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration": 60,
        },
    )

    assert response.status_code == 200
    result = await db_session.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()
    assert exam is not None
    assert exam.duration == 150
