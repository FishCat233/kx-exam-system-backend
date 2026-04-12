"""题目相关功能测试."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Problem, StudentCode


async def create_admin_token(
    client: AsyncClient, db_session: AsyncSession, suffix: str = ""
) -> str:
    """创建管理员 Token 并返回 Token 值."""
    unique_name = f"Test Admin {datetime.now(UTC).timestamp()} {suffix}"
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
            "pledge_content": "# 考前承诺书",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["exam_id"]


async def create_test_problem(
    client: AsyncClient,
    db_session: AsyncSession,
    exam_id: int,
    title: str = "Test Problem",
    content: str = "Problem content",
    order_num: int = 1,
) -> int:
    """创建测试题目并返回题目 ID."""
    token = await create_admin_token(client, db_session, f"problem_{title}")
    response = await client.post(
        f"/api/exams/{exam_id}/problems",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": title, "content": content, "order_num": order_num},
    )
    assert response.status_code == 200
    return response.json()["data"]["problem_id"]


@pytest.mark.asyncio
async def test_create_problem_success(client: AsyncClient, db_session: AsyncSession):
    """测试成功添加题目."""
    exam_id = await create_test_exam(client, db_session, "Exam for Problem")
    token = await create_admin_token(client, db_session, "create_problem")
    response = await client.post(
        f"/api/exams/{exam_id}/problems",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Hello World", "content": "Write a program", "order_num": 1},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "problem_id" in data["data"]
    result = await db_session.execute(
        select(Problem).where(Problem.id == data["data"]["problem_id"])
    )
    problem = result.scalar_one_or_none()
    assert problem is not None
    assert problem.title == "Hello World"


@pytest.mark.asyncio
async def test_create_problem_exam_not_found(client: AsyncClient, db_session: AsyncSession):
    """测试为不存在的考试添加题目."""
    token = await create_admin_token(client, db_session, "exam_not_found")
    response = await client.post(
        "/api/exams/9999/problems",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Test", "content": "Content", "order_num": 1},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_problem_unauthorized(client: AsyncClient, db_session: AsyncSession):
    """测试未授权添加题目."""
    exam_id = await create_test_exam(client, db_session, "Exam for Unauthorized")
    response = await client.post(
        f"/api/exams/{exam_id}/problems",
        json={"title": "Test", "content": "Content", "order_num": 1},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_problem_validation_error(client: AsyncClient, db_session: AsyncSession):
    """测试添加题目参数验证失败."""
    exam_id = await create_test_exam(client, db_session, "Exam for Validation")
    token = await create_admin_token(client, db_session, "validation")
    response = await client.post(
        f"/api/exams/{exam_id}/problems",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "Content only", "order_num": 1},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_problem_success(client: AsyncClient, db_session: AsyncSession):
    """测试成功修改题目."""
    exam_id = await create_test_exam(client, db_session, "Exam for Update")
    problem_id = await create_test_problem(client, db_session, exam_id, "Original")
    token = await create_admin_token(client, db_session, "update_problem")
    response = await client.put(
        f"/api/problems/{problem_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Updated", "content": "Updated content"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["title"] == "Updated"


@pytest.mark.asyncio
async def test_update_problem_partial(client: AsyncClient, db_session: AsyncSession):
    """测试部分字段更新题目."""
    exam_id = await create_test_exam(client, db_session, "Exam for Partial")
    problem_id = await create_test_problem(client, db_session, exam_id, "Original", "Content", 1)
    token = await create_admin_token(client, db_session, "partial_update")
    response = await client.put(
        f"/api/problems/{problem_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "New Title"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["title"] == "New Title"
    assert data["data"]["content"] == "Content"


@pytest.mark.asyncio
async def test_update_problem_not_found(client: AsyncClient, db_session: AsyncSession):
    """测试修改不存在的题目."""
    token = await create_admin_token(client, db_session, "notfound")
    response = await client.put(
        "/api/problems/9999",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "New"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_problem_unauthorized(client: AsyncClient, db_session: AsyncSession):
    """测试未授权修改题目."""
    exam_id = await create_test_exam(client, db_session, "Exam for Unauthorized")
    problem_id = await create_test_problem(client, db_session, exam_id)
    response = await client.put(f"/api/problems/{problem_id}", json={"title": "New"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_problem_success(client: AsyncClient, db_session: AsyncSession):
    """测试成功删除题目."""
    exam_id = await create_test_exam(client, db_session, "Exam for Delete")
    problem_id = await create_test_problem(client, db_session, exam_id, "To Delete")
    token = await create_admin_token(client, db_session, "delete_problem")
    response = await client.delete(
        f"/api/problems/{problem_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    result = await db_session.execute(select(Problem).where(Problem.id == problem_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_problem_not_found(client: AsyncClient, db_session: AsyncSession):
    """测试删除不存在的题目."""
    token = await create_admin_token(client, db_session, "notfound")
    response = await client.delete(
        "/api/problems/9999", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_problem_unauthorized(client: AsyncClient, db_session: AsyncSession):
    """测试未授权删除题目."""
    exam_id = await create_test_exam(client, db_session, "Exam for Unauthorized Delete")
    problem_id = await create_test_problem(client, db_session, exam_id)
    response = await client.delete(f"/api/problems/{problem_id}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_problem_cascade_codes(client: AsyncClient, db_session: AsyncSession):
    """测试删除题目时级联删除关联代码."""
    exam_id = await create_test_exam(client, db_session, "Exam for Cascade")
    problem_id = await create_test_problem(client, db_session, exam_id, "With Codes")
    token = await create_admin_token(client, db_session, "cascade")
    code = StudentCode(student_id=1, problem_id=problem_id, code="int main() {}")
    db_session.add(code)
    await db_session.commit()
    response = await client.delete(
        f"/api/problems/{problem_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    result = await db_session.execute(
        select(StudentCode).where(StudentCode.problem_id == problem_id)
    )
    assert result.scalar_one_or_none() is None
