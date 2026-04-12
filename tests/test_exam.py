"""考试相关功能测试."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Admin, Exam, ExamStatus, Problem
from app.utils.auth import create_access_token, get_password_hash


async def create_test_admin(
    db_session: AsyncSession,
    username: str = "test_admin",
    password: str = "test_password",
) -> Admin:
    """创建测试管理员账号."""
    admin = Admin(
        username=username,
        password_hash=get_password_hash(password),
        name="Test Admin",
        is_active=True,
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
    admin = await create_test_admin(db_session, username=f"admin_{name.replace(' ', '_')}")
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
            "pledge_content": "# 考前承诺书",
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
    response = await client.get(f"/api/exams/{exam_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["id"] == exam_id
    assert data["data"]["name"] == "Detail Exam"


@pytest.mark.asyncio
async def test_get_exam_detail_not_found(client: AsyncClient):
    """测试获取不存在的考试详情."""
    response = await client.get("/api/exams/9999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_exam_success(client: AsyncClient, db_session: AsyncSession):
    """测试成功创建考试."""
    admin = await create_test_admin(db_session, username="create_exam_admin")
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
            "pledge_content": "# 考前承诺书",
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


@pytest.mark.asyncio
async def test_create_exam_invalid_time_range(client: AsyncClient, db_session: AsyncSession):
    """测试创建考试时间范围无效."""
    admin = await create_test_admin(db_session, username="invalid_time_admin")
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
            "pledge_content": "# 考前承诺书",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_exam_validation_error(client: AsyncClient, db_session: AsyncSession):
    """测试创建考试参数验证失败."""
    admin = await create_test_admin(db_session, username="validation_admin")
    token = create_admin_token(admin.id)
    response = await client.post(
        "/api/exams",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Invalid Exam"},
    )
    assert response.status_code == 422
