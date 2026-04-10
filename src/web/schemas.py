"""
Web API 数据模型

定义 REST API 和 WebSocket 通信使用的 Pydantic 模型。
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# WebSocket 消息类型
# ──────────────────────────────────────────────

class WSMessageType(str, Enum):
    """WebSocket 消息类型"""
    # 客户端 → 服务端
    CHAT = "chat"                      # 发送对话消息
    CANCEL = "cancel"                  # 取消当前生成
    COMMAND = "command"                # 发送斜杠命令

    # 服务端 → 客户端
    STREAM_DELTA = "stream_delta"      # 流式内容片段
    TOOL_START = "tool_start"          # 工具开始执行
    TOOL_END = "tool_end"              # 工具执行完成
    LOOP_START = "loop_start"          # 新一轮循环开始
    USAGE = "usage"                    # Token 用量统计
    DONE = "done"                      # 生成完成
    ERROR = "error"                    # 错误
    INFO = "info"                      # 信息通知
    PERMISSION = "permission"          # 权限请求


class WSMessage(BaseModel):
    """WebSocket 消息基类"""
    type: WSMessageType
    data: dict[str, Any] = Field(default_factory=dict)


class WSChatMessage(WSMessage):
    """客户端发送的对话消息"""
    type: WSMessageType = WSMessageType.CHAT
    data: dict[str, Any] = Field(default_factory=lambda: {
        "message": ""
    })


class WSCommandMessage(WSMessage):
    """客户端发送的命令消息"""
    type: WSMessageType = WSMessageType.COMMAND
    data: dict[str, Any] = Field(default_factory=lambda: {
        "command": "",
        "args": {}
    })


class WSPermissionMessage(WSMessage):
    """服务端发送的权限请求"""
    type: WSMessageType = WSMessageType.PERMISSION
    data: dict[str, Any] = Field(default_factory=lambda: {
        "request_id": "",
        "tool_name": "",
        "arguments": {},
        "danger_level": "safe",
    })


class WSPermissionResponse(WSMessage):
    """客户端发送的权限响应"""
    type: WSMessageType = WSMessageType.PERMISSION
    data: dict[str, Any] = Field(default_factory=lambda: {
        "request_id": "",
        "allowed": False,
    })


# ──────────────────────────────────────────────
# REST API 模型
# ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    """聊天请求"""
    message: str = Field(..., min_length=1, max_length=100000, description="用户消息")


class ChatResponse(BaseModel):
    """聊天响应（非流式）"""
    content: str = ""
    finish_reason: str = "stop"
    usage: dict[str, int] = Field(default_factory=dict)


class ToolInfo(BaseModel):
    """工具信息"""
    name: str
    description: str
    category: str = ""
    danger_level: str = "safe"
    parameters: list[dict[str, Any]] = Field(default_factory=list)


class FileEntry(BaseModel):
    """文件/目录条目"""
    name: str
    path: str
    is_dir: bool
    size: int = 0
    modified: str = ""


class FileInfo(BaseModel):
    """文件内容信息"""
    path: str
    content: str
    size: int
    lines: int


class SessionInfo(BaseModel):
    """会话信息"""
    session_id: str
    created_at: str
    message_count: int


class SessionListResponse(BaseModel):
    """会话列表响应"""
    sessions: list[SessionInfo]


class SessionLoadResponse(BaseModel):
    """会话加载响应"""
    session_id: str
    messages: list[dict[str, Any]]
    message_count: int


class AgentStatus(BaseModel):
    """Agent 状态信息"""
    state: str
    provider: str
    model: str
    tools_count: int
    tool_names: list[str]
    session_id: str
    round: int
    tool_call_count: int
    usage: dict[str, int]
    message_count: int


class ErrorResponse(BaseModel):
    """错误响应"""
    error: str
    detail: str = ""


class SuccessResponse(BaseModel):
    """成功响应"""
    success: bool = True
    message: str = ""


class HistoryMessage(BaseModel):
    """对话历史消息"""
    role: str
    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class HistoryResponse(BaseModel):
    """对话历史响应"""
    messages: list[HistoryMessage]
    count: int


class CostInfo(BaseModel):
    """费用信息"""
    total_tokens: int
    total_rounds: int
    average_tokens_per_round: float
    estimated_cost: float = 0.0
    currency: str = "USD"
