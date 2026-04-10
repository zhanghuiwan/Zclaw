"""
Token 用量追踪
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class CostTracker:
    """Token 用量和费用追踪"""

    def __init__(self):
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_rounds: int = 0
        self._round_costs: list[dict] = []

    def record_round(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_rounds += 1
        self._round_costs.append({
            "round": self.total_rounds,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        })

    def get_total(self) -> int:
        return self.total_prompt_tokens + self.total_completion_tokens

    def get_average_per_round(self) -> float:
        if self.total_rounds == 0:
            return 0.0
        return self.get_total() / self.total_rounds

    def estimate_cost(self, price_per_million_input: float = 0.0, price_per_million_output: float = 0.0) -> float:
        """估算费用。"""
        input_cost = (self.total_prompt_tokens / 1_000_000) * price_per_million_input
        output_cost = (self.total_completion_tokens / 1_000_000) * price_per_million_output
        return input_cost + output_cost

    def get_summary(self) -> str:
        total = self.get_total()
        avg = self.get_average_per_round()
        return (
            f"总 Token 数: {total:,} "
            f"(输入: {self.total_prompt_tokens:,}, 输出: {self.total_completion_tokens:,})\n"
            f"轮次: {self.total_rounds}\n"
            f"平均每轮: {avg:,.0f} tokens"
        )

    def __repr__(self) -> str:
        return f"CostTracker(rounds={self.total_rounds}, total_tokens={self.get_total():,})"
