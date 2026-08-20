"""HTTP 接口限流服务（基于内存固定窗口）.

单实例部署场景下直接使用进程内存储，不引入 Redis 等外部依赖。
若后续多实例部署，需替换为共享存储（如 Redis）实现。
"""

import threading
import time
from collections.abc import Callable

from fastapi import HTTPException, Request, status

from app.config import settings

# 窗口保留时长（秒）：超过该时间未活动的 key 会被回收，防止内存无限增长
_WINDOW_MAX_AGE = 3600


class FixedWindowLimiter:
    """线程安全的内存固定窗口限流器.

    与 WebSocket 服务的限流实现保持一致的固定窗口模型：
    记录每个 key 的 (窗口起始时间, 窗口内请求数)，窗口从第一次请求开始计时，
    窗口过期后整窗口重置。

    注意：固定窗口在窗口边界附近存在突发漏洞（窗口末尾与下个窗口开头的请求
    可能在极短时间内集中到达）。如需严格封顶可换用滑动窗口实现。
    """

    def __init__(self) -> None:
        self._windows: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window: float) -> bool:
        """检查并记录一次请求，若未超限则计数 +1.

        Args:
            key: 限流键（IP 或 token）
            limit: 窗口内最大请求数
            window: 窗口大小（秒）

        Returns:
            是否允许该请求通过
        """
        now = time.monotonic()
        with self._lock:
            start, count = self._windows.get(key, (now, 0))
            if now - start > window:
                self._windows[key] = (now, 1)
                return True
            if count >= limit:
                return False
            self._windows[key] = (start, count + 1)
            return True

    def cleanup(self, max_age: float = _WINDOW_MAX_AGE) -> None:
        """回收长期未活动的 key，防止内存无限增长."""
        now = time.monotonic()
        with self._lock:
            stale = [k for k, (start, _) in self._windows.items() if now - start > max_age]
            for k in stale:
                del self._windows[k]

    def reset(self) -> None:
        """清空所有窗口（测试用）."""
        with self._lock:
            self._windows.clear()


# 全局限流器实例
limiter = FixedWindowLimiter()


def client_ip(request: Request) -> str:
    """从请求中提取客户端 IP，获取不到时使用 unknown 兜底."""
    return request.client.host if request.client else "unknown"


def bearer_token(request: Request) -> str:
    """从 Authorization 头中提取 Bearer token，无则返回空字符串."""
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:]
    return ""


def _too_many(window: float) -> HTTPException:
    """构造 429 响应，携带 Retry-After 头."""
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="请求过于频繁，请稍后重试",
        headers={"Retry-After": str(int(window))},
    )


def rate_limit(
    *,
    scope: str,
    ip_limit: int | None = None,
    ip_window: float = 60.0,
    token_limit: int | None = None,
    token_window: float = 60.0,
) -> Callable[[Request], None]:
    """生成限流依赖的工厂函数.

    Args:
        scope: 限流键命名空间，用于隔离不同接口的额度
        ip_limit: 每 IP 窗口内最大请求数，None 表示不按 IP 限流
        ip_window: IP 限流窗口大小（秒）
        token_limit: 每 token 窗口内最大请求数，None 表示不按 token 限流
        token_window: token 限流窗口大小（秒）

    Returns:
        FastAPI 依赖函数（作用于 Request）
    """

    def dependency(request: Request) -> None:
        if not settings.rate_limit_enabled:
            return

        if ip_limit is not None:
            ip = client_ip(request)
            if not limiter.check(f"{scope}:ip:{ip}", ip_limit, ip_window):
                raise _too_many(ip_window)

        if token_limit is not None:
            token = bearer_token(request)
            if token and not limiter.check(f"{scope}:token:{token}", token_limit, token_window):
                raise _too_many(token_window)

    return dependency
