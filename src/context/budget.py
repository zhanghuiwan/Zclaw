"""
Token 预算计算器
"""
from __future__ import annotations
from src.llm.models import Message


class TokenBudget:
    """Token 预算计算器"""

    def __init__(self, max_context_tokens: int = 32768, safety_margin_ratio: float = 0.1):
        self._max = max_context_tokens
        self._margin = safety_margin_ratio

    @property
    def total(self) -> int:
        return self._max

    @property
    def available(self) -> int:
        return int(self._max * (1 - self._margin))

    def estimate_tokens(self, messages: list[Message]) -> int:
        """估算消息列表的 token 数（1 token ≈ 4 chars）。"""
        total = 0
        for msg in messages:
            if msg.content:
                total += len(msg.content)
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    total += len(tc.name) + len(str(tc.arguments))
        return total // 4 + len(messages) * 4

    def usage_ratio(self, messages: list[Message]) -> float:
        """返回当前使用的 token 占比 (0.0 ~ 1.0)。"""
        used = self.estimate_tokens(messages)
        return used / self._max if self._max > 0 else 1.0

    def remaining(self, messages: list[Message]) -> int:
        """返回剩余可用 token 数。"""
        return max(0, self.available - self.estimate_tokens(messages))
