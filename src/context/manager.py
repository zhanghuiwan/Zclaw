"""
上下文管理器
"""
from __future__ import annotations
import logging
from src.config.settings import ContextConfig
from src.context.budget import TokenBudget
from src.context.compressor import ContextCompressor
from src.llm.models import Message, MessageRole

logger = logging.getLogger(__name__)


class ContextManager:
    """上下文管理器"""

    def __init__(self, config: ContextConfig, max_context_tokens: int = 32768):
        self._config = config
        self._budget = TokenBudget(
            max_context_tokens=max_context_tokens,
            safety_margin_ratio=config.safety_margin_ratio,
        )
        self._compressor = ContextCompressor()
        self._auto_compress_threshold = 0.8  # 80%

    @property
    def budget(self) -> TokenBudget:
        return self._budget

    def should_compress(self, messages: list[Message]) -> bool:
        """检查是否需要压缩。"""
        return self._budget.usage_ratio(messages) >= self._auto_compress_threshold

    def prepare_messages(self, messages: list[Message], force_compress: bool = False) -> list[Message]:
        """准备发送给 LLM 的消息列表（必要时压缩）。"""
        if force_compress or self.should_compress(messages):
            logger.info(f"正在压缩上下文（使用率: {self._budget.usage_ratio(messages):.0%}）")
            return self._compressor.compress(messages)
        return messages

    def get_usage_info(self, messages: list[Message]) -> dict:
        """获取上下文使用信息。"""
        ratio = self._budget.usage_ratio(messages)
        used = self._budget.estimate_tokens(messages)
        return {
            "used_tokens": used,
            "max_tokens": self._budget.total,
            "available_tokens": self._budget.available,
            "usage_ratio": f"{ratio:.1%}",
            "needs_compression": ratio >= self._auto_compress_threshold,
        }
