"""
计划数据结构
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class PlanStepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """计划中的单个步骤"""
    index: int
    description: str
    status: PlanStepStatus = PlanStepStatus.PENDING
    result: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "description": self.description,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PlanStep:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class Plan:
    """执行计划"""
    goal: str = ""
    steps: list[PlanStep] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "active"  # active（活跃）、completed（已完成）、abandoned（已放弃）

    @property
    def current_step_index(self) -> int:
        for i, step in enumerate(self.steps):
            if step.status in (PlanStepStatus.PENDING, PlanStepStatus.IN_PROGRESS):
                return i
        return len(self.steps)

    @property
    def progress(self) -> float:
        if not self.steps:
            return 0.0
        done = sum(1 for s in self.steps if s.status == PlanStepStatus.DONE)
        return done / len(self.steps)

    def advance(self) -> PlanStep | None:
        """将当前步骤标记为完成，返回下一步。"""
        # 查找并完成当前活跃步骤（IN_PROGRESS 或第一个 PENDING）
        for step in self.steps:
            if step.status == PlanStepStatus.IN_PROGRESS:
                step.status = PlanStepStatus.DONE
                return self._activate_next()
        # 没有 IN_PROGRESS 步骤：将第一个 PENDING 标记为 DONE 并激活下一步
        for step in self.steps:
            if step.status == PlanStepStatus.PENDING:
                step.status = PlanStepStatus.DONE
                return self._activate_next()
        return None

    def _activate_next(self) -> PlanStep | None:
        for step in self.steps:
            if step.status == PlanStepStatus.PENDING:
                step.status = PlanStepStatus.IN_PROGRESS
                return step
        return None

    def fail_current(self, error: str) -> None:
        for step in self.steps:
            if step.status == PlanStepStatus.IN_PROGRESS:
                step.status = PlanStepStatus.FAILED
                step.error = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Plan:
        data = dict(data)
        steps_data = data.pop("steps", [])
        data["steps"] = [PlanStep.from_dict(s) for s in steps_data]
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def format_status(self) -> str:
        """格式化计划状态为可读文本。"""
        if not self.steps:
            return "暂无计划。"
        lines = [f"计划: {self.goal}", f"进度: {self.progress:.0%}"]
        for i, step in enumerate(self.steps):
            icon = {"pending": "[ ]", "in_progress": "[>]", "done": "[+]", "failed": "[!]", "skipped": "[-]"}.get(step.status.value, "[?]")
            lines.append(f"  {icon} 第 {i+1} 步: {step.description}")
            if step.error:
                lines.append(f"      错误: {step.error}")
            elif step.result:
                lines.append(f"      结果: {step.result[:80]}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"Plan(goal='{self.goal[:30]}', steps={len(self.steps)}, progress={self.progress:.0%})"
