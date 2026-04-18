"""
OpenAI 兼容 LLM 提供者

适用于所有使用 OpenAI API 格式的服务（百炼、Ollama、Azure 等）。
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from src.llm.base import BaseProvider
from src.llm.models import (
    LLMConnectionError,
    LLMResponseError,
    Message,
    Response,
    StreamEvent,
    StreamEventType,
    ToolCall,
    ToolDefinition,
    Usage,
)

logger = logging.getLogger(__name__)


class OpenAICompatProvider(BaseProvider):
    """OpenAI 兼容 API 提供者"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 8192,
    ) -> Response:
        """发送聊天请求。"""
        openai_messages = [m.to_openai_dict() for m in messages]
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools and self.supports_tools:
            kwargs["tools"] = [t.to_openai_dict() for t in tools]
            kwargs["tool_choice"] = "auto"

        try:
            response = await self._client.chat.completions.create(**kwargs)
        except Exception as e:
            error_msg = str(e)
            if "Connection" in error_msg:
                raise LLMConnectionError(error_msg, provider=self.name)
            raise LLMResponseError(error_msg, provider=self.name)

        choice = response.choices[0]
        content = choice.message.content or ""

        tool_calls = []
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                args_str = tc.function.arguments or "{}"
                # 尝试解析，如果失败则用空对象（避免 MiniMax API 返回畸形 JSON 的问题）
                try:
                    import json
                    json.loads(args_str)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"LLM 返回了无效的 tool arguments，已替换为空对象: {repr(args_str)[:100]}")
                    args_str = "{}"
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args_str,
                ))

        usage = Usage()
        if response.usage:
            usage = Usage(
                prompt_tokens=response.usage.prompt_tokens or 0,
                completion_tokens=response.usage.completion_tokens or 0,
                total_tokens=response.usage.total_tokens or 0,
            )

        return Response(
            content=content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
        )

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float = 0.3,
        max_tokens: int = 8192,
    ) -> AsyncIterator[StreamEvent]:
        """发送流式聊天请求。"""
        openai_messages = [m.to_openai_dict() for m in messages]
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": openai_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools and self.supports_tools:
            kwargs["tools"] = [t.to_openai_dict() for t in tools]
            kwargs["tool_choice"] = "auto"

        try:
            stream = await self._client.chat.completions.create(**kwargs)
        except Exception as e:
            error_msg = str(e)
            if "Connection" in error_msg:
                raise LLMConnectionError(error_msg, provider=self.name)
            raise LLMResponseError(error_msg, provider=self.name)

        async with stream:
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                # 内容增量
                if delta.content:
                    yield StreamEvent(
                        type=StreamEventType.CONTENT_DELTA,
                        data=delta.content,
                    )

                # 工具调用增量
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        if tc_delta.id:
                            yield StreamEvent(
                                type=StreamEventType.TOOL_CALL_START,
                                data={
                                    "index": tc_delta.index,
                                    "id": tc_delta.id,
                                    "name": tc_delta.function.name if tc_delta.function else "",
                                },
                            )
                        if tc_delta.function and tc_delta.function.arguments:
                            yield StreamEvent(
                                type=StreamEventType.TOOL_CALL_DELTA,
                                data={
                                    "index": tc_delta.index,
                                    "delta": tc_delta.function.arguments,
                                },
                            )

                # Token 使用量
                if chunk.usage:
                    yield StreamEvent(
                        type=StreamEventType.USAGE,
                        data=Usage(
                            prompt_tokens=chunk.usage.prompt_tokens or 0,
                            completion_tokens=chunk.usage.completion_tokens or 0,
                            total_tokens=chunk.usage.total_tokens or 0,
                        ),
                    )

                # 结束原因
                finish_reason = chunk.choices[0].finish_reason
                if finish_reason and finish_reason != "null":
                    if finish_reason == "tool_calls" and delta.tool_calls:
                        for tc_delta in delta.tool_calls:
                            yield StreamEvent(
                                type=StreamEventType.TOOL_CALL_END,
                                data={
                                    "index": tc_delta.index,
                                    "id": tc_delta.id or "",
                                    "name": tc_delta.function.name if tc_delta.function else "",
                                    "arguments": tc_delta.function.arguments if tc_delta.function else "",
                                },
                            )

        yield StreamEvent(type=StreamEventType.DONE, data=None)
