"""
Web API 路由

提供 REST API 和 WebSocket 端点，连接前端和 Agent 后端。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException

from src.llm.models import StreamEventType
from src.web.schemas import (
    AgentStatus,
    ChatRequest,
    ChatResponse,
    CostInfo,
    ErrorResponse,
    FileEntry,
    FileInfo,
    HistoryMessage,
    HistoryResponse,
    SessionInfo,
    SessionListResponse,
    SessionLoadResponse,
    SuccessResponse,
    ToolInfo,
    WSMessageType,
)
from src.web.ws_manager import ConnectionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# ──────────────────────────────────────────────
# WebSocket 管理器（模块级单例）
# ──────────────────────────────────────────────
ws_manager = ConnectionManager()

# Agent 实例引用（由 server.py 设置）
_agent = None
_settings = None


def set_agent(agent) -> None:
    """设置 Agent 实例引用。"""
    global _agent
    _agent = agent


def set_settings(settings) -> None:
    """设置 Settings 实例引用。"""
    global _settings
    _settings = settings


def get_agent():
    """获取 Agent 实例。"""
    if _agent is None:
        raise RuntimeError("Agent 尚未初始化")
    return _agent


# ──────────────────────────────────────────────
# WebSocket 端点
# ──────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 端点 - 实时对话。

    协议:
    - 客户端发送: {"type": "chat", "data": {"message": "..."}}
    - 服务端推送: {"type": "stream_delta", "data": {"content": "..."}}
    - 服务端推送: {"type": "tool_start", "data": {"id": "...", "name": "..."}}
    - 服务端推送: {"type": "tool_end", "data": {"id": "...", "name": "...", "success": true}}
    - 服务端推送: {"type": "usage", "data": {"prompt_tokens": 100, "completion_tokens": 200}}
    - 服务端推送: {"type": "done", "data": null}
    - 服务端推送: {"type": "error", "data": {"message": "..."}}
    - 服务端推送: {"type": "permission", "data": {"request_id": "...", ...}}
    """
    conn_id = await ws_manager.connect(websocket)

    # 设置权限回调
    async def web_permission_callback(request):
        """Web 模式的权限回调 - 通过 WebSocket 向用户请求确认。"""
        from src.security.permission import DangerLevel, PermissionResponse, PermissionDecision

        # SAFE 级别由 PermissionManager 自动处理（无需回调）
        # 此处只处理 CONFIRM 和 DANGEROUS 级别

        request_id = uuid.uuid4().hex[:8]

        # 尝试获取 arguments 的可序列化版本
        try:
            args_for_client = dict(request.arguments)
        except Exception:
            args_for_client = str(request.arguments)

        allowed = await ws_manager.request_permission(
            conn_id=conn_id,
            request_id=request_id,
            tool_name=request.tool_name,
            arguments=args_for_client,
            danger_level=request.danger_level.value,
        )

        if allowed:
            return PermissionResponse(
                decision=PermissionDecision.ALLOW,
                reason="用户批准",
                auto=False,
            )
        else:
            return PermissionResponse(
                decision=PermissionDecision.DENY,
                reason="用户拒绝或超时",
                auto=False,
            )

    if _agent and _agent.permission_manager:
        _agent.permission_manager.set_auto_confirm(False)
        _agent.permission_manager.set_confirm_callback(web_permission_callback)

    # 当前正在运行的生成任务
    current_task: asyncio.Task | None = None
    cancel_event = asyncio.Event()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws_manager.send_json(conn_id, {
                    "type": "error",
                    "data": {"message": "无效的 JSON 消息"},
                })
                continue

            msg_type = msg.get("type", "")
            data = msg.get("data", {})

            if msg_type == WSMessageType.CHAT:
                message = data.get("message", "").strip()
                if not message:
                    continue

                # 取消之前的任务
                if current_task and not current_task.done():
                    cancel_event.set()
                    try:
                        await asyncio.wait_for(current_task, timeout=2.0)
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        pass
                cancel_event.clear()

                # 创建新的生成任务
                current_task = asyncio.create_task(
                    _handle_chat(conn_id, message, cancel_event)
                )

            elif msg_type == WSMessageType.CANCEL:
                if current_task and not current_task.done():
                    cancel_event.set()
                    await ws_manager.send_json(conn_id, {
                        "type": "info",
                        "data": {"message": "正在取消生成..."},
                    })

            elif msg_type == WSMessageType.PERMISSION:
                # 处理权限响应
                request_id = data.get("request_id", "")
                allowed = data.get("allowed", False)
                ws_manager.resolve_permission(request_id, allowed)

            elif msg_type == WSMessageType.COMMAND:
                await _handle_command(conn_id, data)

            else:
                await ws_manager.send_json(conn_id, {
                    "type": "error",
                    "data": {"message": f"未知消息类型: {msg_type}"},
                })

    except WebSocketDisconnect:
        logger.info(f"客户端断开连接: {conn_id}")
    except Exception as e:
        logger.error(f"WebSocket 错误 ({conn_id}): {e}")
    finally:
        ws_manager.disconnect(conn_id)
        if current_task and not current_task.done():
            cancel_event.set()


async def _handle_chat(
    conn_id: str, message: str, cancel_event: asyncio.Event
) -> None:
    """
    处理聊天消息并流式推送结果。

    将 Agent 的 StreamEvent 转换为 WebSocket 消息推送给客户端。
    """
    agent = get_agent()
    round_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    try:
        async for event in agent.chat_stream(message):
            if cancel_event.is_set():
                break

            if event.type == StreamEventType.CONTENT_DELTA:
                await ws_manager.send_json(conn_id, {
                    "type": "stream_delta",
                    "data": {"content": event.data},
                })

            elif event.type == StreamEventType.TOOL_EXECUTE_START:
                await ws_manager.send_json(conn_id, {
                    "type": "tool_start",
                    "data": {
                        "id": event.data.get("id", ""),
                        "name": event.data.get("name", ""),
                    },
                })

            elif event.type == StreamEventType.TOOL_EXECUTE_END:
                await ws_manager.send_json(conn_id, {
                    "type": "tool_end",
                    "data": {
                        "id": event.data.get("id", ""),
                        "name": event.data.get("name", ""),
                        "success": event.data.get("success", False),
                        "error": event.data.get("error"),
                    },
                })

            elif event.type == StreamEventType.LOOP_START:
                await ws_manager.send_json(conn_id, {
                    "type": "loop_start",
                    "data": {"round": event.data.get("round", 1)},
                })

            elif event.type == StreamEventType.USAGE:
                round_usage["prompt_tokens"] += event.data.prompt_tokens
                round_usage["completion_tokens"] += event.data.completion_tokens
                round_usage["total_tokens"] += event.data.total_tokens
                await ws_manager.send_json(conn_id, {
                    "type": "usage",
                    "data": round_usage,
                })

            elif event.type == StreamEventType.DONE:
                await ws_manager.send_json(conn_id, {
                    "type": "done",
                    "data": None,
                })

            elif event.type == StreamEventType.ERROR:
                await ws_manager.send_json(conn_id, {
                    "type": "error",
                    "data": {"message": str(event.data)},
                })

    except Exception as e:
        logger.error(f"聊天处理错误: {e}")
        await ws_manager.send_json(conn_id, {
            "type": "error",
            "data": {"message": str(e)},
        })
    finally:
        if not cancel_event.is_set():
            await ws_manager.send_json(conn_id, {
                "type": "done",
                "data": None,
            })


async def _handle_command(conn_id: str, data: dict[str, Any]) -> None:
    """处理斜杠命令。"""
    agent = get_agent()
    command = data.get("command", "").strip().lower()
    args = data.get("args", {})

    if command == "clear":
        agent.clear_history()
        await ws_manager.send_json(conn_id, {
            "type": "info",
            "data": {"message": "对话历史已清空。"},
        })

    elif command == "info":
        s = agent._settings
        pc = s.llm.providers[s.llm.default_provider]
        info = (
            f"Provider: {s.llm.default_provider}\n"
            f"模型: {pc.model}\n"
            f"Base URL: {pc.base_url}\n"
            f"最大上下文: {pc.max_context_tokens} tokens\n"
            f"温度: {s.llm.temperature}\n"
            f"工具: {len(agent.tools)} 个已注册\n"
            f"状态: {agent.state.value}"
        )
        await ws_manager.send_json(conn_id, {
            "type": "info",
            "data": {"message": info},
        })

    elif command == "compact":
        if agent.context_manager:
            msgs = agent.loop.messages
            agent.context_manager.prepare_messages(msgs, force_compress=True)
            await ws_manager.send_json(conn_id, {
                "type": "info",
                "data": {"message": "上下文已压缩。"},
            })
        else:
            await ws_manager.send_json(conn_id, {
                "type": "error",
                "data": {"message": "上下文管理器未启用"},
            })

    else:
        await ws_manager.send_json(conn_id, {
            "type": "error",
            "data": {"message": f"未知命令: {command}"},
        })


# ──────────────────────────────────────────────
# REST API 端点
# ──────────────────────────────────────────────

@router.get("/status", response_model=AgentStatus)
async def get_status():
    """获取 Agent 状态信息。"""
    agent = get_agent()
    s = agent._settings
    provider = s.llm.default_provider
    model = s.llm.providers[provider].model
    usage = agent.loop.usage

    return AgentStatus(
        state=agent.state.value,
        provider=provider,
        model=model,
        tools_count=len(agent.tools),
        tool_names=agent.tools.tool_names,
        session_id=agent.session_id,
        round=agent.loop.round,
        tool_call_count=agent.loop.tool_call_count,
        usage={
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
        },
        message_count=len(agent.loop.messages),
    )


@router.get("/tools", response_model=list[ToolInfo])
async def get_tools():
    """获取已注册工具列表。"""
    agent = get_agent()
    tools = []
    for name, tool in agent.tools.all_tools.items():
        tools.append(ToolInfo(
            name=tool.name,
            description=tool.description,
            category=tool.metadata.category if tool.metadata else "",
            danger_level=tool.danger_level.value,
            parameters=[
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                }
                for p in (tool.parameters or [])
            ],
        ))
    return tools


@router.get("/history", response_model=HistoryResponse)
async def get_history():
    """获取对话历史。"""
    agent = get_agent()
    messages = []
    for msg in agent.loop.messages:
        if msg.role.value == "system":
            continue  # 不返回 system prompt
        messages.append(HistoryMessage(
            role=msg.role.value,
            content=msg.content,
            tool_calls=[
                {
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments,
                }
                for tc in (msg.tool_calls or [])
            ] or None,
            tool_call_id=msg.tool_call_id,
            name=msg.name,
        ))
    return HistoryResponse(messages=messages, count=len(messages))


@router.post("/clear", response_model=SuccessResponse)
async def clear_history():
    """清空对话历史。"""
    agent = get_agent()
    agent.clear_history()
    return SuccessResponse(message="对话历史已清空")


@router.get("/files/list", response_model=list[FileEntry])
async def list_files(path: str = "."):
    """
    列出目录内容。

    Args:
        path: 目录路径（相对于工作目录或绝对路径）
    """
    try:
        target = Path(path).resolve()

        # 安全检查
        deny_dirs = _settings.security.path_restrictions.get("deny", []) if _settings else []
        for deny_dir in deny_dirs:
            deny_path = Path(deny_dir).resolve()
            try:
                target.relative_to(deny_path)
                raise HTTPException(status_code=403, detail="访问被拒绝: 受保护目录")
            except ValueError:
                pass  # 不在禁止目录下

        if not target.exists():
            raise HTTPException(status_code=404, detail=f"路径不存在: {path}")

        if not target.is_dir():
            raise HTTPException(status_code=400, detail=f"不是目录: {path}")

        entries = []
        try:
            for item in target.iterdir():
                # 跳过隐藏文件
                if item.name.startswith("."):
                    continue
                try:
                    stat = item.stat()
                    entries.append(FileEntry(
                        name=item.name,
                        path=str(item),
                        is_dir=item.is_dir(),
                        size=stat.st_size if not item.is_dir() else 0,
                        modified=_format_time(stat.st_mtime),
                    ))
                except (PermissionError, OSError):
                    continue
        except PermissionError:
            raise HTTPException(status_code=403, detail="权限不足")

        # 排序: 目录在前，按名称排序
        entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))
        return entries

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/files/read", response_model=FileInfo)
async def read_file(path: str, offset: int = 0, limit: int = 500):
    """
    读取文件内容。

    Args:
        path: 文件路径
        offset: 起始行号（0-based）
        limit: 最大行数
    """
    try:
        target = Path(path).resolve()

        # 安全检查
        deny_dirs = _settings.security.path_restrictions.get("deny", []) if _settings else []
        for deny_dir in deny_dirs:
            deny_path = Path(deny_dir).resolve()
            try:
                target.relative_to(deny_path)
                raise HTTPException(status_code=403, detail="访问被拒绝: 受保护目录")
            except ValueError:
                pass

        if not target.exists():
            raise HTTPException(status_code=404, detail=f"文件不存在: {path}")

        if target.is_dir():
            raise HTTPException(status_code=400, detail=f"是目录而非文件: {path}")

        # 限制文件大小（5MB）
        if target.stat().st_size > 5 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="文件过大（最大 5MB）")

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except PermissionError:
            raise HTTPException(status_code=403, detail="权限不足")

        lines = content.splitlines()
        total_lines = len(lines)

        if offset > 0 or limit < total_lines:
            lines = lines[offset:offset + limit]
            content = "\n".join(lines)
            # 添加行号提示
            content = f"[显示第 {offset + 1}-{offset + len(lines)} 行，共 {total_lines} 行]\n\n{content}"

        return FileInfo(
            path=str(target),
            content=content,
            size=target.stat().st_size,
            lines=total_lines,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions():
    """列出保存的会话。"""
    agent = get_agent()
    try:
        sessions = agent.session_manager.list_sessions()
        return SessionListResponse(sessions=[
            SessionInfo(
                session_id=s.get("session_id", s.get("id", "")),
                created_at=s.get("created_at", s.get("timestamp", "")),
                message_count=s.get("message_count", 0),
            )
            for s in sessions
        ])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/load", response_model=SuccessResponse)
async def load_session(session_id: str):
    """加载会话。"""
    agent = get_agent()
    try:
        messages = agent.session_manager.load(session_id)
        if messages is None:
            raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")
        # 将历史消息恢复到 Agent Loop
        agent.loop.clear_history()
        for msg in messages:
            agent.loop.add_message(msg)
        return SuccessResponse(message=f"已加载会话: {session_id}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cost", response_model=CostInfo)
async def get_cost():
    """获取费用信息。"""
    agent = get_agent()
    usage = agent.loop.usage
    rounds = agent.loop.round
    avg = usage.total_tokens / rounds if rounds > 0 else 0

    return CostInfo(
        total_tokens=usage.total_tokens,
        total_rounds=rounds,
        average_tokens_per_round=round(avg, 1),
    )


@router.get("/config")
async def get_config():
    """获取当前配置信息（脱敏）。"""
    if _settings is None:
        raise HTTPException(status_code=500, detail="配置未加载")

    s = _settings
    providers = {}
    for name, pc in s.llm.providers.items():
        providers[name] = {
            "base_url": pc.base_url,
            "model": pc.model,
            "max_context_tokens": pc.max_context_tokens,
            "supports_tools": pc.supports_tools,
            "supports_vision": pc.supports_vision,
            "supports_streaming": pc.supports_streaming,
            "api_key": pc.api_key[:8] + "..." if len(pc.api_key) > 8 else "***",
        }

    return {
        "llm": {
            "default_provider": s.llm.default_provider,
            "fallback_providers": s.llm.fallback_providers,
            "temperature": s.llm.temperature,
            "max_tokens": s.llm.max_tokens,
            "providers": providers,
        },
        "agent": {
            "max_loop_rounds": s.agent.max_loop_rounds,
            "planning_mode": s.agent.planning_mode,
        },
        "web": {
            "host": s.web.host,
            "port": s.web.port,
        },
    }


def _format_time(timestamp: float) -> str:
    """格式化时间戳。"""
    from datetime import datetime
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (OSError, ValueError):
        return ""
