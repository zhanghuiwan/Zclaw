"""
Gateway Server - Gateway 与 FastAPI 集成

将 Gateway 的消息处理能力通过 FastAPI WebSocket 暴露。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
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

# 权限响应存储（connection_id -> {tool_call_id: (allowed, event)}）
_permission_responses: dict[str, dict[str, tuple[bool, asyncio.Event]]] = {}


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
    enable_stdio: bool = False,
) -> Gateway:
    """
    初始化 Gateway 并连接所有组件。

    Args:
        agents_dir: Agent 配置目录
        storage_path: 存储路径
        enable_stdio: 是否启用 STDIO 通道

    Returns:
        Gateway: 初始化的 Gateway 实例
    """
    from src.brain.agent_pool import AgentPool

    # 创建 Gateway（传入 agents_dir）
    gateway = Gateway(
        storage_path=storage_path,
        default_agent_id="default",
        agents_dir=agents_dir,
    )

    # 创建并连接 AgentPool
    pool = AgentPool(agents_dir=agents_dir)
    gateway.set_agent_pool(pool)

    # 注册 STDIO 通道（如果启用）
    if enable_stdio:
        from src.channel.channels.stdio import StdioChannel
        stdio_channel = StdioChannel()
        gateway.register_channel(stdio_channel)
        logger.info("STDIO 通道已注册")

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

                # 等待之前的任务完成（带超时）
                if current_task and not current_task.done():
                    cancel_event.set() if cancel_event else None
                    try:
                        await asyncio.wait_for(current_task, timeout=60.0)
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

            elif msg_type == "permission_response":
                tool_call_id = data.get("tool_call_id")
                allowed = data.get("allowed", False)
                # 权限响应处理：更新等待状态并触发事件
                if conn_id in _permission_responses and tool_call_id in _permission_responses[conn_id]:
                    resp_data = _permission_responses[conn_id][tool_call_id]
                    _permission_responses[conn_id][tool_call_id] = (allowed, resp_data[1])
                    resp_data[1].set()

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
        logger.error(f"Gateway WebSocket 错误 ({conn_id}): {e}", exc_info=True)
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
    agent = None

    try:
        # 获取 Agent
        agent = await gateway._agent_pool.get_agent(agent_id)

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

            elif event.type == StreamEventType.LOOP_START:
                await _ws_manager.send_json(conn_id, {
                    "type": "loop_start",
                    "data": {"round": event.data.get("round", 1)},
                })

            elif event.type == StreamEventType.PERMISSION_REQUEST:
                # 发送权限请求给客户端并等待响应
                perm_data = event.data
                await _ws_manager.send_json(conn_id, {
                    "type": "permission",
                    "data": {
                        "tool_call_id": perm_data.get("tool_call_id"),
                        "tool_name": perm_data.get("tool_name"),
                        "arguments": perm_data.get("arguments"),
                        "danger_level": perm_data.get("danger_level"),
                    },
                })

                # 创建权限响应等待
                tool_call_id = perm_data.get("tool_call_id")
                event_ready = asyncio.Event()
                logger.info(f"[DEBUG] 等待权限响应: tool_call_id={tool_call_id}")

                # 存储等待事件
                if conn_id not in _permission_responses:
                    _permission_responses[conn_id] = {}
                _permission_responses[conn_id][tool_call_id] = (False, event_ready)
                logger.info(f"[DEBUG] 权限请求已发送，等待响应: conn_id={conn_id}, tool_call_id={tool_call_id}")

                # 等待权限响应（由 websocket_gateway 中的消息处理设置）
                # 使用 polling loop 以避免阻塞事件循环
                while not event_ready.is_set():
                    await asyncio.sleep(0.1)

                logger.info(f"[DEBUG] 权限响应到达，准备处理: tool_call_id={tool_call_id}")

                # 获取响应结果
                resp_data = _permission_responses[conn_id].pop(tool_call_id, (False, None))
                allowed = resp_data[0]
                agent.loop.resolve_permission(tool_call_id, allowed)

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
        # 等待消息发送完成
        await asyncio.sleep(0.1)
    finally:
        # 释放 Agent
        if agent is not None and gateway._agent_pool:
            await gateway._agent_pool.release_agent(agent_id)


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
        # 重新加载 Agent 配置（创建新的 AgentPool）
        from src.brain.agent_pool import AgentPool
        pool = AgentPool(agents_dir="agents")
        gateway.set_agent_pool(pool)
        await _ws_manager.send_json(conn_id, {
            "type": "info",
            "data": {"message": f"已重新加载 AgentPool"},
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

async def create_gateway_app(
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
    gateway = await initialize_gateway(agents_dir, storage_path)

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

    # 根路径
    @app.get("/")
    async def root():
        return {
            "name": "Zclaw Gateway",
            "version": "0.1.0",
            "status": "running",
            "docs": "/docs",
            "websocket": "/api/ws/gateway",
            "api": "/api/gateway/status",
        }

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

    app, gateway = await create_gateway_app(agents_dir, storage_path)

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


async def start_gateway_stdio(
    agents_dir: str | Path = "agents",
    storage_path: str = ".Zclaw",
) -> None:
    """
    启动 Gateway STDIO 模式（交互式 CLI）。

    Args:
        agents_dir: Agent 配置目录
        storage_path: 存储路径
    """
    from src.channel.channels.stdio import StdioChannel

    # 初始化 Gateway（启用 STDIO）
    gateway = await initialize_gateway(
        agents_dir=agents_dir,
        storage_path=storage_path,
        enable_stdio=True,
    )

    # 启动 Gateway
    await gateway.start()

    # 获取 STDIO 通道
    stdio_channel = gateway.get_channel("stdio")
    if not stdio_channel:
        logger.error("STDIO 通道未注册")
        return

    logger.info("Gateway STDIO 模式已启动，输入 /quit 退出")

    # 主循环
    try:
        while gateway.is_running:
            # 读取用户输入
            user_input = await stdio_channel.read_line(" > ")
            if user_input is None:
                break

            # 处理命令
            if user_input.strip() == "/quit":
                break

            # 通过 Gateway 处理消息
            response = await gateway.handle_message(
                channel_name="stdio",
                raw_message={"text": user_input},
            )

            # 发送响应
            if response:
                await stdio_channel.send(response)

    except KeyboardInterrupt:
        logger.info("收到键盘中断")
    finally:
        await gateway.shutdown()
        logger.info("Gateway STDIO 模式已关闭")


if __name__ == "__main__":
    import sys
    import argparse
    import signal

    parser = argparse.ArgumentParser(description="Zclaw Gateway Server")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", type=int, default=8080, help="监听端口")
    parser.add_argument("--agents-dir", type=str, default="agents", help="Agent 配置目录")
    parser.add_argument("--storage-path", type=str, default=".Zclaw", help="存储路径")
    parser.add_argument("--no-pid", action="store_true", help="不写入 PID 文件")

    args = parser.parse_args()

    # 写入 PID 文件
    pid_dir = Path.home() / ".Zclaw"
    pid_file = pid_dir / "gateway.pid"

    if not args.no_pid:
        pid_dir.mkdir(parents=True, exist_ok=True)
        pid_file.write_text(str(os.getpid()))
        print(f"PID file: {pid_file}")

    # 优雅关闭处理
    shutdown_event = asyncio.Event()

    def signal_handler(sig, frame):
        print(f"\n收到信号 {sig}, 准备关闭...")
        shutdown_event.set()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    async def run_server():
        await start_gateway_server(
            agents_dir=args.agents_dir,
            storage_path=args.storage_path,
            host=args.host,
            port=args.port,
        )

    async def run_with_shutdown():
        server_task = asyncio.create_task(run_server())

        # 等待关闭信号
        await shutdown_event.wait()

        # 清理 PID 文件
        if pid_file.exists():
            pid_file.unlink()

        print("Gateway 已关闭")

    try:
        asyncio.run(run_with_shutdown())
    except KeyboardInterrupt:
        pass
    finally:
        if pid_file.exists():
            pid_file.unlink()
