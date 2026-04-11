"""WebSocket 路由."""

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.models import OperationLevel, OperationLog, Student, SubmitStatus
from app.services.websocket import ws_manager

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 连接端点.

    处理 WebSocket 连接，包括：
    - Token 验证
    - 连接管理
    - 消息处理
    - 断开连接处理

    Args:
        websocket: WebSocket 对象
    """
    token = None
    student_id = None
    db: AsyncSession | None = None

    try:
        # 1. 获取 token 参数
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing token")
            return

        # 2. 获取数据库会话
        db_gen = get_db_session()
        db = await anext(db_gen)

        # 3. 验证 token
        student = await ws_manager.verify_token(token, db)
        if not student:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
            return

        student_id = student.id

        # 4. 建立连接
        await ws_manager.connect(websocket, token, student_id)

        # 5. 更新学生状态
        student.is_fullscreen = True
        await db.commit()

        # 6. 记录连接成功日志
        log = OperationLog(
            student_id=student_id,
            operation_type="websocket_connected",
            description="WebSocket 连接成功",
            level=OperationLevel.NORMAL,
            ip_address=websocket.client.host if websocket.client else None,
            user_agent=websocket.headers.get("user-agent"),
        )
        db.add(log)
        await db.commit()

        # 7. 发送连接成功消息
        await websocket.send_json(
            {
                "type": "connected",
                "data": {"message": "WebSocket 连接成功"},
            }
        )

        # 8. 消息循环
        while True:
            try:
                # 接收消息
                data = await websocket.receive_text()
                message = json.loads(data)
                await handle_message(websocket, message, student_id, db)
            except json.JSONDecodeError:
                await websocket.send_json(
                    {
                        "type": "error",
                        "data": {"message": "Invalid JSON format"},
                    }
                )
            except Exception as e:
                await websocket.send_json(
                    {
                        "type": "error",
                        "data": {"message": f"Error processing message: {str(e)}"},
                    }
                )

    except WebSocketDisconnect:
        # 正常断开连接
        await handle_disconnect(token, student_id, db, normal=True)
    except Exception as e:
        # 异常断开连接
        await handle_disconnect(token, student_id, db, normal=False, error=str(e))
    finally:
        # 清理资源
        if token:
            ws_manager.disconnect(token)
        if db:
            await db.close()


async def handle_message(
    websocket: WebSocket,
    message: dict,
    student_id: int,
    db: AsyncSession,
):
    """处理客户端消息.

    Args:
        websocket: WebSocket 对象
        message: 消息内容
        student_id: 学生 ID
        db: 数据库会话
    """
    msg_type = message.get("type")
    msg_data = message.get("data", {})

    handlers = {
        "ping": handle_ping,
        "fullscreen_change": handle_fullscreen_change,
        "visibility_change": handle_visibility_change,
        "code_save": handle_code_save,
    }

    handler = handlers.get(msg_type)
    if handler:
        await handler(websocket, msg_data, student_id, db)
    else:
        await websocket.send_json(
            {
                "type": "error",
                "data": {"message": f"Unknown message type: {msg_type}"},
            }
        )


async def handle_ping(
    websocket: WebSocket,
    data: dict,
    student_id: int,
    db: AsyncSession,
):
    """处理 ping 消息.

    Args:
        websocket: WebSocket 对象
        data: 消息数据
        student_id: 学生 ID
        db: 数据库会话
    """
    await websocket.send_json({"type": "pong"})


async def handle_fullscreen_change(
    websocket: WebSocket,
    data: dict,
    student_id: int,
    db: AsyncSession,
):
    """处理全屏状态变化消息.

    Args:
        websocket: WebSocket 对象
        data: 消息数据，包含 is_fullscreen 字段
        student_id: 学生 ID
        db: 数据库会话
    """
    is_fullscreen = data.get("is_fullscreen", False)

    # 更新学生状态
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()

    if student:
        student.is_fullscreen = is_fullscreen
        await db.commit()

    # 记录日志
    if is_fullscreen:
        # 进入全屏 - 普通操作
        log = OperationLog(
            student_id=student_id,
            operation_type="fullscreen_enter",
            description="进入全屏模式",
            level=OperationLevel.NORMAL,
        )
    else:
        # 退出全屏 - 严重异常
        log = OperationLog(
            student_id=student_id,
            operation_type="fullscreen_exit",
            description="退出全屏模式",
            level=OperationLevel.CRITICAL,
        )
        # 发送警告通知
        await ws_manager.send_warning(
            student_id,
            "检测到您已退出全屏模式，请立即返回全屏，否则可能被强制收卷",
            level="critical",
        )

    db.add(log)
    await db.commit()

    # 发送确认
    await websocket.send_json(
        {
            "type": "fullscreen_change_ack",
            "data": {"is_fullscreen": is_fullscreen},
        }
    )


async def handle_visibility_change(
    websocket: WebSocket,
    data: dict,
    student_id: int,
    db: AsyncSession,
):
    """处理页面可见性变化消息.

    Args:
        websocket: WebSocket 对象
        data: 消息数据，包含 is_visible 字段
        student_id: 学生 ID
        db: 数据库会话
    """
    is_visible = data.get("is_visible", True)

    # 记录日志
    if is_visible:
        # 页面可见 - 普通操作
        log = OperationLog(
            student_id=student_id,
            operation_type="visibility_visible",
            description="页面变为可见",
            level=OperationLevel.NORMAL,
        )
    else:
        # 页面不可见（切屏）- 异常操作
        log = OperationLog(
            student_id=student_id,
            operation_type="visibility_hidden",
            description="页面变为不可见（可能的切屏行为）",
            level=OperationLevel.WARNING,
        )
        # 发送警告通知
        await ws_manager.send_warning(
            student_id,
            "检测到您切换了页面，请保持在考试页面，多次切屏将被记录",
            level="warning",
        )

    db.add(log)
    await db.commit()

    # 发送确认
    await websocket.send_json(
        {
            "type": "visibility_change_ack",
            "data": {"is_visible": is_visible},
        }
    )


async def handle_code_save(
    websocket: WebSocket,
    data: dict,
    student_id: int,
    db: AsyncSession,
):
    """处理代码保存消息.

    Args:
        websocket: WebSocket 对象
        data: 消息数据，包含 problem_id 和 saved_at 字段
        student_id: 学生 ID
        db: 数据库会话
    """
    problem_id = data.get("problem_id")
    saved_at = data.get("saved_at")

    # 记录日志
    log = OperationLog(
        student_id=student_id,
        operation_type="code_save",
        description=f"保存题目 {problem_id} 的代码",
        level=OperationLevel.NORMAL,
    )
    db.add(log)
    await db.commit()

    # 发送确认
    await websocket.send_json(
        {
            "type": "code_save_ack",
            "data": {
                "problem_id": problem_id,
                "saved_at": saved_at,
            },
        }
    )


async def handle_disconnect(
    token: str | None,
    student_id: int | None,
    db: AsyncSession | None,
    normal: bool = True,
    error: str | None = None,
):
    """处理断开连接.

    Args:
        token: WebSocket Token
        student_id: 学生 ID
        db: 数据库会话
        normal: 是否正常断开
        error: 错误信息（异常断开时）
    """
    if not student_id or not db:
        return

    # 查询学生信息
    result = await db.execute(select(Student).where(Student.id == student_id))
    student = result.scalar_one_or_none()

    if not student:
        return

    if normal:
        # 正常断开（交卷后）
        if student.submit_status in [SubmitStatus.SUBMITTED, SubmitStatus.FORCE_SUBMITTED]:
            log = OperationLog(
                student_id=student_id,
                operation_type="websocket_disconnected",
                description="WebSocket 正常断开（考试已结束）",
                level=OperationLevel.NORMAL,
            )
        else:
            # 考试中正常断开，可能是刷新页面
            log = OperationLog(
                student_id=student_id,
                operation_type="websocket_disconnected",
                description="WebSocket 断开（考试中）",
                level=OperationLevel.WARNING,
            )
    else:
        # 异常断开
        log = OperationLog(
            student_id=student_id,
            operation_type="websocket_disconnected",
            description=f"WebSocket 异常断开: {error or '未知错误'}",
            level=OperationLevel.CRITICAL,
        )

    db.add(log)
    await db.commit()

    # 更新学生状态
    student.is_fullscreen = False
    await db.commit()
