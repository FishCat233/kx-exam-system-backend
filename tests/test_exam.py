"""考试相关功能测试."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Exam, ExamStatus, Problem

# ==================== 辅助函数 ====================


async def create_admin_token(
    client: AsyncClient, db_session: AsyncSession, suffix: str = ""
) -> str:
    """创建管理员 Token 并返回 Token 值."""
    # 使用唯一名称和不同的过期时间避免 token 冲突
    unique_name = f"Test Admin {datetime.now(UTC).timestamp()} {suffix}"
    # 使用不同的过期时间来确保 JWT token 唯一
    expires_at = (
        datetime.now(UTC) + timedelta(days=1, seconds=hash(unique_name) % 1000)
    ).isoformat()
    response = await client.post(
        "/api/admin/tokens",
        headers={"X-Super-Admin-Key": settings.super_admin_key},
        json={"name": unique_name, "expires_at": expires_at},
    )
    assert response.status_code == 200
    return response.json()["data"]["token"]


async def create_test_exam(
    client: AsyncClient,
    db_session: AsyncSession,
    name: str = "Test Exam",
    start_offset_minutes: int = 60,
    end_offset_minutes: int = 180,
) -> int:
    """创建测试考试并返回考试 ID."""
    token = await create_admin_token(client, db_session, name)

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
            "pledge_content": "# 考前承诺书\n\n我承诺...",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["exam_id"]


# ==================== 获取考试列表测试 ====================


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
    # 创建两个考试
    await create_test_exam(client, db_session, "Exam 1")
    await create_test_exam(client, db_session, "Exam 2")

    response = await client.get("/api/exams")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert len(data["data"]) == 2

    # 验证按创建时间倒序排列
    assert data["data"][0]["name"] == "Exam 2"
    assert data["data"][1]["name"] == "Exam 1"

    # 验证不包含 pledge_content
    assert "pledge_content" not in data["data"][0]


# ==================== 获取考试详情测试 ====================


@pytest.mark.asyncio
async def test_get_exam_detail(client: AsyncClient, db_session: AsyncSession):
    """测试获取考试详情."""
    exam_id = await create_test_exam(client, db_session, "Detail Test Exam")

    response = await client.get(f"/api/exams/{exam_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["id"] == exam_id
    assert data["data"]["name"] == "Detail Test Exam"
    assert data["data"]["subject"] == "C Programming"
    assert data["data"]["duration"] == 120
    assert data["data"]["status"] == "not_started"
    assert data["data"]["pledge_content"] == "# 考前承诺书\n\n我承诺..."
    # problems 字段在考试详情中返回
    assert "problems" in data["data"]
    assert isinstance(data["data"]["problems"], list)


@pytest.mark.asyncio
async def test_get_exam_not_found(client: AsyncClient):
    """测试获取不存在的考试详情."""
    response = await client.get("/api/exams/9999")
    assert response.status_code == 404
    data = response.json()
    assert data["code"] == 404
    assert "not found" in data["message"].lower()


# ==================== 创建考试测试 ====================


@pytest.mark.asyncio
async def test_create_exam_success(client: AsyncClient, db_session: AsyncSession):
    """测试成功创建考试."""
    token = await create_admin_token(client, db_session)

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
            "pledge_content": "# 承诺书",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "exam_id" in data["data"]

    # 验证数据库中有记录
    result = await db_session.execute(select(Exam).where(Exam.id == data["data"]["exam_id"]))
    exam = result.scalar_one_or_none()
    assert exam is not None
    assert exam.name == "New Exam"
    assert exam.status == ExamStatus.NOT_STARTED


@pytest.mark.asyncio
async def test_create_exam_unauthorized(client: AsyncClient):
    """测试未授权创建考试."""
    start_time = datetime.now(UTC) + timedelta(hours=1)
    end_time = datetime.now(UTC) + timedelta(hours=3)

    response = await client.post(
        "/api/exams",
        json={
            "name": "New Exam",
            "subject": "C Programming",
            "duration": 120,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        },
    )
    # 缺少 Authorization 头会导致 401（未授权）
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_exam_invalid_time_range(client: AsyncClient, db_session: AsyncSession):
    """测试创建考试时间范围无效."""
    token = await create_admin_token(client, db_session)

    start_time = datetime.now(UTC) + timedelta(hours=3)
    end_time = datetime.now(UTC) + timedelta(hours=1)  # 结束时间早于开始时间

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
    assert response.status_code == 422
    data = response.json()
    assert "End time must be after start time" in data["message"]


@pytest.mark.asyncio
async def test_create_exam_validation_error(client: AsyncClient, db_session: AsyncSession):
    """测试创建考试参数验证失败."""
    token = await create_admin_token(client, db_session)

    response = await client.post(
        "/api/exams",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "",  # 空名称
            "subject": "C Programming",
            "duration": 120,
        },
    )
    assert response.status_code == 422


# ==================== 更新考试测试 ====================


@pytest.mark.asyncio
async def test_update_exam_success(client: AsyncClient, db_session: AsyncSession):
    """测试成功更新考试."""
    exam_id = await create_test_exam(client, db_session, "Original Name")
    token = await create_admin_token(client, db_session, "update")

    response = await client.put(
        f"/api/exams/{exam_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Updated Name"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["name"] == "Updated Name"
    assert data["data"]["subject"] == "C Programming"  # 未修改的字段保持不变


@pytest.mark.asyncio
async def test_update_exam_not_found(client: AsyncClient, db_session: AsyncSession):
    """测试更新不存在的考试."""
    token = await create_admin_token(client, db_session, "notfound")

    response = await client.put(
        "/api/exams/9999",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Updated Name"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_exam_already_started(client: AsyncClient, db_session: AsyncSession):
    """测试更新已开始的考试."""
    # 创建一个考试并手动设置为已开始状态
    exam_id = await create_test_exam(client, db_session, "Started Exam")

    result = await db_session.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one()
    exam.status = ExamStatus.IN_PROGRESS
    await db_session.commit()

    token = await create_admin_token(client, db_session, "started")

    response = await client.put(
        f"/api/exams/{exam_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "New Name"},
    )
    assert response.status_code == 400
    data = response.json()
    assert "already started" in data["message"].lower()


# ==================== 删除考试测试 ====================


@pytest.mark.asyncio
async def test_delete_exam_success(client: AsyncClient, db_session: AsyncSession):
    """测试成功删除考试."""
    exam_id = await create_test_exam(client, db_session, "Exam to Delete")
    token = await create_admin_token(client, db_session, "delete")

    response = await client.delete(
        f"/api/exams/{exam_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "deleted successfully" in data["data"]["message"].lower()

    # 验证数据库中已删除
    result = await db_session.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one_or_none()
    assert exam is None


@pytest.mark.asyncio
async def test_delete_exam_not_found(client: AsyncClient, db_session: AsyncSession):
    """测试删除不存在的考试."""
    token = await create_admin_token(client, db_session, "notfound")

    response = await client.delete(
        "/api/exams/9999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_exam_already_started(client: AsyncClient, db_session: AsyncSession):
    """测试删除已开始的考试."""
    # 创建一个考试并手动设置为已开始状态
    exam_id = await create_test_exam(client, db_session, "Started Exam")

    result = await db_session.execute(select(Exam).where(Exam.id == exam_id))
    exam = result.scalar_one()
    exam.status = ExamStatus.IN_PROGRESS
    await db_session.commit()

    token = await create_admin_token(client, db_session, "started")

    response = await client.delete(
        f"/api/exams/{exam_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    data = response.json()
    assert "already started" in data["message"].lower()


@pytest.mark.asyncio
async def test_delete_exam_cascade_problems(client: AsyncClient, db_session: AsyncSession):
    """测试删除考试时级联删除题目."""
    exam_id = await create_test_exam(client, db_session, "Exam with Problems")
    token = await create_admin_token(client, db_session, "cascade")

    # 添加题目到考试
    problem = Problem(
        exam_id=exam_id,
        title="Test Problem",
        content="Problem content",
        order_num=1,
    )
    db_session.add(problem)
    await db_session.commit()

    # 验证题目已创建
    result = await db_session.execute(select(Problem).where(Problem.exam_id == exam_id))
    assert result.scalar_one_or_none() is not None

    # 删除考试
    response = await client.delete(
        f"/api/exams/{exam_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    # 验证题目也被删除
    result = await db_session.execute(select(Problem).where(Problem.exam_id == exam_id))
    assert result.scalar_one_or_none() is None


# ==================== 获取考试题目列表测试 ====================


@pytest.mark.asyncio
async def test_get_exam_problems_empty(client: AsyncClient, db_session: AsyncSession):
    """测试获取没有题目的考试."""
    exam_id = await create_test_exam(client, db_session)

    response = await client.get(f"/api/exams/{exam_id}/problems")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"] == []


@pytest.mark.asyncio
async def test_get_exam_problems_with_data(client: AsyncClient, db_session: AsyncSession):
    """测试获取有题目的考试."""
    exam_id = await create_test_exam(client, db_session, "Exam with Problems")

    # 添加题目
    problem1 = Problem(
        exam_id=exam_id,
        title="Problem 1",
        content="Content 1",
        order_num=2,
    )
    problem2 = Problem(
        exam_id=exam_id,
        title="Problem 2",
        content="Content 2",
        order_num=1,
    )
    db_session.add(problem1)
    db_session.add(problem2)
    await db_session.commit()

    response = await client.get(f"/api/exams/{exam_id}/problems")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert len(data["data"]) == 2

    # 验证按 order_num 排序
    assert data["data"][0]["title"] == "Problem 2"
    assert data["data"][1]["title"] == "Problem 1"


@pytest.mark.asyncio
async def test_get_exam_problems_exam_not_found(client: AsyncClient):
    """测试获取不存在的考试的题目列表."""
    response = await client.get("/api/exams/9999/problems")
    assert response.status_code == 404
