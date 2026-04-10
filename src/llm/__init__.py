"""
LLM 模块

提供大语言模型的抽象接口和多提供者路由。
"""

from src.llm.base import BaseProvider
from src.llm.models import (
    LLMError,
    LLMConnectionError,
    LLMAuthError,
    LLMRateLimitError,
    LLMResponseError,
    Message,
    MessageRole,
    Response,
    ToolCall,
    ToolCallResult,
    ToolDefinition,
    Usage,
    StreamEvent,
    StreamEventType,
)
from src.llm.openai_compat import OpenAICompatProvider
from src.llm.router import LLMRouter, create_provider

__all__ = [
    "BaseProvider",
    "OpenAICompatProvider",
    "LLMRouter",
    "create_provider",
    "LLMError",
    "LLMConnectionError",
    "LLMAuthError",
    "LLMRateLimitError",
    "LLMResponseError",
    "Message",
    "MessageRole",
    "Response",
    "ToolCall",
    "ToolCallResult",
    "ToolDefinition",
    "Usage",
    "StreamEvent",
    "StreamEventType",
]
