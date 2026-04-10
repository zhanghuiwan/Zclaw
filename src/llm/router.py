"""
LLM 路由器

管理多个 LLM 提供者，支持默认选择、手动切换和自动回退。
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator

from src.config.settings import LLMConfig
from src.llm.base import BaseProvider
from src.llm.models import (
    LLMError,
    Message,
    Response,
    StreamEvent,
    ToolDefinition,
)
from src.llm.openai_compat import OpenAICompatProvider

logger = logging.getLogger(__name__)


def create_provider(name: str, config_dict: dict[str, Any]) -> BaseProvider:
    """工厂函数：根据配置创建提供者实例。"""
    return OpenAICompatProvider(name=name, **config_dict)


class LLMRouter:
    """
    LLM 路由器。

    管理多个 Provider 实例，提供统一的调用接口。
    """

    def __init__(self, config: LLMConfig):
        self._config = config
        self._providers: dict[str, BaseProvider] = {}

        # 初始化所有提供者
        for name, pc in config.providers.items():
            try:
                self._providers[name] = create_provider(name, pc.model_dump())
                logger.info(f"Provider '{name}' initialized: {pc.model}")
            except Exception as e:
                logger.error(f"提供者 '{name}' 初始化失败: {e}")

    @property
    def default_provider(self) -> BaseProvider:
        name = self._config.default_provider
        if name not in self._providers:
            raise LLMError(f"默认提供者 '{name}' 不可用")
        return self._providers[name]

    @property
    def available_providers(self) -> list[str]:
        return list(self._providers.keys())

    def get_provider(self, name: str) -> BaseProvider:
        if name not in self._providers:
            raise LLMError(f"未找到提供者 '{name}'。可用: {list(self._providers.keys())}")
        return self._providers[name]

    def _get_fallback_chain(self, primary: str) -> list[BaseProvider]:
        """获取回退链。"""
        chain = []
        if primary in self._providers:
            chain.append(self._providers[primary])
        for fb in self._config.fallback_providers:
            if fb in self._providers and self._providers[fb] not in chain:
                chain.append(self._providers[fb])
        return chain

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Response:
        """发送聊天请求，支持自动回退。"""
        temp = temperature if temperature is not None else self._config.temperature
        tokens = max_tokens if max_tokens is not None else self._config.max_tokens

        chain = self._get_fallback_chain(self._config.default_provider)
        last_error: Exception | None = None

        for provider in chain:
            try:
                return await provider.chat(
                    messages=messages,
                    tools=tools,
                    temperature=temp,
                    max_tokens=tokens,
                )
            except LLMError as e:
                last_error = e
                if not e.recoverable:
                    raise
                logger.warning(f"提供者 '{provider.name}' 失败 ({e})，尝试回退...")
            except Exception as e:
                last_error = e
                logger.warning(f"提供者 '{provider.name}' 出现意外错误: {e}")

        raise LLMError(
            f"所有提供者均失败。最后错误: {last_error}",
            provider=self._config.default_provider,
        )

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """发送流式聊天请求。"""
        temp = temperature if temperature is not None else self._config.temperature
        tokens = max_tokens if max_tokens is not None else self._config.max_tokens

        chain = self._get_fallback_chain(self._config.default_provider)
        last_error: Exception | None = None

        for provider in chain:
            try:
                async for event in provider.chat_stream(
                    messages=messages,
                    tools=tools,
                    temperature=temp,
                    max_tokens=tokens,
                ):
                    yield event
                return
            except LLMError as e:
                last_error = e
                if not e.recoverable:
                    raise
                logger.warning(f"提供者 '{provider.name}' 失败 ({e})，尝试回退...")
            except Exception as e:
                last_error = e
                logger.warning(f"提供者 '{provider.name}' 出现意外错误: {e}")

        raise LLMError(
            f"所有提供者均失败。最后错误: {last_error}",
            provider=self._config.default_provider,
        )

    def __repr__(self) -> str:
        return f"LLMRouter(default={self._config.default_provider}, providers={list(self._providers.keys())})"
