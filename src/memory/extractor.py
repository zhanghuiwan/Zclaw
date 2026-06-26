"""
记忆自动提取器

从对话内容中自动提取值得长期记住的信息。
支持多种提取后端（LLM / Mock），通过工厂函数创建。
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from src.llm.models import Message, MessageRole

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# 提取结果数据模型
# ──────────────────────────────────────────────

@dataclass
class ExtractedMemory:
    """从对话中提取出的单条记忆"""
    type: str = "fact"          # fact / episode / preference / skill
    content: str = ""
    tags: list[str] = field(default_factory=list)
    importance: float = 0.5     # 0.0 ~ 1.0


# ──────────────────────────────────────────────
# 提取器抽象基类
# ──────────────────────────────────────────────

class BaseExtractor(ABC):
    """记忆提取器抽象基类"""

    @abstractmethod
    async def extract(self, messages: list[Message]) -> list[ExtractedMemory]:
        """
        从对话消息中提取记忆。

        Args:
            messages: 最近的对话消息列表（含 user 和 assistant）

        Returns:
            提取出的记忆列表，空列表表示没有需要记住的内容
        """
        ...


# ──────────────────────────────────────────────
# Mock 提取器（测试用）
# ──────────────────────────────────────────────

class MockExtractor(BaseExtractor):
    """
    Mock 提取器，用于测试和演示。

    使用简单的规则匹配提取记忆，无需 LLM 调用。
    也可接受外部注入的固定结果列表。
    """

    def __init__(self, fixed_results: list[ExtractedMemory] | None = None):
        self._fixed_results = fixed_results

    async def extract(self, messages: list[Message]) -> list[ExtractedMemory]:
        # 如果注入了固定结果，直接返回
        if self._fixed_results is not None:
            return self._fixed_results

        # 简单规则匹配（仅用于演示）
        results = []
        for msg in messages:
            text = msg.content or ""
            if msg.role == MessageRole.USER:
                # 检测偏好表达
                if re.search(r"我喜欢|我偏好|我习惯|prefer|i like", text.lower()):
                    results.append(ExtractedMemory(
                        type="preference",
                        content=text[:200],
                        tags=["auto_extracted"],
                        importance=0.7,
                    ))
                # 检测事实陈述
                elif re.search(r"项目使用|使用的是|版本是|is built with", text.lower()):
                    results.append(ExtractedMemory(
                        type="fact",
                        content=text[:200],
                        tags=["auto_extracted"],
                        importance=0.6,
                    ))

        return results


# ──────────────────────────────────────────────
# LLM 提取器（生产用）
# ──────────────────────────────────────────────

EXTRACTION_PROMPT = """你是一个记忆提取助手。分析以下对话，提取值得长期记住的信息。

要求：
1. 只提取确实值得长期记住的信息（用户偏好、项目事实、重要事件、学到的技能）
2. 忽略临时性/一次性内容（如"帮我写个函数"、"bug 在哪"）
3. 每条记忆要简洁（50 字以内）

请返回 JSON 数组，每项格式：
{{"type": "fact|episode|preference|skill", "content": "记忆内容", "tags": ["标签1"], "importance": 0.7}}

如果对话中没有值得记住的内容，返回空数组 []

对话内容：
{conversation}"""


class LLMExtractor(BaseExtractor):
    """
    基于 LLM 的记忆提取器。

    使用一个独立的 LLM 调用来分析对话并提取记忆。
    支持使用不同于主模型的低成本模型。
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "qwen-turbo",
        temperature: float = 0.1,
    ):
        self._base_url = base_url
        self._api_key = api_key
        self._model = model
        self._temperature = temperature

    async def extract(self, messages: list[Message]) -> list[ExtractedMemory]:
        # 过滤出用户和助手的对话内容
        conversation_lines = []
        for msg in messages:
            if msg.role == MessageRole.USER:
                conversation_lines.append(f"用户: {(msg.content or '')[:500]}")
            elif msg.role == MessageRole.ASSISTANT and msg.content:
                conversation_lines.append(f"助手: {msg.content[:500]}")

        if not conversation_lines:
            return []

        conversation_text = "\n".join(conversation_lines[-20:])  # 最近 20 条

        prompt = EXTRACTION_PROMPT.format(conversation=conversation_text)

        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(base_url=self._base_url, api_key=self._api_key)

            response = await client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self._temperature,
                max_tokens=1024,
            )

            content = response.choices[0].message.content or ""
            return self._parse_response(content)
        except Exception as e:
            logger.error(f"记忆提取失败: {e}")
            return []

    def _parse_response(self, text: str) -> list[ExtractedMemory]:
        """解析 LLM 返回的 JSON 数组。"""
        # 尝试提取 JSON（可能被 ```json 包裹）
        json_match = re.search(r'\[.*\]', text, re.DOTALL)
        if not json_match:
            return []

        try:
            items = json.loads(json_match.group())
        except json.JSONDecodeError:
            logger.debug("记忆提取返回了无效的 JSON: %s", text[:200])
            return []

        results = []
        valid_types = {"fact", "episode", "preference", "skill"}
        for item in items:
            if not isinstance(item, dict):
                continue
            mem_type = item.get("type", "fact")
            if mem_type not in valid_types:
                mem_type = "fact"
            content = item.get("content", "").strip()
            if not content:
                continue
            results.append(ExtractedMemory(
                type=mem_type,
                content=content[:500],  # 限制长度
                tags=item.get("tags", [])[:5],
                importance=max(0.0, min(1.0, float(item.get("importance", 0.5)))),
            ))

        return results


# ──────────────────────────────────────────────
# 工厂函数
# ──────────────────────────────────────────────

def create_extractor(settings=None) -> BaseExtractor | None:
    """
    创建记忆提取器。

    优先使用 LLM 提取器（如果配置了 API），否则返回 None。
    """
    if settings is not None:
        try:
            provider = settings.llm.default_provider
            pc = settings.llm.providers[provider]
            if pc.api_key:
                return LLMExtractor(
                    base_url=pc.base_url,
                    api_key=pc.api_key,
                    model=pc.model,
                )
        except Exception:
            pass

    logger.warning("未配置 LLM API，无法使用记忆提取功能")
    return None
