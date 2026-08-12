"""WebSocket 路由 — 每条消息独立短会话."""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import OperationLevel, OperationLog, Student, SubmitStatus
from app.services.websocket import ws_manager

logger = logging.getLogger(__name__)

WS_HEARTBEAT_TIMEOUT = 90  # 心跳超时秒数（3 × 30s 客户端心跳间隔）

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 连接端点 — 每条消息创建独立数据库会话."""
    token = None
    student_id = None
    student: Student | None = None

    try:
        # 1. 获取 token
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="缺少 token")
            return

        # 2. 验证 token 并加载考生
        async with AsyncSessionLocal() as db:
            student = await ws_manager.verify_token(token, db)
            if not student:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token 无效")
                return

            student_id = student.id

            # 3. 阻止重复连接
            if ws_manager.is_connected(student_id):
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="已在其他标签页连接",
                )
                return

            # 4. 建立连接
            ip = websocket.client.host if websocket.client else None
            ua = websocket.headers.get("user-agent")
            await ws_manager.connect(websocket, token, student_id, ip_address=ip, user_agent=ua)

            # 5. 更新全屏状态 + 记录连接日志
            student.is_fullscreen = True
            log = OperationLog(
                student_id=student_id,
                operation_type="websocket_connected",
                description="WebSocket 连接成功",
                level=OperationLevel.NORMAL,
                ip_address=ip,
                user_agent=ua,
            )
            db.add(log)
            await db.commit()

        # 6. 发送连接成功
        try:
            await websocket.send_json(
                {"type": "connected", "data": {"message": "WebSocket 连接成功"}}
            )
        except WebSocketDisconnect:
            await _handle_disconnect(token, student_id, normal=True)
            return

        # 7. 消息循环
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=WS_HEARTBEAT_TIMEOUT
                )
            except TimeoutError:
                logger.warning("WebSocket 心跳超时 (student_id=%s)", student_id)
                await _handle_disconnect(token, student_id, normal=False, error="心跳超时")
                break
            except WebSocketDisconnect:
                await _handle_disconnect(token, student_id, normal=True)
                break
            except Exception as e:
                logger.exception("WebSocket 接收消息异常")
                await _handle_disconnect(token, student_id, normal=False, error=str(e))
                break

            # 速率限制
            if not ws_manager.check_rate_limit(token):
                try:
                    await websocket.send_json(
                        {"type": "error", "data": {"message": "消息频率过高，请稍后重试"}}
                    )
                except Exception:
                    break
                continue

            # 每条消息独立短会话
            try:
                message = json.loads(data)
                async with AsyncSessionLocal() as msg_db:
                    # 重新加载考生（确保状态最新）
                    result = await msg_db.execute(select(Student).where(Student.id == student_id))
                    fresh_student = result.scalar_one_or_none()
                    if fresh_student is None:
                        break
                    await _handle_message(websocket, message, fresh_student, msg_db)
            except json.JSONDecodeError:
                try:
                    await websocket.send_json(
                        {"type": "error", "data": {"message": "无效的 JSON 格式"}}
                    )
                except Exception:
                    break
            except WebSocketDisconnect:
                await _handle_disconnect(token, student_id, normal=True)
                break
            except Exception as e:
                logger.exception("WebSocket 消息处理异常")
                try:
                    await websocket.send_json(
                        {"type": "error", "data": {"message": f"消息处理错误: {str(e)}"}}
                    )
                except Exception:
                    break

    except WebSocketDisconnect:
        await _handle_disconnect(token, student_id, normal=True)
    except Exception as e:
        logger.exception("WebSocket 致命异常")
        await _handle_disconnect(token, student_id, normal=False, error=str(e))
    finally:
        if token:
            ws_manager.disconnect(token)


async def _handle_message(
    websocket: WebSocket,
    message: dict,
    student: Student,
    db,
):
    """处理客户端消息 — 每条消息独立的数据库会话."""
    msg_type = message.get("type", "")
    msg_data = message.get("data", {})

    handlers = {
        "ping": _handle_ping,
        "fullscreen_change": _handle_fullscreen_change,
        "visibility_change": _handle_visibility_change,
    }

    handler = handlers.get(msg_type)
    if handler:
        await handler(websocket, msg_data, student, db)
    else:
        await websocket.send_json(
            {"type": "error", "data": {"message": f"未知消息类型: {msg_type}"}}
        )


async def _handle_ping(websocket: WebSocket, _data: dict, _student: Student, _db):
    """处理 ping."""
    await websocket.send_json({"type": "pong"})


async def _handle_fullscreen_change(
    websocket: WebSocket,
    data: dict,
    student: Student,
    db,
):
    """处理全屏状态变化."""
    is_fullscreen = data.get("is_fullscreen", False)
    student.is_fullscreen = is_fullscreen

    if not is_fullscreen:
        conn_info = ws_manager.get_connection_info(student.id)
        if conn_info is None:
            logger.warning(f"未找到 {student.id} 的连接, 将无法进行记录")
        else:
            log = OperationLog(
                student_id=student.id,
                operation_type="fullscreen_exit",
                description="退出全屏模式",
                level=OperationLevel.CRITICAL,
                ip_address=conn_info.get("ip_address", "None"),
                user_agent=conn_info.get("user_agent", "None"),
            )
            db.add(log)

    await db.commit()

    if not is_fullscreen:
        await ws_manager.send_warning(
            student.id,
            "检测到您已退出全屏模式，请立即返回全屏，否则可能被强制收卷",
            level="critical",
        )

    await websocket.send_json(
        {"type": "fullscreen_change_ack", "data": {"is_fullscreen": is_fullscreen}}
    )


async def _handle_visibility_change(
    websocket: WebSocket,
    data: dict,
    student: Student,
    db,
):
    """处理页面可见性变化."""
    is_visible = data.get("is_visible", True)

    if not is_visible:
        conn_info = ws_manager.get_connection_info(student.id)
        if conn_info is None:
            logger.warning(f"未找到 {student.id} 的连接, 将无法进行记录")
        else:
            log = OperationLog(
                student_id=student.id,
                operation_type="visibility_hidden",
                description="页面变为不可见（可能的切屏行为）",
                level=OperationLevel.WARNING,
                ip_address=conn_info.get("ip_address", "None"),
                user_agent=conn_info.get("user_agent", "None"),
            )
            db.add(log)
        await db.commit()

    await websocket.send_json({"type": "visibility_change_ack", "data": {"is_visible": is_visible}})


async def _handle_disconnect(
    token: str | None,
    student_id: int | None,
    normal: bool = True,
    error: str | None = None,
):
    """处理断开连接 — 自己的短会话."""
    if not student_id:
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Student).where(Student.id == student_id))
        student = result.scalar_one_or_none()

        if not student:
            return

        conn_info = ws_manager.get_connection_info(student_id)

        if conn_info is None:
            logger.warning(f"未找到 {student.id} 的连接, 将无法进行记录")
        else:
            if normal:
                if student.submit_status in (SubmitStatus.SUBMITTED, SubmitStatus.FORCE_SUBMITTED):
                    log = OperationLog(
                        student_id=student_id,
                        operation_type="websocket_disconnected",
                        description="WebSocket 正常断开（考试已结束）",
                        level=OperationLevel.NORMAL,
                        ip_address=conn_info.get("ip_address", "None"),
                        user_agent=conn_info.get("user_agent", "None"),
                    )
                else:
                    log = OperationLog(
                        student_id=student_id,
                        operation_type="websocket_disconnected",
                        description="WebSocket 断开（考试中）",
                        level=OperationLevel.WARNING,
                        ip_address=conn_info.get("ip_address", "None"),
                        user_agent=conn_info.get("user_agent", "None"),
                    )
            else:
                log = OperationLog(
                    student_id=student_id,
                    operation_type="websocket_disconnected",
                    description=f"WebSocket 异常断开: {error or '未知错误'}",
                    level=OperationLevel.CRITICAL,
                    ip_address=conn_info.get("ip_address"),
                    user_agent=conn_info.get("user_agent"),
                )

            db.add(log)

        student.is_fullscreen = False
        await db.commit()
