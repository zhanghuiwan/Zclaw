"""
LLM 提供者抽象基类
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from src.llm.models import (
    Message,
    Response,
    StreamEvent,
    ToolDefinition,
    Usage,
)


class BaseProvider(ABC):
    """LLM 提供者抽象基类"""

    def __init__(self, name: str, base_url: str, api_key: str, model: str, **kwargs):
        self.name = name
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.max_context_tokens = kwargs.get("max_context_tokens", 32768)
        self.supports_tools = kwargs.get("supports_tools", False)
        self.supports_vision = kwargs.get("supports_vision", False)
        self.supports_streaming = kwargs.get("supports_streaming", True)

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 8192,
    ) -> Response:
        """发送聊天请求并获取完整响应。"""
        ...

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 8192,
    ) -> AsyncIterator[StreamEvent]:
        """发送聊天请求并获取流式响应。"""
        ...

    async def count_tokens(self, messages: list[Message]) -> int:
        """估算消息列表的 token 数量（粗略估计：1 token ≈ 4 字符）。"""
        total_chars = 0
        for msg in messages:
            if msg.content:
                total_chars += len(msg.content)
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    total_chars += len(tc.name) + len(str(tc.arguments))
        return total_chars // 4 + len(messages) * 4

    def __repr__(self) -> str:
        return (
            f"Provider(name='{self.name}', model='{self.model}', "
            f"base_url='{self.base_url}')"
        )
