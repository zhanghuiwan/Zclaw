"""
任务规划器

分析用户输入，对复杂任务生成执行计划。
"""
from __future__ import annotations

import json
import logging
from typing import Any

from src.core.plan import Plan, PlanStep

logger = logging.getLogger(__name__)

PLAN_REQUEST_PROMPT = """分析以下用户请求并创建一个执行计划。

用户请求: {user_input}

可用工具: {tool_names}

请将计划创建为 JSON 数组格式的步骤列表，每个步骤应是一个清晰、可执行的操作。
只输出 JSON 数组，不要输出其他文字。示例:
[{{"description": "读取文件以了解其结构"}}, {{"description": "识别问题所在"}}]

计划:"""

PLAN_PARSE_PROMPT = """以下文本包含一个 JSON 格式的计划。请提取并只返回 JSON 数组。
文本: {text}

JSON:"""


class Planner:
    """
    任务规划器。

    对复杂任务生成执行计划，跟踪计划执行状态。
    """

    def __init__(self):
        self._current_plan: Plan | None = None

    @property
    def plan(self) -> Plan | None:
        return self._current_plan

    @property
    def has_plan(self) -> bool:
        return self._current_plan is not None

    def create_plan_from_steps(self, goal: str, steps: list[dict[str, str]]) -> Plan:
        """从步骤列表创建计划。"""
        plan = Plan(goal=goal)
        for i, step_data in enumerate(steps):
            plan.steps.append(PlanStep(
                index=i,
                description=step_data.get("description", f"Step {i+1}"),
            ))
        self._current_plan = plan
        logger.info(f"Created plan with {len(plan.steps)} steps: {goal[:50]}")
        return plan

    def parse_plan_from_text(self, goal: str, text: str) -> Plan | None:
        """从 LLM 响应文本中解析计划。"""
        try:
            # 尝试提取 JSON 数组
            text = text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                text = "\n".join(lines[1:-1])  # 移除代码围栏
            text = text.strip()
            if text.startswith("[") and text.endswith("]"):
                steps_data = json.loads(text)
                return self.create_plan_from_steps(goal, steps_data)
        except (json.JSONDecodeError, TypeError, IndexError) as e:
            logger.warning(f"Failed to parse plan: {e}")
        return None

    def create_empty_plan(self, goal: str) -> Plan:
        plan = Plan(goal=goal)
        self._current_plan = plan
        return plan

    def advance(self) -> PlanStep | None:
        """标记当前步骤完成，激活下一步。"""
        if not self._current_plan:
            return None
        return self._current_plan.advance()

    def fail_current(self, error: str) -> None:
        """标记当前步骤失败。"""
        if self._current_plan:
            self._current_plan.fail_current(error)

    def clear_plan(self) -> None:
        self._current_plan = None

    def get_context(self) -> str:
        """获取当前计划的状态，用于注入上下文。"""
        if not self._current_plan:
            return ""
        return f"\n\n{self._current_plan.format_status()}"

    def get_plan_request_prompt(self, user_input: str, tool_names: list[str]) -> str:
        """获取用于请求 LLM 生成计划的 prompt。"""
        return PLAN_REQUEST_PROMPT.format(
            user_input=user_input,
            tool_names=", ".join(tool_names),
        )

    def get_plan_parse_prompt(self, text: str) -> str:
        return PLAN_PARSE_PROMPT.format(text=text)

    def __repr__(self) -> str:
        return f"Planner(has_plan={self.has_plan}, plan={self._current_plan})"
