"""代码管理相关测试."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Exam, ExamStatus, Problem, Student, StudentCode, SubmitStatus
from app.services.websocket import ws_manager
from app.utils import create_student_token, generate_login_code


async def create_test_exam(
    db_session: AsyncSession, status: ExamStatus = ExamStatus.NOT_STARTED
) -> Exam:
    """创建测试考试."""
    exam = Exam(
        name="测试考试",
        subject="C语言",
        duration=120,
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC) + timedelta(hours=2),
        status=status,
    )
    db_session.add(exam)
    await db_session.commit()
    await db_session.refresh(exam)
    return exam


async def create_test_problem(db_session: AsyncSession, exam_id: int) -> Problem:
    """创建测试题目."""
    problem = Problem(
        exam_id=exam_id,
        title="测试题目",
        content="这是一道测试题目",
        order_num=1,
    )
    db_session.add(problem)
    await db_session.commit()
    await db_session.refresh(problem)
    return problem


async def create_test_student(db_session: AsyncSession, exam_id: int) -> Student:
    """创建测试考生."""
    student = Student(
        exam_id=exam_id,
        student_id="2024001",
        name="张三",
        login_code=generate_login_code(),
        login_code_used=True,
        login_time=datetime.now(UTC),
        submit_status=SubmitStatus.NOT_STARTED,
    )
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)
    return student


async def get_auth_headers(student: Student) -> dict:
    """获取认证请求头."""
    token = create_student_token(student.id, student.exam_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_get_code_success(client: AsyncClient, db_session: AsyncSession):
    """测试获取代码成功."""
    # 准备数据
    exam = await create_test_exam(db_session)
    problem = await create_test_problem(db_session, exam.id)
    student = await create_test_student(db_session, exam.id)

    # 创建代码记录
    code_record = StudentCode(
        student_id=student.id,
        problem_id=problem.id,
        code='printf("Hello World");',
        saved_at=datetime.now(UTC),
    )
    db_session.add(code_record)
    await db_session.commit()

    # 发送请求
    headers = await get_auth_headers(student)
    response = await client.get(f"/api/code/{problem.id}", headers=headers)

    # 验证结果
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["code"] == 'printf("Hello World");'
    assert data["data"]["saved_at"] is not None


@pytest.mark.asyncio
async def test_get_code_not_found(client: AsyncClient, db_session: AsyncSession):
    """测试获取代码（无记录场景）."""
    # 准备数据
    exam = await create_test_exam(db_session)
    problem = await create_test_problem(db_session, exam.id)
    student = await create_test_student(db_session, exam.id)

    # 发送请求
    headers = await get_auth_headers(student)
    response = await client.get(f"/api/code/{problem.id}", headers=headers)

    # 验证结果
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["code"] == ""
    assert data["data"]["saved_at"] is None


@pytest.mark.asyncio
async def test_save_code_create(client: AsyncClient, db_session: AsyncSession):
    """测试保存代码（创建新记录）."""
    # 准备数据
    exam = await create_test_exam(db_session, status=ExamStatus.ONGOING)
    problem = await create_test_problem(db_session, exam.id)
    student = await create_test_student(db_session, exam.id)
    ws_manager.ever_connected_students.add(student.id)

    # 发送请求
    headers = await get_auth_headers(student)
    response = await client.post(
        f"/api/code/{problem.id}",
        headers=headers,
        json={"code": "int main() { return 0; }"},
    )

    # 验证结果
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["saved_at"] is not None

    # 验证数据库状态
    await db_session.refresh(student)
    assert student.submit_status == SubmitStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_save_code_update(client: AsyncClient, db_session: AsyncSession):
    """测试保存代码（更新现有记录）."""
    # 准备数据
    exam = await create_test_exam(db_session, status=ExamStatus.ONGOING)
    problem = await create_test_problem(db_session, exam.id)
    student = await create_test_student(db_session, exam.id)
    ws_manager.ever_connected_students.add(student.id)

    # 创建初始代码记录
    code_record = StudentCode(
        student_id=student.id,
        problem_id=problem.id,
        code="old code",
        saved_at=datetime.now(UTC),
    )
    db_session.add(code_record)
    await db_session.commit()

    # 发送请求更新代码
    headers = await get_auth_headers(student)
    response = await client.post(
        f"/api/code/{problem.id}",
        headers=headers,
        json={"code": 'int main() { printf("Updated"); return 0; }'},
    )

    # 验证结果
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200

    # 验证数据库状态
    await db_session.refresh(code_record)
    assert code_record.code == 'int main() { printf("Updated"); return 0; }'


@pytest.mark.asyncio
async def test_save_code_exam_ended(client: AsyncClient, db_session: AsyncSession):
    """测试保存代码时考试已结束."""
    # 准备数据
    exam = await create_test_exam(db_session, status=ExamStatus.ENDED)
    problem = await create_test_problem(db_session, exam.id)
    student = await create_test_student(db_session, exam.id)

    # 发送请求
    headers = await get_auth_headers(student)
    response = await client.post(
        f"/api/code/{problem.id}",
        headers=headers,
        json={"code": "some code"},
    )

    # 验证结果
    assert response.status_code == 400
    data = response.json()
    assert "message" in data
    assert "考试已结束" in data["message"]


@pytest.mark.asyncio
async def test_save_and_get_fill_blank_answer(client: AsyncClient, db_session: AsyncSession):
    """测试填空题答案保存与取回."""
    # 准备数据
    exam = await create_test_exam(db_session, status=ExamStatus.ONGOING)
    problem = Problem(
        exam_id=exam.id,
        title="填空题",
        content="C语言中声明整型变量的关键字是 ____",
        type="fill_blank",
        order_num=1,
    )
    db_session.add(problem)
    await db_session.commit()
    await db_session.refresh(problem)
    student = await create_test_student(db_session, exam.id)
    ws_manager.ever_connected_students.add(student.id)

    # 保存 JSON 数组字符串答案
    answer = '["int", "整数变量"]'
    headers = await get_auth_headers(student)
    response = await client.post(
        f"/api/code/{problem.id}",
        headers=headers,
        json={"code": answer},
    )

    # 验证结果
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["saved_at"] is not None

    # 保存后考生状态变为进行中
    await db_session.refresh(student)
    assert student.submit_status == SubmitStatus.IN_PROGRESS

    # 原样取回答案
    get_response = await client.get(f"/api/code/{problem.id}", headers=headers)
    assert get_response.status_code == 200
    get_data = get_response.json()
    assert get_data["code"] == 200
    assert get_data["data"]["code"] == answer


@pytest.mark.asyncio
async def test_submit_code_success(client: AsyncClient, db_session: AsyncSession):
    """测试交卷成功."""
    # 准备数据
    exam = await create_test_exam(db_session, status=ExamStatus.ONGOING)
    student = await create_test_student(db_session, exam.id)
    student.submit_status = SubmitStatus.IN_PROGRESS
    await db_session.commit()

    # 发送请求
    headers = await get_auth_headers(student)
    response = await client.post("/api/code/submit", headers=headers)

    # 验证结果
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert data["data"]["status"] == SubmitStatus.SUBMITTED
    assert data["data"]["submit_time"] is not None

    # 验证数据库状态
    await db_session.refresh(student)
    assert student.submit_status == SubmitStatus.SUBMITTED
    assert student.submit_time is not None


@pytest.mark.asyncio
async def test_submit_code_already_submitted(client: AsyncClient, db_session: AsyncSession):
    """测试重复交卷."""
    # 准备数据
    exam = await create_test_exam(db_session)
    student = await create_test_student(db_session, exam.id)
    student.submit_status = SubmitStatus.SUBMITTED
    student.submit_time = datetime.now(UTC)
    await db_session.commit()

    # 发送请求
    headers = await get_auth_headers(student)
    response = await client.post("/api/code/submit", headers=headers)

    # 验证结果
    assert response.status_code == 403
    data = response.json()
    assert "message" in data
    assert "已交卷" in data["message"]


@pytest.mark.asyncio
async def test_submit_code_force_submitted(client: AsyncClient, db_session: AsyncSession):
    """测试已被强制收卷后再次交卷."""
    # 准备数据
    exam = await create_test_exam(db_session, status=ExamStatus.ONGOING)
    student = await create_test_student(db_session, exam.id)
    student.submit_status = SubmitStatus.FORCE_SUBMITTED
    student.submit_time = datetime.now(UTC)
    await db_session.commit()

    # 发送请求
    headers = await get_auth_headers(student)
    response = await client.post("/api/code/submit", headers=headers)

    # 验证结果
    assert response.status_code == 403
    data = response.json()
    assert "message" in data
    assert "已交卷" in data["message"]


@pytest.mark.asyncio
async def test_get_code_unauthorized(client: AsyncClient):
    """测试未认证访问获取代码."""
    # 未提供 Authorization 头，返回 401（未授权）
    response = await client.get("/api/code/1")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_save_code_unauthorized(client: AsyncClient):
    """测试未认证访问保存代码."""
    response = await client.post("/api/code/1", json={"code": "test"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_submit_code_unauthorized(client: AsyncClient):
    """测试未认证访问交卷."""
    response = await client.post("/api/code/submit")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_code_invalid_token(client: AsyncClient):
    """测试无效 Token 访问获取代码."""
    headers = {"Authorization": "Bearer invalid_token"}
    response = await client.get("/api/code/1", headers=headers)

    assert response.status_code == 401
