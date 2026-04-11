"""WebSocket 服务."""

from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Student


class WebSocketManager:
    """WebSocket 连接管理器."""

    def __init__(self):
        """初始化连接管理器."""
        self.active_connections: dict[str, WebSocket] = {}
        # token -> student_id 映射
        self.token_to_student_id: dict[str, int] = {}
        # student_id -> token 映射（用于反向查找）
        self.student_id_to_token: dict[int, str] = {}

    async def connect(self, websocket: WebSocket, token: str, student_id: int):
        """建立 WebSocket 连接.

        Args:
            websocket: WebSocket 对象
            token: 连接 Token
            student_id: 学生 ID
        """
        await websocket.accept()
        self.active_connections[token] = websocket
        self.token_to_student_id[token] = student_id
        self.student_id_to_token[student_id] = token

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
                Student.submit_status == "in_progress",
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


# 全局 WebSocket 管理器实例
ws_manager = WebSocketManager()
