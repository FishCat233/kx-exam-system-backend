"""WebSocket 服务."""

import time
from typing import TypedDict

from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Student, SubmitStatus


class ClientConnectionInfo(TypedDict, total=False):
    ip_address: str
    user_agent: str


class WebSocketManager:
    """WebSocket 连接管理器."""

    def __init__(self):
        """初始化连接管理器."""
        self.active_connections: dict[str, WebSocket] = {}
        # token -> student_id 映射
        self.token_to_student_id: dict[str, int] = {}
        # student_id -> token 映射（用于反向查找）
        self.student_id_to_token: dict[int, str] = {}
        # token -> 连接元数据（IP、User-Agent）
        self.connection_info: dict[str, ClientConnectionInfo] = {}
        # 速率限制：token -> (窗口起始时间, 计数)
        self._rate_windows: dict[str, tuple[float, int]] = {}
        # 曾经建立过连接的考生集合（连接成功后加入，断开不清除）
        self.ever_connected_students: set[int] = set()

    async def connect(
        self,
        websocket: WebSocket,
        token: str,
        student_id: int,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ):
        """建立 WebSocket 连接.

        Args:
            websocket: WebSocket 对象
            token: 连接 Token
            student_id: 学生 ID
            ip_address: 客户端 IP 地址
            user_agent: 客户端 User-Agent
        """
        await websocket.accept()
        self.active_connections[token] = websocket
        self.token_to_student_id[token] = student_id
        self.student_id_to_token[student_id] = token
        self.ever_connected_students.add(student_id)

        ip_address = ip_address if ip_address else "None"
        user_agent = user_agent if user_agent else "None"
        self.connection_info[token] = ClientConnectionInfo(
            ip_address=ip_address, user_agent=user_agent
        )

    def disconnect(self, token: str):
        """断开 WebSocket 连接.

        Args:
            token: 连接 Token
        """
        if token in self.active_connections:
            student_id = self.token_to_student_id.get(token)
            if student_id and student_id in self.student_id_to_token:
                del self.student_id_to_token[student_id]
            del self.active_connections[token]
            self.token_to_student_id.pop(token, None)
            self.connection_info.pop(token, None)
            self._rate_windows.pop(token, None)

    async def send_message(self, token: str, message: dict):
        """发送消息给指定连接.

        Args:
            token: 连接 Token
            message: 消息内容
        """
        if websocket := self.active_connections.get(token):
            await websocket.send_json(message)

    async def send_message_by_student_id(self, student_id: int, message: dict):
        """根据学生 ID 发送消息.

        Args:
            student_id: 学生 ID
            message: 消息内容
        """
        if token := self.student_id_to_token.get(student_id):
            await self.send_message(token, message)

    async def broadcast(self, message: dict):
        """广播消息给所有连接.

        Args:
            message: 消息内容
        """
        for websocket in self.active_connections.values():
            await websocket.send_json(message)

    async def verify_token(self, token: str, db: AsyncSession) -> Student | None:
        """验证 WebSocket Token 有效性.

        Args:
            token: WebSocket Token
            db: 数据库会话

        Returns:
            验证成功返回 Student 对象，失败返回 None
        """
        result = await db.execute(
            select(Student).where(
                Student.websocket_token == token,
                Student.submit_status == SubmitStatus.IN_PROGRESS,
            )
        )
        return result.scalar_one_or_none()

    # ==================== 服务端消息发送接口 ====================

    async def send_exam_status(
        self,
        student_id: int,
        status: str,
        remaining_time: int,
    ):
        """发送考试状态更新.

        Args:
            student_id: 学生 ID
            status: 考试状态
            remaining_time: 剩余时间（秒）
        """
        message = {
            "type": "exam_status",
            "data": {
                "status": status,
                "remaining_time": remaining_time,
            },
        }
        await self.send_message_by_student_id(student_id, message)

    async def send_warning(self, student_id: int, message: str, level: str = "warning"):
        """发送警告通知.

        Args:
            student_id: 学生 ID
            message: 警告消息
            level: 警告级别 (warning/critical)
        """
        msg = {
            "type": "warning",
            "data": {
                "message": message,
                "level": level,
            },
        }
        await self.send_message_by_student_id(student_id, msg)

    async def send_force_submit(self, student_id: int, reason: str = "管理员强制收卷"):
        """发送强制收卷指令.

        Args:
            student_id: 学生 ID
            reason: 强制收卷原因
        """
        message = {
            "type": "force_submit",
            "data": {
                "reason": reason,
            },
        }
        await self.send_message_by_student_id(student_id, message)

    async def send_notification(self, student_id: int, message: str):
        """发送系统通知.

        Args:
            student_id: 学生 ID
            message: 通知消息
        """
        msg = {
            "type": "notification",
            "data": {
                "message": message,
            },
        }
        await self.send_message_by_student_id(student_id, msg)

    def is_connected(self, student_id: int) -> bool:
        """检查学生是否已连接.

        Args:
            student_id: 学生 ID

        Returns:
            是否已连接
        """
        return student_id in self.student_id_to_token

    def has_ever_connected(self, student_id: int) -> bool:
        """检查学生是否曾经建立过连接（断开后仍为 True）.

        Args:
            student_id: 学生 ID

        Returns:
            是否曾经连接过
        """
        return student_id in self.ever_connected_students

    def get_connection_info(self, student_id: int) -> ClientConnectionInfo | None:
        """获取学生连接元数据.

        Args:
            student_id: 学生 ID

        Returns:
            连接元数据字典（ip_address, user_agent），未找到返回空字典
        """
        if token := self.student_id_to_token.get(student_id):
            return self.connection_info.get(token)
        return None

    # 速率限制常量
    _RATE_LIMIT: int = 10  # 每秒最大消息数
    _RATE_WINDOW: float = 1.0  # 窗口大小（秒）

    def check_rate_limit(self, token: str) -> bool:
        """检查消息速率限制（基于滑动窗口）.

        Args:
            token: 连接 Token

        Returns:
            是否允许处理该消息
        """
        now = time.monotonic()
        window_start, count = self._rate_windows.get(token, (now, 0))
        if now - window_start > self._RATE_WINDOW:
            # 新窗口
            self._rate_windows[token] = (now, 1)
            return True
        if count >= self._RATE_LIMIT:
            return False
        self._rate_windows[token] = (window_start, count + 1)
        return True

    async def broadcast_new_problem(
        self,
        exam_id: int,
        problem_title: str,
        db: AsyncSession,
    ):
        """向指定考试的所有在线考生广播新题目通知.

        Args:
            exam_id: 考试 ID
            problem_title: 新添加的题目标题
            db: 数据库会话
        """
        from app.models import Student

        result = await db.execute(
            select(Student).where(
                Student.exam_id == exam_id,
                Student.submit_status == SubmitStatus.IN_PROGRESS,
            )
        )
        students = result.scalars().all()

        message = {
            "type": "new_problem",
            "data": {
                "message": f"新题目已添加：{problem_title}",
                "problem_title": problem_title,
            },
        }

        for student in students:
            if student.id in self.student_id_to_token:
                await self.send_message_by_student_id(student.id, message)


# 全局 WebSocket 管理器实例
ws_manager = WebSocketManager()
