"""
LLM 数据模型

定义消息、响应、工具调用、流式事件等核心数据结构。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 异常层次
# ──────────────────────────────────────────────

class LLMError(Exception):
    """LLM 调用基础异常"""
    def __init__(self, message: str, provider: str = "", recoverable: bool = False):
        super().__init__(message)
        self.provider = provider
        self.recoverable = recoverable


class LLMConnectionError(LLMError):
    def __init__(self, message: str, provider: str = ""):
        super().__init__(message, provider=provider, recoverable=True)


class LLMAuthError(LLMError):
    def __init__(self, message: str, provider: str = ""):
        super().__init__(message, provider=provider, recoverable=False)


class LLMRateLimitError(LLMError):
    def __init__(self, message: str, provider: str = ""):
        super().__init__(message, provider=provider, recoverable=True)


class LLMResponseError(LLMError):
    def __init__(self, message: str, provider: str = ""):
        super().__init__(message, provider=provider, recoverable=False)


# ──────────────────────────────────────────────
# 枚举
# ──────────────────────────────────────────────

class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class StreamEventType(str, Enum):
    # 基础流式事件
    CONTENT_DELTA = "content_delta"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_DELTA = "tool_call_delta"
    TOOL_CALL_END = "tool_call_end"
    USAGE = "usage"
    DONE = "done"
    ERROR = "error"
    # P1: 工具执行事件
    TOOL_EXECUTE_START = "tool_execute_start"
    TOOL_EXECUTE_END = "tool_execute_end"
    # Loop 控制
    LOOP_START = "loop_start"


# ──────────────────────────────────────────────
# 数据类
# ──────────────────────────────────────────────

@dataclass
class Usage:
    """Token 使用量统计"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


@dataclass
class ToolCall:
    """工具调用请求"""
    id: str
    name: str
    arguments: str | dict  # JSON 字符串或字典


@dataclass
class ToolDefinition:
    """工具定义（发给 LLM 的 function schema）"""
    name: str
    description: str
    parameters: dict[str, Any]

    def to_openai_dict(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolCallResult:
    """工具调用结果"""
    tool_call_id: str
    name: str
    success: bool
    content: str = ""
    error: str | None = None


@dataclass
class Message:
    """聊天消息"""
    role: MessageRole
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None

    def to_openai_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role.value}
        if self.content is not None:
            d["content"] = self.content
        if self.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": tc.arguments if isinstance(tc.arguments, str) else __import__("json").dumps(tc.arguments),
                    },
                }
                for tc in self.tool_calls
            ]
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.name:
            d["name"] = self.name
        return d


@dataclass
class Response:
    """LLM 响应"""
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: Usage = field(default_factory=Usage)


@dataclass
class StreamEvent:
    """流式事件"""
    type: StreamEventType
    data: Any = None
