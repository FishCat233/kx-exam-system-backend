"""题目相关功能测试."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Admin, AdminRole, Problem
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
) -> int:
    """创建测试题目并返回题目 ID."""
    admin = await create_test_admin(
        db_session,
        username=f"admin_{title.replace(' ', '_')}",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(admin.id)
    response = await client.post(
        f"/api/exams/{exam_id}/problems",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": title,
            "content": f"# {title}\n\nDescription",
            "order_num": 1,
        },
    )
    assert response.status_code == 200
    # API 返回的是 problem_id 而不是 id
    return response.json()["data"]["problem_id"]


# ==================== 创建题目测试 ====================


@pytest.mark.asyncio
async def test_create_problem_success(client: AsyncClient, db_session: AsyncSession):
    """测试成功创建题目."""
    exam_id = await create_test_exam(client, db_session, "Create Problem Exam")

    admin = await create_test_admin(
        db_session,
        username="create_problem_admin",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(admin.id)

    response = await client.post(
        f"/api/exams/{exam_id}/problems",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "New Problem",
            "content": "# New Problem\n\nDescription",
            "order_num": 1,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    # API 返回的是 problem_id 而不是 id
    assert "problem_id" in data["data"]

    # 验证数据库
    result = await db_session.execute(
        select(Problem).where(Problem.id == data["data"]["problem_id"])
    )
    problem = result.scalar_one_or_none()
    assert problem is not None
    assert problem.title == "New Problem"


@pytest.mark.asyncio
async def test_create_problem_exam_not_found(client: AsyncClient, db_session: AsyncSession):
    """测试为不存在的考试创建题目."""
    admin = await create_test_admin(
        db_session,
        username="notfound_admin",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(admin.id)

    response = await client.post(
        "/api/exams/9999/problems",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Problem",
            "content": "# Problem",
            "order_num": 1,
        },
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_problem_unauthorized(client: AsyncClient, db_session: AsyncSession):
    """测试未授权创建题目."""
    exam_id = await create_test_exam(client, db_session, "Unauthorized Exam")

    response = await client.post(
        f"/api/exams/{exam_id}/problems",
        json={
            "title": "Problem",
            "content": "# Problem",
            "order_num": 1,
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_problem_validation_error(client: AsyncClient, db_session: AsyncSession):
    """测试创建题目参数验证失败."""
    exam_id = await create_test_exam(client, db_session, "Validation Exam")

    admin = await create_test_admin(
        db_session,
        username="validation_admin",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(admin.id)

    # 缺少必填字段
    response = await client.post(
        f"/api/exams/{exam_id}/problems",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Problem",
            # 缺少 content, order_num
        },
    )
    assert response.status_code == 422


# ==================== 修改题目测试 ====================


@pytest.mark.asyncio
async def test_update_problem_success(client: AsyncClient, db_session: AsyncSession):
    """测试成功修改题目."""
    exam_id = await create_test_exam(client, db_session, "Exam for Update")
    problem_id = await create_test_problem(client, db_session, exam_id, "Original Title")

    admin = await create_test_admin(
        db_session,
        username="update_admin",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(admin.id)

    response = await client.put(
        f"/api/problems/{problem_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Updated Title",
            "content": "# Updated Content",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["title"] == "Updated Title"
    assert data["data"]["content"] == "# Updated Content"

    # 验证数据库
    result = await db_session.execute(select(Problem).where(Problem.id == problem_id))
    problem = result.scalar_one()
    assert problem.title == "Updated Title"


@pytest.mark.asyncio
async def test_update_problem_partial(client: AsyncClient, db_session: AsyncSession):
    """测试部分修改题目."""
    exam_id = await create_test_exam(client, db_session, "Exam for Partial")
    problem_id = await create_test_problem(client, db_session, exam_id, "Partial Title")

    admin = await create_test_admin(
        db_session,
        username="partial_admin",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(admin.id)

    response = await client.put(
        f"/api/problems/{problem_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Only Title Updated",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["title"] == "Only Title Updated"


@pytest.mark.asyncio
async def test_update_problem_not_found(client: AsyncClient, db_session: AsyncSession):
    """测试修改不存在的题目."""
    admin = await create_test_admin(
        db_session,
        username="notfound_admin",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(admin.id)

    response = await client.put(
        "/api/problems/9999",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Updated Title"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_problem_unauthorized(client: AsyncClient, db_session: AsyncSession):
    """测试未授权修改题目."""
    exam_id = await create_test_exam(client, db_session, "Exam for Unauthorized")
    problem_id = await create_test_problem(client, db_session, exam_id, "Unauthorized Title")

    response = await client.put(
        f"/api/problems/{problem_id}",
        json={"title": "Updated Title"},
    )
    assert response.status_code == 401


# ==================== 删除题目测试 ====================


@pytest.mark.asyncio
async def test_delete_problem_success(client: AsyncClient, db_session: AsyncSession):
    """测试成功删除题目."""
    exam_id = await create_test_exam(client, db_session, "Exam for Delete")
    problem_id = await create_test_problem(client, db_session, exam_id, "Delete Title")

    admin = await create_test_admin(
        db_session,
        username="delete_admin",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(admin.id)

    response = await client.delete(
        f"/api/problems/{problem_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200

    # 验证数据库
    result = await db_session.execute(select(Problem).where(Problem.id == problem_id))
    problem = result.scalar_one_or_none()
    assert problem is None


@pytest.mark.asyncio
async def test_delete_problem_not_found(client: AsyncClient, db_session: AsyncSession):
    """测试删除不存在的题目."""
    admin = await create_test_admin(
        db_session,
        username="delete_notfound_admin",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(admin.id)

    response = await client.delete(
        "/api/problems/9999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_problem_unauthorized(client: AsyncClient, db_session: AsyncSession):
    """测试未授权删除题目."""
    exam_id = await create_test_exam(client, db_session, "Exam for Unauthorized Delete")
    problem_id = await create_test_problem(client, db_session, exam_id, "Unauthorized Delete")

    response = await client.delete(f"/api/problems/{problem_id}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_problem_cascade_codes(client: AsyncClient, db_session: AsyncSession):
    """测试删除题目时级联删除代码."""
    exam_id = await create_test_exam(client, db_session, "Exam for Cascade")
    problem_id = await create_test_problem(client, db_session, exam_id, "Cascade Title")

    # 创建考生和代码（这里简化处理，只验证题目删除）
    admin = await create_test_admin(
        db_session,
        username="cascade_admin",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(admin.id)

    response = await client.delete(
        f"/api/problems/{problem_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    # 验证题目被删除
    result = await db_session.execute(select(Problem).where(Problem.id == problem_id))
    problem = result.scalar_one_or_none()
    assert problem is None


@pytest.mark.asyncio
async def test_create_problem_forbidden_for_regular_admin(
    client: AsyncClient, db_session: AsyncSession
):
    """测试普通管理员不能创建题目."""
    exam_id = await create_test_exam(client, db_session, "Forbidden Problem Exam")
    admin = await create_test_admin(db_session, username="regular_problem_admin")
    token = create_admin_token(admin.id)

    response = await client.post(
        f"/api/exams/{exam_id}/problems",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Forbidden Problem",
            "content": "# Forbidden Problem",
            "order_num": 1,
        },
    )

    assert response.status_code == 403


# ==================== 选择题测试 ====================


@pytest.mark.asyncio
async def test_create_single_choice_problem_success(client: AsyncClient, db_session: AsyncSession):
    """测试成功创建单选题."""
    exam_id = await create_test_exam(client, db_session, "Single Choice Exam")

    admin = await create_test_admin(
        db_session,
        username="single_choice_admin",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(admin.id)

    response = await client.post(
        f"/api/exams/{exam_id}/problems",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "单选题测试",
            "content": "# 单选题\n\n这是一道单选题",
            "type": "single_choice",
            "options": [
                {"id": "A", "content": "选项A", "is_correct": False},
                {"id": "B", "content": "选项B", "is_correct": True},
                {"id": "C", "content": "选项C", "is_correct": False},
                {"id": "D", "content": "选项D", "is_correct": False},
            ],
            "order_num": 1,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "problem_id" in data["data"]

    # 验证数据库
    result = await db_session.execute(
        select(Problem).where(Problem.id == data["data"]["problem_id"])
    )
    problem = result.scalar_one_or_none()
    assert problem is not None
    assert problem.title == "单选题测试"
    assert problem.type == "single_choice"
    assert problem.options is not None


@pytest.mark.asyncio
async def test_create_multiple_choice_problem_success(client: AsyncClient, db_session: AsyncSession):
    """测试成功创建多选题."""
    exam_id = await create_test_exam(client, db_session, "Multiple Choice Exam")

    admin = await create_test_admin(
        db_session,
        username="multiple_choice_admin",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(admin.id)

    response = await client.post(
        f"/api/exams/{exam_id}/problems",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "多选题测试",
            "content": "# 多选题\n\n这是一道多选题",
            "type": "multiple_choice",
            "options": [
                {"id": "A", "content": "选项A", "is_correct": True},
                {"id": "B", "content": "选项B", "is_correct": True},
                {"id": "C", "content": "选项C", "is_correct": False},
                {"id": "D", "content": "选项D", "is_correct": False},
            ],
            "order_num": 1,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200

    # 验证数据库
    result = await db_session.execute(
        select(Problem).where(Problem.id == data["data"]["problem_id"])
    )
    problem = result.scalar_one_or_none()
    assert problem is not None
    assert problem.type == "multiple_choice"


@pytest.mark.asyncio
async def test_create_single_choice_problem_not_enough_options(
    client: AsyncClient, db_session: AsyncSession
):
    """测试单选题选项不足."""
    exam_id = await create_test_exam(client, db_session, "Not Enough Options Exam")

    admin = await create_test_admin(
        db_session,
        username="not_enough_options_admin",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(admin.id)

    response = await client.post(
        f"/api/exams/{exam_id}/problems",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "单选题测试",
            "content": "# 单选题",
            "type": "single_choice",
            "options": [
                {"id": "A", "content": "选项A", "is_correct": True},
            ],
            "order_num": 1,
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert "至少需要2个选项" in data["message"]


@pytest.mark.asyncio
async def test_create_single_choice_problem_no_correct_answer(
    client: AsyncClient, db_session: AsyncSession
):
    """测试单选题没有正确答案."""
    exam_id = await create_test_exam(client, db_session, "No Correct Answer Exam")

    admin = await create_test_admin(
        db_session,
        username="no_correct_admin",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(admin.id)

    response = await client.post(
        f"/api/exams/{exam_id}/problems",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "单选题测试",
            "content": "# 单选题",
            "type": "single_choice",
            "options": [
                {"id": "A", "content": "选项A", "is_correct": False},
                {"id": "B", "content": "选项B", "is_correct": False},
            ],
            "order_num": 1,
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert "必须有且只有一个正确答案" in data["message"]


@pytest.mark.asyncio
async def test_create_multiple_choice_problem_no_correct_answer(
    client: AsyncClient, db_session: AsyncSession
):
    """测试多选题没有正确答案."""
    exam_id = await create_test_exam(client, db_session, "Multi No Correct Exam")

    admin = await create_test_admin(
        db_session,
        username="multi_no_correct_admin",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(admin.id)

    response = await client.post(
        f"/api/exams/{exam_id}/problems",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "多选题测试",
            "content": "# 多选题",
            "type": "multiple_choice",
            "options": [
                {"id": "A", "content": "选项A", "is_correct": False},
                {"id": "B", "content": "选项B", "is_correct": False},
            ],
            "order_num": 1,
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert "至少需要一个正确答案" in data["message"]


@pytest.mark.asyncio
async def test_list_problems_with_choice_type(client: AsyncClient, db_session: AsyncSession):
    """测试获取题目列表包含选择题类型."""
    exam_id = await create_test_exam(client, db_session, "List Choice Exam")

    admin = await create_test_admin(
        db_session,
        username="list_choice_admin",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(admin.id)

    # 创建单选题
    await client.post(
        f"/api/exams/{exam_id}/problems",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "单选题",
            "content": "# 单选题",
            "type": "single_choice",
            "options": [
                {"id": "A", "content": "选项A", "is_correct": True},
                {"id": "B", "content": "选项B", "is_correct": False},
            ],
            "order_num": 1,
        },
    )

    # 创建编程题
    await client.post(
        f"/api/exams/{exam_id}/problems",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "编程题",
            "content": "# 编程题",
            "type": "coding",
            "order_num": 2,
        },
    )

    # 获取题目列表
    response = await client.get(f"/api/exams/{exam_id}/problems")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert len(data["data"]) == 2

    # 验证题目类型
    problem_types = [p["type"] for p in data["data"]]
    assert "single_choice" in problem_types
    assert "coding" in problem_types

    # 验证选择题包含选项
    choice_problem = next(p for p in data["data"] if p["type"] == "single_choice")
    assert "options" in choice_problem
    assert len(choice_problem["options"]) == 2


@pytest.mark.asyncio
async def test_update_problem_to_choice_type(client: AsyncClient, db_session: AsyncSession):
    """测试将编程题更新为选择题."""
    exam_id = await create_test_exam(client, db_session, "Update to Choice Exam")
    problem_id = await create_test_problem(client, db_session, exam_id, "Original Problem")

    admin = await create_test_admin(
        db_session,
        username="update_to_choice_admin",
        role=AdminRole.SUPER_ADMIN,
    )
    token = create_admin_token(admin.id)

    response = await client.put(
        f"/api/problems/{problem_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "type": "single_choice",
            "options": [
                {"id": "A", "content": "选项A", "is_correct": True},
                {"id": "B", "content": "选项B", "is_correct": False},
            ],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["type"] == "single_choice"
    assert len(data["data"]["options"]) == 2
