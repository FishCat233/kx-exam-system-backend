"""WebSocket 连接失败上报与重复连接测试."""

import secrets
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Exam,
    ExamStatus,
    OperationLevel,
    OperationLog,
    Problem,
    Student,
    SubmitStatus,
)
from app.services.websocket import ws_manager
from app.utils import create_student_token


async def create_report_exam(db_session: AsyncSession) -> Exam:
    """创建测试考试."""
    exam = Exam(
        name="测试考试",
        subject="C语言",
        duration=120,
        start_time=datetime.now(UTC),
        end_time=datetime.now(UTC) + timedelta(hours=2),
        status=ExamStatus.ONGOING,
    )
    db_session.add(exam)
    await db_session.commit()
    await db_session.refresh(exam)
    return exam


async def create_report_problem(db_session: AsyncSession, exam_id: int) -> Problem:
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


async def create_report_student(
    db_session: AsyncSession, exam_id: int, fullscreen: bool = True
) -> Student:
    """创建测试考生."""
    student = Student(
        exam_id=exam_id,
        student_id="2024001",
        name="张三",
        login_code="ABC123",
        login_code_used=True,
        submit_status=SubmitStatus.IN_PROGRESS,
        websocket_token=secrets.token_urlsafe(32),
        is_fullscreen=fullscreen,
    )
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)
    return student


async def count_failed_logs(db_session: AsyncSession, student_id: int) -> int:
    """统计连接失败日志数量."""
    result = await db_session.execute(
        select(func.count())
        .select_from(OperationLog)
        .where(
            OperationLog.student_id == student_id,
            OperationLog.operation_type == "websocket_connect_failed",
        )
    )
    return result.scalar() or 0


def auth_headers(student: Student) -> dict:
    """获取考生认证请求头."""
    token = create_student_token(student.id, student.exam_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_report_ws_failure_writes_critical_log(client: AsyncClient, db_session: AsyncSession):
    """测试 WS 未连接时上报：写入 critical 日志并清除全屏标记."""
    exam = await create_report_exam(db_session)
    student = await create_report_student(db_session, exam.id, fullscreen=True)

    response = await client.post(
        "/api/ws/report", json={"reason": "连接超时"}, headers=auth_headers(student)
    )

    assert response.status_code == 200
    assert response.json()["code"] == 200

    result = await db_session.execute(
        select(OperationLog).where(
            OperationLog.student_id == student.id,
            OperationLog.operation_type == "websocket_connect_failed",
        )
    )
    log = result.scalar_one_or_none()
    assert log is not None
    assert log.level == OperationLevel.CRITICAL
    assert "连接超时" in log.description

    await db_session.refresh(student)
    assert student.is_fullscreen is False


@pytest.mark.asyncio
async def test_report_ws_failure_ignored_when_connected(
    client: AsyncClient, db_session: AsyncSession
):
    """测试 WS 已连接时上报：不写日志."""
    exam = await create_report_exam(db_session)
    student = await create_report_student(db_session, exam.id, fullscreen=True)

    class MockWebSocket:
        async def accept(self):
            pass

    token = student.websocket_token
    await ws_manager.connect(MockWebSocket(), token, student.id)

    try:
        response = await client.post(
            "/api/ws/report", json={"reason": "连接超时"}, headers=auth_headers(student)
        )

        assert response.status_code == 200
        assert await count_failed_logs(db_session, student.id) == 0
    finally:
        ws_manager.disconnect(token)


@pytest.mark.asyncio
async def test_report_ws_failure_dedup_within_window(client: AsyncClient, db_session: AsyncSession):
    """测试去重：窗口内重复上报只写一条日志，窗口外再写."""
    exam = await create_report_exam(db_session)
    student = await create_report_student(db_session, exam.id)

    for _ in range(2):
        response = await client.post(
            "/api/ws/report", json={"reason": "连接超时"}, headers=auth_headers(student)
        )
        assert response.status_code == 200

    assert await count_failed_logs(db_session, student.id) == 1

    # 把首条日志时间挪到去重窗口之外，再上报应写入新日志
    result = await db_session.execute(
        select(OperationLog)
        .where(OperationLog.student_id == student.id)
        .order_by(OperationLog.created_at.desc())
        .limit(1)
    )
    log = result.scalar_one()
    log.created_at = datetime.now(UTC) - timedelta(seconds=120)
    await db_session.commit()

    response = await client.post(
        "/api/ws/report", json={"reason": "再次失败"}, headers=auth_headers(student)
    )
    assert response.status_code == 200
    assert await count_failed_logs(db_session, student.id) == 2


@pytest.mark.asyncio
async def test_duplicate_ws_connection_writes_warning_log(db_session: AsyncSession, monkeypatch):
    """测试重复连接被拒绝：写入 warning 日志."""
    from types import SimpleNamespace

    import app.routers.ws as ws_module
    from app.routers.ws import websocket_endpoint
    from tests.conftest import TestingSessionLocal

    # 端点内部使用短会话工厂，测试中指向测试数据库
    monkeypatch.setattr(ws_module, "AsyncSessionLocal", TestingSessionLocal)

    exam = await create_report_exam(db_session)
    student = await create_report_student(db_session, exam.id)
    ws_token = student.websocket_token

    class MockWebSocket:
        async def accept(self):
            pass

    await ws_manager.connect(MockWebSocket(), ws_token, student.id)

    class MockRejectedWebSocket:
        query_params = {"token": ws_token}
        headers = {}
        client = SimpleNamespace(host="127.0.0.1")

        def __init__(self):
            self.close_code = None
            self.close_reason = None

        async def close(self, code=1000, reason=None):
            self.close_code = code
            self.close_reason = reason

    try:
        rejected = MockRejectedWebSocket()
        await websocket_endpoint(rejected)

        assert rejected.close_code == 1008
        assert rejected.close_reason == "已在其他标签页连接"

        result = await db_session.execute(
            select(OperationLog).where(
                OperationLog.student_id == student.id,
                OperationLog.operation_type == "websocket_duplicate_connection",
            )
        )
        log = result.scalar_one_or_none()
        assert log is not None
        assert log.level == OperationLevel.WARNING
    finally:
        ws_manager.disconnect(ws_token)


@pytest.mark.asyncio
async def test_submit_without_ws_writes_critical_log(client: AsyncClient, db_session: AsyncSession):
    """测试交卷时 WS 未连接：交卷放行，写入 critical 日志."""
    exam = await create_report_exam(db_session)
    student = await create_report_student(db_session, exam.id)

    response = await client.post("/api/code/submit", headers=auth_headers(student))

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "submitted"

    result = await db_session.execute(
        select(OperationLog).where(
            OperationLog.student_id == student.id,
            OperationLog.operation_type == "websocket_missing_at_submit",
        )
    )
    log = result.scalar_one_or_none()
    assert log is not None
    assert log.level == OperationLevel.CRITICAL


@pytest.mark.asyncio
async def test_submit_with_ws_writes_no_missing_log(client: AsyncClient, db_session: AsyncSession):
    """测试交卷时 WS 已连接：交卷成功且不写缺失日志."""
    exam = await create_report_exam(db_session)
    student = await create_report_student(db_session, exam.id)

    class MockWebSocket:
        async def accept(self):
            pass

    token = student.websocket_token
    await ws_manager.connect(MockWebSocket(), token, student.id)

    try:
        response = await client.post("/api/code/submit", headers=auth_headers(student))

        assert response.status_code == 200

        result = await db_session.execute(
            select(OperationLog).where(
                OperationLog.student_id == student.id,
                OperationLog.operation_type == "websocket_missing_at_submit",
            )
        )
        assert result.scalar_one_or_none() is None
    finally:
        ws_manager.disconnect(token)


@pytest.mark.asyncio
async def test_save_code_rejected_when_ws_never_connected(
    client: AsyncClient, db_session: AsyncSession
):
    """测试从未建立 WS 连接的考生保存代码被拒绝并记 critical 日志."""
    exam = await create_report_exam(db_session)
    student = await create_report_student(db_session, exam.id)
    problem = await create_report_problem(db_session, exam.id)

    response = await client.post(
        f"/api/code/{problem.id}",
        json={"code": "int main() { return 0; }"},
        headers=auth_headers(student),
    )

    assert response.status_code == 403

    result = await db_session.execute(
        select(OperationLog).where(
            OperationLog.student_id == student.id,
            OperationLog.operation_type == "websocket_never_connected",
        )
    )
    log = result.scalar_one_or_none()
    assert log is not None
    assert log.level == OperationLevel.CRITICAL


@pytest.mark.asyncio
async def test_save_code_block_log_dedup(client: AsyncClient, db_session: AsyncSession):
    """测试连续被拒只记一条日志."""
    exam = await create_report_exam(db_session)
    student = await create_report_student(db_session, exam.id)
    problem = await create_report_problem(db_session, exam.id)

    for _ in range(3):
        response = await client.post(
            f"/api/code/{problem.id}",
            json={"code": "int main() { return 0; }"},
            headers=auth_headers(student),
        )
        assert response.status_code == 403

    result = await db_session.execute(
        select(func.count())
        .select_from(OperationLog)
        .where(
            OperationLog.student_id == student.id,
            OperationLog.operation_type == "websocket_never_connected",
        )
    )
    assert result.scalar() == 1


@pytest.mark.asyncio
async def test_save_code_allowed_after_connected(client: AsyncClient, db_session: AsyncSession):
    """测试建立过 WS 连接（即使已断开）的考生可以保存代码."""
    exam = await create_report_exam(db_session)
    student = await create_report_student(db_session, exam.id)
    problem = await create_report_problem(db_session, exam.id)

    class MockWebSocket:
        async def accept(self):
            pass

    token = student.websocket_token
    await ws_manager.connect(MockWebSocket(), token, student.id)
    ws_manager.disconnect(token)

    response = await client.post(
        f"/api/code/{problem.id}",
        json={"code": "int main() { return 0; }"},
        headers=auth_headers(student),
    )

    assert response.status_code == 200
