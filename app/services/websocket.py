"""WebSocket 服务."""

from fastapi import WebSocket


class WebSocketManager:
    """WebSocket 连接管理器."""

    def __init__(self):
        """初始化连接管理器."""
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, token: str):
        """建立 WebSocket 连接.

        Args:
            websocket: WebSocket 对象
            token: 连接 Token
        """
        await websocket.accept()
        self.active_connections[token] = websocket

    def disconnect(self, token: str):
        """断开 WebSocket 连接.

        Args:
            token: 连接 Token
        """
        self.active_connections.pop(token, None)

    async def send_message(self, token: str, message: dict):
        """发送消息给指定连接.

        Args:
            token: 连接 Token
            message: 消息内容
        """
        if websocket := self.active_connections.get(token):
            await websocket.send_json(message)

    async def broadcast(self, message: dict):
        """广播消息给所有连接.

        Args:
            message: 消息内容
        """
        for websocket in self.active_connections.values():
            await websocket.send_json(message)


# 全局 WebSocket 管理器实例
ws_manager = WebSocketManager()
