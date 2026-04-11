"""WebSocket 测试."""

import secrets
from datetime import UTC, datetime

import pytest_asyncio

from app.models import Exam, ExamStatus, Student, SubmitStatus
from app.services.websocket import WebSocketManager


@pytest_asyncio.fixture
async def test_exam(db_session):
    """创建测试考试."""
    exam = Exam(
        name="测试考试",
        subject="C语言",
        duration=120,
        start_time=datetime(2025, 1, 1, 8, 0, 0, tzinfo=UTC),
        end_time=datetime(2025, 12, 31, 18, 0, 0, tzinfo=UTC),
        status=ExamStatus.IN_PROGRESS,
        pledge_content="测试承诺书",
    )
    db_session.add(exam)
    await db_session.commit()
    await db_session.refresh(exam)
    return exam


@pytest_asyncio.fixture
async def test_student(db_session, test_exam):
    """创建测试考生."""
    student = Student(
        exam_id=test_exam.id,
        student_id="2024001",
        name="张三",
        login_code="ABC123",
        login_code_used=True,
        submit_status=SubmitStatus.IN_PROGRESS,
        websocket_token=secrets.token_urlsafe(32),
    )
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)
    return student


class TestWebSocketManager:
    """WebSocket 管理器测试."""

    @pytest_asyncio.fixture
    async def manager(self):
        """创建测试用的 WebSocket 管理器."""
        manager = WebSocketManager()
        yield manager
        # 清理
        manager.active_connections.clear()
        manager.token_to_student_id.clear()
        manager.student_id_to_token.clear()

    async def test_connect(self, manager):
        """测试连接建立."""

        # 使用 mock WebSocket
        class MockWebSocket:
            def __init__(self):
                self.accepted = False
                self.messages = []

            async def accept(self):
                self.accepted = True

            async def send_json(self, data):
                self.messages.append(data)

        ws = MockWebSocket()
        token = "test_token"
        student_id = 1

        await manager.connect(ws, token, student_id)

        assert ws.accepted
        assert token in manager.active_connections
        assert manager.token_to_student_id[token] == student_id
        assert manager.student_id_to_token[student_id] == token

    async def test_disconnect(self, manager):
        """测试连接断开."""

        class MockWebSocket:
            async def accept(self):
                pass

        ws = MockWebSocket()
        token = "test_token"
        student_id = 1

        await manager.connect(ws, token, student_id)
        manager.disconnect(token)

        assert token not in manager.active_connections
        assert token not in manager.token_to_student_id
        assert student_id not in manager.student_id_to_token

    async def test_send_message(self, manager):
        """测试发送消息."""

        class MockWebSocket:
            def __init__(self):
                self.messages = []

            async def accept(self):
                pass

            async def send_json(self, data):
                self.messages.append(data)

        ws = MockWebSocket()
        token = "test_token"
        student_id = 1

        await manager.connect(ws, token, student_id)

        message = {"type": "test", "data": "hello"}
        await manager.send_message(token, message)

        assert len(ws.messages) == 1
        assert ws.messages[0] == message

    async def test_send_message_by_student_id(self, manager):
        """测试根据学生 ID 发送消息."""

        class MockWebSocket:
            def __init__(self):
                self.messages = []

            async def accept(self):
                pass

            async def send_json(self, data):
                self.messages.append(data)

        ws = MockWebSocket()
        token = "test_token"
        student_id = 1

        await manager.connect(ws, token, student_id)

        message = {"type": "test", "data": "hello"}
        await manager.send_message_by_student_id(student_id, message)

        assert len(ws.messages) == 1
        assert ws.messages[0] == message

    async def test_is_connected(self, manager):
        """测试连接状态检查."""

        class MockWebSocket:
            async def accept(self):
                pass

        ws = MockWebSocket()
        token = "test_token"
        student_id = 1

        assert not manager.is_connected(student_id)

        await manager.connect(ws, token, student_id)
        assert manager.is_connected(student_id)

        manager.disconnect(token)
        assert not manager.is_connected(student_id)

    async def test_verify_token(self, manager, db_session, test_student):
        """测试 Token 验证."""
        # 有效 token
        student = await manager.verify_token(test_student.websocket_token, db_session)
        assert student is not None
        assert student.id == test_student.id

        # 无效 token
        student = await manager.verify_token("invalid_token", db_session)
        assert student is None

        # 已交卷学生
        test_student.submit_status = SubmitStatus.SUBMITTED
        await db_session.commit()
        student = await manager.verify_token(test_student.websocket_token, db_session)
        assert student is None


class TestWebSocketServerMessages:
    """WebSocket 服务端消息发送测试."""

    async def test_send_exam_status(self):
        """测试发送考试状态."""

        class MockWebSocket:
            def __init__(self):
                self.messages = []

            async def accept(self):
                pass

            async def send_json(self, data):
                self.messages.append(data)

        manager = WebSocketManager()
        ws = MockWebSocket()
        token = "test_token"
        student_id = 1

        await manager.connect(ws, token, student_id)
        await manager.send_exam_status(student_id, "in_progress", 3600)

        assert len(ws.messages) == 1
        assert ws.messages[0]["type"] == "exam_status"
        assert ws.messages[0]["data"]["status"] == "in_progress"
        assert ws.messages[0]["data"]["remaining_time"] == 3600

    async def test_send_warning(self):
        """测试发送警告."""

        class MockWebSocket:
            def __init__(self):
                self.messages = []

            async def accept(self):
                pass

            async def send_json(self, data):
                self.messages.append(data)

        manager = WebSocketManager()
        ws = MockWebSocket()
        token = "test_token"
        student_id = 1

        await manager.connect(ws, token, student_id)
        await manager.send_warning(student_id, "测试警告", "warning")

        assert len(ws.messages) == 1
        assert ws.messages[0]["type"] == "warning"
        assert ws.messages[0]["data"]["message"] == "测试警告"
        assert ws.messages[0]["data"]["level"] == "warning"

    async def test_send_force_submit(self):
        """测试发送强制收卷指令."""

        class MockWebSocket:
            def __init__(self):
                self.messages = []

            async def accept(self):
                pass

            async def send_json(self, data):
                self.messages.append(data)

        manager = WebSocketManager()
        ws = MockWebSocket()
        token = "test_token"
        student_id = 1

        await manager.connect(ws, token, student_id)
        await manager.send_force_submit(student_id, "测试原因")

        assert len(ws.messages) == 1
        assert ws.messages[0]["type"] == "force_submit"
        assert ws.messages[0]["data"]["reason"] == "测试原因"

    async def test_send_notification(self):
        """测试发送系统通知."""

        class MockWebSocket:
            def __init__(self):
                self.messages = []

            async def accept(self):
                pass

            async def send_json(self, data):
                self.messages.append(data)

        manager = WebSocketManager()
        ws = MockWebSocket()
        token = "test_token"
        student_id = 1

        await manager.connect(ws, token, student_id)
        await manager.send_notification(student_id, "测试通知")

        assert len(ws.messages) == 1
        assert ws.messages[0]["type"] == "notification"
        assert ws.messages[0]["data"]["message"] == "测试通知"
