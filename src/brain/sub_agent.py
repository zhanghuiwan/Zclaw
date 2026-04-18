"""
Sub-Agent Manager - 子代理管理器

管理临时子代理的生命周期，用于并行处理复杂任务的子任务。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SubAgentStatus(Enum):
    """子代理状态"""
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    IDLE = "idle"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SubAgentConfig:
    """子代理配置"""
    parent_id: str                      # 父代理 ID
    task: str                           # 任务描述
    inherited_context: dict[str, Any]   # 继承的上下文
    max_rounds: int = 50              # 最大对话轮次
    max_time_seconds: float = 300      # 最大运行时间（秒）
    max_token_budget: int = 100000    # 最大 token 预算
    tools: list[str] | None = None     # 可用工具（None 表示继承父代理）
    model: str = ""                    # 使用的模型（空表示继承）


@dataclass
class SubAgent:
    """子代理实例"""
    sub_agent_id: str
    config: SubAgentConfig
    status: SubAgentStatus = SubAgentStatus.CREATED
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: Any = None
    error: str | None = None
    rounds: int = 0
    token_usage: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "sub_agent_id": self.sub_agent_id,
            "parent_id": self.config.parent_id,
            "task": self.config.task,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "result": str(self.result)[:500] if self.result else None,
            "error": self.error,
            "rounds": self.rounds,
            "token_usage": self.token_usage,
        }


class SubAgentManager:
    """
    子代理管理器

    负责：
    - 创建子代理
    - 管理子代理生命周期
    - 收集子代理结果
    - 清理已完成的子代理
    """

    def __init__(self):
        self._sub_agents: dict[str, SubAgent] = {}
        self._parent_to_children: dict[str, set[str]] = {}  # parent_id -> set of sub_agent_id

    def _generate_sub_agent_id(self) -> str:
        """生成子代理 ID"""
        return f"sub_{uuid.uuid4().hex[:12]}"

    async def create(
        self,
        parent_id: str,
        task: str,
        inherited_context: dict[str, Any] | None = None,
        **kwargs,
    ) -> SubAgent:
        """
        创建子代理。

        Args:
            parent_id: 父代理 ID
            task: 任务描述
            inherited_context: 继承的上下文
            **kwargs: 额外的配置参数

        Returns:
            SubAgent: 创建的子代理
        """
        sub_agent_id = self._generate_sub_agent_id()

        config = SubAgentConfig(
            parent_id=parent_id,
            task=task,
            inherited_context=inherited_context or {},
            max_rounds=kwargs.get("max_rounds", 50),
            max_time_seconds=kwargs.get("max_time_seconds", 300),
            max_token_budget=kwargs.get("max_token_budget", 100000),
            tools=kwargs.get("tools"),
            model=kwargs.get("model", ""),
        )

        sub_agent = SubAgent(
            sub_agent_id=sub_agent_id,
            config=config,
            status=SubAgentStatus.CREATED,
        )

        self._sub_agents[sub_agent_id] = sub_agent

        if parent_id not in self._parent_to_children:
            self._parent_to_children[parent_id] = set()
        self._parent_to_children[parent_id].add(sub_agent_id)

        logger.info(f"子代理已创建: {sub_agent_id} (parent={parent_id}, task={task[:50]})")
        return sub_agent

    async def start(self, sub_agent_id: str) -> bool:
        """
        启动子代理。

        Args:
            sub_agent_id: 子代理 ID

        Returns:
            bool: 是否成功
        """
        sub_agent = self._sub_agents.get(sub_agent_id)
        if not sub_agent:
            logger.error(f"子代理不存在: {sub_agent_id}")
            return False

        sub_agent.status = SubAgentStatus.RUNNING
        sub_agent.started_at = datetime.now()

        logger.info(f"子代理已启动: {sub_agent_id}")
        return True

    async def complete(self, sub_agent_id: str, result: Any) -> bool:
        """
        标记子代理为完成。

        Args:
            sub_agent_id: 子代理 ID
            result: 执行结果

        Returns:
            bool: 是否成功
        """
        sub_agent = self._sub_agents.get(sub_agent_id)
        if not sub_agent:
            return False

        sub_agent.status = SubAgentStatus.DONE
        sub_agent.result = result
        sub_agent.finished_at = datetime.now()

        logger.info(f"子代理已完成: {sub_agent_id}")
        return True

    async def fail(self, sub_agent_id: str, error: str) -> bool:
        """
        标记子代理为失败。

        Args:
            sub_agent_id: 子代理 ID
            error: 错误信息

        Returns:
            bool: 是否成功
        """
        sub_agent = self._sub_agents.get(sub_agent_id)
        if not sub_agent:
            return False

        sub_agent.status = SubAgentStatus.FAILED
        sub_agent.error = error
        sub_agent.finished_at = datetime.now()

        logger.error(f"子代理失败: {sub_agent_id} - {error}")
        return True

    async def cancel(self, sub_agent_id: str) -> bool:
        """
        取消子代理。

        Args:
            sub_agent_id: 子代理 ID

        Returns:
            bool: 是否成功
        """
        sub_agent = self._sub_agents.get(sub_agent_id)
        if not sub_agent:
            return False

        sub_agent.status = SubAgentStatus.CANCELLED
        sub_agent.finished_at = datetime.now()

        logger.info(f"子代理已取消: {sub_agent_id}")
        return True

    async def destroy(self, sub_agent_id: str) -> bool:
        """
        销毁子代理（清理资源）。

        Args:
            sub_agent_id: 子代理 ID

        Returns:
            bool: 是否成功
        """
        sub_agent = self._sub_agents.get(sub_agent_id)
        if not sub_agent:
            return False

        # 从父代理的子代理列表中移除
        parent_id = sub_agent.config.parent_id
        if parent_id in self._parent_to_children:
            self._parent_to_children[parent_id].discard(sub_agent_id)

        # 移除子代理
        del self._sub_agents[sub_agent_id]

        logger.info(f"子代理已销毁: {sub_agent_id}")
        return True

    def get(self, sub_agent_id: str) -> SubAgent | None:
        """获取子代理"""
        return self._sub_agents.get(sub_agent_id)

    def get_by_parent(self, parent_id: str) -> list[SubAgent]:
        """获取父代理的所有子代理"""
        sub_agent_ids = self._parent_to_children.get(parent_id, set())
        return [
            sub_agent
            for sub_agent_id in sub_agent_ids
            if (sub_agent := self._sub_agents.get(sub_agent_id))
        ]

    def get_active(self) -> list[SubAgent]:
        """获取所有活跃的子代理"""
        return [
            sub_agent
            for sub_agent in self._sub_agents.values()
            if sub_agent.status in (SubAgentStatus.RUNNING, SubAgentStatus.IDLE)
        ]

    def get_status(self, sub_agent_id: str) -> SubAgentStatus | None:
        """获取子代理状态"""
        sub_agent = self._sub_agents.get(sub_agent_id)
        return sub_agent.status if sub_agent else None

    def is_alive(self, sub_agent_id: str) -> bool:
        """检查子代理是否存活"""
        sub_agent = self._sub_agents.get(sub_agent_id)
        if not sub_agent:
            return False
        return sub_agent.status in (SubAgentStatus.RUNNING, SubAgentStatus.IDLE)

    def cleanup_completed(self, parent_id: str | None = None) -> int:
        """
        清理已完成的子代理。

        Args:
            parent_id: 父代理 ID（None 表示清理所有）

        Returns:
            int: 清理的数量
        """
        to_cleanup = []

        for sub_agent_id, sub_agent in self._sub_agents.items():
            if sub_agent.status in (
                SubAgentStatus.DONE,
                SubAgentStatus.FAILED,
                SubAgentStatus.CANCELLED,
            ):
                if parent_id is None or sub_agent.config.parent_id == parent_id:
                    to_cleanup.append(sub_agent_id)

        for sub_agent_id in to_cleanup:
            self._sub_agents.pop(sub_agent_id, None)
            parent_id_inner = None
            for p_id, children in self._parent_to_children.items():
                if sub_agent_id in children:
                    parent_id_inner = p_id
                    break
            if parent_id_inner:
                self._parent_to_children[parent_id_inner].discard(sub_agent_id)

        if to_cleanup:
            logger.info(f"清理了 {len(to_cleanup)} 个已完成的子代理")

        return len(to_cleanup)

    def get_status_summary(self) -> dict[str, Any]:
        """获取子代理状态摘要"""
        status_counts: dict[str, int] = {}
        for sub_agent in self._sub_agents.values():
            status_key = sub_agent.status.value
            status_counts[status_key] = status_counts.get(status_key, 0) + 1

        return {
            "total": len(self._sub_agents),
            "active": len(self.get_active()),
            "by_status": status_counts,
            "parent_count": len(self._parent_to_children),
        }
