"""
Gateway Server - Gateway 与 FastAPI 集成

将 Gateway 的消息处理能力通过 FastAPI WebSocket 暴露。
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.channel.gateway import Gateway
from src.channel.channels.base import ChannelMessage
from src.web.ws_manager import ConnectionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# Gateway 实例引用
_gateway: Gateway | None = None
_ws_manager = ConnectionManager()


def set_gateway(gateway: Gateway) -> None:
    """设置 Gateway 实例引用。"""
    global _gateway
    _gateway = gateway


def get_gateway() -> Gateway:
    """获取 Gateway 实例。"""
    if _gateway is None:
        raise RuntimeError("Gateway 尚未初始化")
    return _gateway


async def initialize_gateway(
    agents_dir: str | Path = "agents",
    storage_path: str = ".Zclaw",
) -> Gateway:
    """
    初始化 Gateway 并连接所有组件。

    Args:
        agents_dir: Agent 配置目录
        storage_path: 存储路径

    Returns:
        Gateway: 初始化的 Gateway 实例
    """
    from src.brain.agent_factory import AgentFactory

    # 创建 Gateway
    gateway = Gateway(
        storage_path=storage_path,
        default_agent_id="default",
    )

    # 创建并连接 AgentFactory
    factory = AgentFactory(agents_dir)
    factory.load_agents_from_directory()
    gateway.set_agent_factory(factory.create_agent)

    # 加载 Cron 任务
    await gateway.load_cron_from_agents_config(agents_dir)

    # 保存引用
    set_gateway(gateway)

    logger.info("Gateway 初始化完成")
    return gateway


# ──────────────────────────────────────────────
# WebSocket Gateway 端点
# ──────────────────────────────────────────────

@router.websocket("/ws/gateway")
async def websocket_gateway(websocket: WebSocket):
    """
    Gateway WebSocket 端点 - 通过 Gateway 处理消息。

    协议:
    - 客户端发送: {"type": "chat", "data": {"message": "...", "agent_id": "default"}}
    - 客户端发送: {"type": "command", "data": {"command": "...", "args": {...}}}
    - 服务端推送: {"type": "stream_delta", "data": {"content": "..."}}
    - 服务端推送: {"type": "done", "data": null}
    - 服务端推送: {"type": "error", "data": {"message": "..."}}
    """
    gateway = get_gateway()
    conn_id = await _ws_manager.connect(websocket)

    current_task: asyncio.Task | None = None
    cancel_event: asyncio.Event | None = None

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await _ws_manager.send_json(conn_id, {
                    "type": "error",
                    "data": {"message": "无效的 JSON 消息"},
                })
                continue

            msg_type = msg.get("type", "")
            data = msg.get("data", {})

            if msg_type == "chat":
                message = data.get("message", "").strip()
                if not message:
                    continue

                agent_id = data.get("agent_id", gateway._default_agent_id)

                # 取消之前的任务
                if current_task and not current_task.done():
                    cancel_event.set() if cancel_event else None
                    try:
                        await asyncio.wait_for(current_task, timeout=2.0)
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        pass

                cancel_event = asyncio.Event()

                # 创建新的处理任务
                current_task = asyncio.create_task(
                    _handle_gateway_chat(conn_id, message, agent_id, cancel_event)
                )

            elif msg_type == "cancel":
                if current_task and not current_task.done():
                    cancel_event.set() if cancel_event else None
                    await _ws_manager.send_json(conn_id, {
                        "type": "info",
                        "data": {"message": "正在取消..."},
                    })

            elif msg_type == "command":
                await _handle_gateway_command(conn_id, data)

            else:
                await _ws_manager.send_json(conn_id, {
                    "type": "error",
                    "data": {"message": f"未知消息类型: {msg_type}"},
                })

    except WebSocketDisconnect:
        logger.info(f"Gateway WebSocket 客户端断开: {conn_id}")
    except Exception as e:
        logger.error(f"Gateway WebSocket 错误 ({conn_id}): {e}")
    finally:
        _ws_manager.disconnect(conn_id)
        if current_task and not current_task.done():
            if cancel_event:
                cancel_event.set()


async def _handle_gateway_chat(
    conn_id: str,
    message: str,
    agent_id: str,
    cancel_event: asyncio.Event,
) -> None:
    """
    通过 Gateway 处理聊天消息。

    由于 Gateway.handle_message 返回文本响应，
    我们需要通过 Agent.chat_stream 来实现流式响应。
    """
    gateway = get_gateway()

    try:
        # 获取 Agent
        agent = await gateway._agent_factory(agent_id)

        # 使用 Agent 的流式接口
        async for event in agent.chat_stream(message):
            if cancel_event.is_set():
                break

            # 转换事件为 WebSocket 消息
            from src.llm.models import StreamEventType

            if event.type == StreamEventType.CONTENT_DELTA:
                await _ws_manager.send_json(conn_id, {
                    "type": "stream_delta",
                    "data": {"content": event.data},
                })

            elif event.type == StreamEventType.TOOL_EXECUTE_START:
                await _ws_manager.send_json(conn_id, {
                    "type": "tool_start",
                    "data": {
                        "id": event.data.get("id", ""),
                        "name": event.data.get("name", ""),
                    },
                })

            elif event.type == StreamEventType.TOOL_EXECUTE_END:
                await _ws_manager.send_json(conn_id, {
                    "type": "tool_end",
                    "data": {
                        "id": event.data.get("id", ""),
                        "name": event.data.get("name", ""),
                        "success": event.data.get("success", False),
                    },
                })

            elif event.type == StreamEventType.USAGE:
                await _ws_manager.send_json(conn_id, {
                    "type": "usage",
                    "data": {
                        "prompt_tokens": event.data.prompt_tokens,
                        "completion_tokens": event.data.completion_tokens,
                        "total_tokens": event.data.total_tokens,
                    },
                })

            elif event.type == StreamEventType.DONE:
                await _ws_manager.send_json(conn_id, {
                    "type": "done",
                    "data": None,
                })
                break

            elif event.type == StreamEventType.ERROR:
                await _ws_manager.send_json(conn_id, {
                    "type": "error",
                    "data": {"message": str(event.data)},
                })
                break

    except Exception as e:
        logger.error(f"Gateway 聊天处理错误: {e}")
        await _ws_manager.send_json(conn_id, {
            "type": "error",
            "data": {"message": str(e)},
        })
        await _ws_manager.send_json(conn_id, {
            "type": "done",
            "data": None,
        })


async def _handle_gateway_command(conn_id: str, data: dict[str, Any]) -> None:
    """处理 Gateway 命令。"""
    gateway = get_gateway()
    command = data.get("command", "").strip().lower()
    args = data.get("args", {})

    if command == "status":
        status = gateway.get_status()
        await _ws_manager.send_json(conn_id, {
            "type": "status",
            "data": status,
        })

    elif command == "reload":
        # 重新加载 Agent 配置
        from src.brain.agent_factory import AgentFactory
        factory = AgentFactory("agents")
        factory.load_agents_from_directory()
        gateway.set_agent_factory(factory.create_agent)
        await _ws_manager.send_json(conn_id, {
            "type": "info",
            "data": {"message": f"已重新加载 {len(factory.list_agents())} 个 Agent"},
        })

    elif command == "cron":
        # 查看 Cron 任务状态
        cron_status = gateway.cron_scheduler.get_status()
        await _ws_manager.send_json(conn_id, {
            "type": "cron_status",
            "data": cron_status,
        })

    else:
        await _ws_manager.send_json(conn_id, {
            "type": "error",
            "data": {"message": f"未知命令: {command}"},
        })


# ──────────────────────────────────────────────
# REST API Gateway 端点
# ──────────────────────────────────────────────

@router.get("/gateway/status")
async def get_gateway_status():
    """获取 Gateway 状态。"""
    gateway = get_gateway()
    return gateway.get_status()


@router.get("/gateway/sessions")
async def list_gateway_sessions():
    """列出所有 Session。"""
    gateway = get_gateway()
    return {
        "active": gateway.session_manager.get_active_count(),
        "total": len(gateway.session_manager._active_sessions),
    }


@router.post("/gateway/sessions/{session_id}/hibernate")
async def hibernate_session(session_id: str):
    """休眠指定 Session。"""
    gateway = get_gateway()
    gateway.session_manager.hibernate_session(session_id)
    return {"message": f"Session {session_id} 已休眠"}


@router.post("/gateway/sessions/{session_id}/wakeup")
async def wakeup_session(session_id: str):
    """唤醒指定 Session。"""
    gateway = get_gateway()
    gateway.session_manager.wakeup_session(session_id)
    return {"message": f"Session {session_id} 已唤醒"}


# ──────────────────────────────────────────────
# 创建 FastAPI 应用（带 Gateway）
# ──────────────────────────────────────────────

def create_gateway_app(
    agents_dir: str | Path = "agents",
    storage_path: str = ".Zclaw",
) -> tuple[Any, Gateway]:
    """
    创建带 Gateway 的 FastAPI 应用。

    Args:
        agents_dir: Agent 配置目录
        storage_path: 存储路径

    Returns:
        tuple: (FastAPI app, Gateway instance)
    """
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    # 初始化 Gateway
    gateway = asyncio.run(initialize_gateway(agents_dir, storage_path))

    app = FastAPI(
        title="Zclaw Gateway",
        description="24/7 自主运行 Gateway",
        version="0.1.0",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 挂载路由
    app.include_router(router)

    return app, gateway


async def start_gateway_server(
    agents_dir: str | Path = "agents",
    storage_path: str = ".Zclaw",
    host: str = "0.0.0.0",
    port: int = 8080,
) -> None:
    """
    启动 Gateway Web 服务器。

    Args:
        agents_dir: Agent 配置目录
        storage_path: 存储路径
        host: 监听地址
        port: 监听端口
    """
    import uvicorn

    app, gateway = create_gateway_app(agents_dir, storage_path)

    # 启动 Gateway 主循环（但不阻塞）
    asyncio.create_task(gateway.start())

    logger.info(f"启动 Gateway Web 服务器: http://{host}:{port}")

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
        ws_ping_interval=30,
        ws_ping_timeout=60,
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        agents_dir = sys.argv[1]
    else:
        agents_dir = "agents"

    asyncio.run(start_gateway_server(agents_dir))
