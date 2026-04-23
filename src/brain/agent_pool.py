"""
AgentPool - Agent 实例池

管理 Agent 实例的生命周期，实现：
1. 按 agent_id 获取或创建 Agent 实例
2. 跟踪 Agent 实例状态（活跃/空闲/休眠）
3. 自动休眠空闲 Agent
4. 限制最大实例数（防止内存溢出）
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from pathlib import Path
from typing import Any

from src.config.settings import Settings
from src.brain.soul_loader import SoulLoader, Soul
from src.brain.user_profile import UserProfileLoader, UserProfile
from src.brain.agents_config import AgentsConfigLoader, AgentBehaviorConfig

logger = logging.getLogger(__name__)


class AgentInstanceState(Enum):
    """Agent 实例状态"""
    CREATING = "creating"   # 创建中
    ACTIVE = "active"       # 活跃（正在处理请求）
    IDLE = "idle"           # 空闲（等待请求）
    DORMANT = "dormant"     # 休眠（释放了内存）
    DISPOSED = "disposed"   # 已销毁


class AgentInstance:
    """
    Agent 实例包装器

    包含 Agent 实例及其元数据（状态、创建时间、最后活跃时间等）。
    """

    def __init__(self, agent_id: str, agent: Any):
        self.agent_id = agent_id
        self.agent = agent
        self.state = AgentInstanceState.CREATING
        self.created_at = time.time()
        self.last_active_at = time.time()
        self.request_count = 0  # 处理的请求数

    def mark_active(self) -> None:
        """标记为活跃"""
        self.state = AgentInstanceState.ACTIVE
        self.last_active_at = time.time()

    def mark_idle(self) -> None:
        """标记为空闲"""
        self.state = AgentInstanceState.IDLE
        self.last_active_at = time.time()

    def mark_dormant(self) -> None:
        """标记为休眠"""
        self.state = AgentInstanceState.DORMANT
        # 释放 Agent 的对话历史（保留记忆）
        try:
            self.agent.clear_history()
        except Exception as e:
            logger.warning(f"Agent {self.agent_id} 清理历史失败: {e}")

    def mark_disposed(self) -> None:
        """标记为已销毁"""
        self.state = AgentInstanceState.DISPOSED

    def is_idle_too_long(self, max_idle_seconds: int) -> bool:
        """检查空闲时间是否超过阈值"""
        if self.state != AgentInstanceState.IDLE:
            return False
        elapsed = time.time() - self.last_active_at
        return elapsed > max_idle_seconds

    def __repr__(self) -> str:
        return (
            f"AgentInstance(id={self.agent_id}, state={self.state.value}, "
            f"requests={self.request_count}, "
            f"idle_for={time.time() - self.last_active_at:.0f}s)"
        )


class AgentPool:
    """
    Agent 实例池

    职责：
    1. 按 agent_id 获取或创建 Agent 实例
    2. 跟踪 Agent 实例状态
    3. 自动休眠空闲 Agent
    4. 限制最大实例数
    """

    def __init__(
        self,
        agents_dir: str | Path = "agents",
        max_idle_seconds: int = 1800,  # 30分钟空闲休眠
        max_instances: int = 10,
    ):
        self._agents_dir = Path(agents_dir)
        self._max_idle = max_idle_seconds
        self._max_instances = max_instances

        # Agent 实例管理
        self._instances: dict[str, AgentInstance] = {}  # agent_id → AgentInstance
        self._locks: dict[str, asyncio.Lock] = {}  # agent_id → 锁

        # 加载器（从 AgentFactory 迁移）
        self._soul_loader = SoulLoader()
        self._user_loader = UserProfileLoader()
        self._agents_loader = AgentsConfigLoader()

        # 配置缓存
        self._soul_cache: dict[str, Soul] = {}
        self._user_cache: dict[str, UserProfile] = {}
        self._behavior_cache: dict[str, AgentBehaviorConfig] = {}

        logger.info(
            f"AgentPool 初始化: agents_dir={self._agents_dir}, "
            f"max_idle={self._max_idle}s, max_instances={self._max_instances}"
        )

    @property
    def agents_dir(self) -> Path:
        return self._agents_dir

    @property
    def max_instances(self) -> int:
        return self._max_instances

    @property
    def instance_count(self) -> int:
        """当前实例数量（不包括已销毁的）"""
        return sum(
            1 for inst in self._instances.values()
            if inst.state != AgentInstanceState.DISPOSED
        )

    @property
    def active_count(self) -> int:
        """活跃实例数量"""
        return sum(
            1 for inst in self._instances.values()
            if inst.state == AgentInstanceState.ACTIVE
        )

    def list_agents(self) -> list[str]:
        """列出所有已加载的 Agent ID"""
        return [
            agent_id for agent_id, inst in self._instances.items()
            if inst.state != AgentInstanceState.DISPOSED
        ]

    def get_instance_info(self, agent_id: str) -> dict[str, Any] | None:
        """获取 Agent 实例信息"""
        inst = self._instances.get(agent_id)
        if inst is None or inst.state == AgentInstanceState.DISPOSED:
            return None

        return {
            "agent_id": inst.agent_id,
            "state": inst.state.value,
            "created_at": inst.created_at,
            "last_active_at": inst.last_active_at,
            "request_count": inst.request_count,
            "idle_seconds": time.time() - inst.last_active_at,
        }

    # ==================== 配置加载 ====================

    def _ensure_config_loaded(self, agent_id: str) -> None:
        """确保配置已加载"""
        if agent_id in self._soul_cache:
            return

        agent_dir = self._agents_dir / agent_id
        if not agent_dir.exists():
            logger.warning(f"Agent 目录不存在: {agent_dir}")

        # 加载 SOUL
        soul_file = agent_dir / "SOUL.md"
        soul = self._soul_loader.load(soul_file) if soul_file.exists() else Soul()
        self._soul_cache[agent_id] = soul

        # 加载 USER
        user_file = agent_dir / "USER.md"
        user = self._user_loader.load(user_file) if user_file.exists() else UserProfile()
        self._user_cache[agent_id] = user

        # 加载 AGENTS 配置
        agents_file = agent_dir / "AGENTS.md"
        behavior = self._agents_loader.load(agents_file) if agents_file.exists() else AgentBehaviorConfig()
        self._behavior_cache[agent_id] = behavior

    def get_soul(self, agent_id: str) -> Soul | None:
        """获取 Agent 的 Soul"""
        self._ensure_config_loaded(agent_id)
        return self._soul_cache.get(agent_id)

    def get_user_profile(self, agent_id: str) -> UserProfile | None:
        """获取 Agent 的 UserProfile"""
        self._ensure_config_loaded(agent_id)
        return self._user_cache.get(agent_id)

    def get_behavior_config(self, agent_id: str) -> AgentBehaviorConfig | None:
        """获取 Agent 的行为配置"""
        self._ensure_config_loaded(agent_id)
        return self._behavior_cache.get(agent_id)

    # ==================== Agent 创建 ====================

    def _get_lock(self, agent_id: str) -> asyncio.Lock:
        """获取 Agent 的锁"""
        if agent_id not in self._locks:
            self._locks[agent_id] = asyncio.Lock()
        return self._locks[agent_id]

    async def _create_agent_instance(self, agent_id: str) -> Any:
        """
        创建 Agent 实例。

        此方法在锁内执行，确保并发安全。
        """
        from src.core.agent import Agent
        from src.config.settings import load_settings

        # 从 .env 文件加载配置
        settings = load_settings(use_env=True)

        # 更新 memory 路径
        settings.memory.storage_path = f".Zclaw/agents/{agent_id}/memory"

        # 创建 Agent
        agent = Agent(settings=settings, session_id=agent_id)

        # 注册额外工具
        await self._register_extra_tools(agent, agent_id)

        # P9: 初始化 MCP 连接
        if settings.mcp.enabled:
            mcp_count = await agent.init_mcp()
            if mcp_count > 0:
                logger.info(f"已初始化 {mcp_count} 个 MCP 工具到 Agent {agent_id}")

        # 设置系统提示词（使用 Soul）
        soul = self.get_soul(agent_id)
        if soul:
            system_prompt = self._soul_loader.to_system_prompt(soul)
            existing_prompt = agent.loop.messages[0].content if agent.loop.messages else ""
            new_prompt = f"{system_prompt}\n\n{existing_prompt}"
            agent.set_system_prompt(new_prompt)

        logger.info(f"Agent 实例已创建: {agent_id}")
        return agent

    async def _register_extra_tools(self, agent: Any, agent_id: str) -> None:
        """注册额外工具（BrowserTool, ProcessTool）"""
        try:
            from src.tools.builtin.browser_tool import BrowserTool
            from src.tools.builtin.process_tool import ProcessTool

            browser_tool = BrowserTool(headless=True)
            agent.tools.register(browser_tool)
            logger.info(f"已注册 BrowserTool 到 Agent {agent_id}")

            process_tool = ProcessTool()
            agent.tools.register(process_tool)
            logger.info(f"已注册 ProcessTool 到 Agent {agent_id}")

        except ImportError as e:
            logger.warning(f"无法注册额外工具: {e}")

    # ==================== Agent 获取/释放 ====================

    async def acquire_agent(self, agent_id: str) -> Any:
        """
        获取 Agent 实例（获取锁）。

        必须与 release_agent 配对使用：
        ```
        agent = await pool.acquire_agent("default")
        try:
            # 使用 agent
        finally:
            await pool.release_agent("default")
        ```

        Args:
            agent_id: Agent ID

        Returns:
            Agent 实例
        """
        # 加载配置
        self._ensure_config_loaded(agent_id)

        # 获取锁（等待直到获取）
        lock = self._get_lock(agent_id)
        await lock.acquire()

        # 检查是否已存在实例
        if agent_id in self._instances:
            inst = self._instances[agent_id]

            # 如果实例忙碌，等待它变成空闲
            wait_count = 0
            while inst.state == AgentInstanceState.ACTIVE:
                lock.release()
                await asyncio.sleep(0.5)
                wait_count += 1
                if wait_count > 120:
                    lock.release()
                    raise RuntimeError(f"Agent {agent_id} 忙碌超时，请稍后再试")
                await lock.acquire()
                inst = self._instances.get(agent_id)
                if not inst:
                    break

            # 如果是休眠状态，需要唤醒（目前是重建）
            if inst and inst.state == AgentInstanceState.DORMANT:
                logger.info(f"Agent {agent_id} 从休眠状态唤醒")
                inst.agent = await self._create_agent_instance(agent_id)

            if inst:
                # 重置 AgentLoop 状态为 IDLE
                # 如果状态不是 IDLE，说明上次可能没有正常结束，需要重置
                from src.core.state import AgentState
                current_state = inst.agent.loop.state
                if current_state != AgentState.IDLE:
                    logger.warning(f"AgentLoop 状态异常 ({current_state.value})，强制重置为 IDLE")
                    inst.agent.loop.clear_history()
                    inst.agent.loop._state._state = AgentState.IDLE

                # 标记为活跃
                inst.mark_active()
                inst.request_count += 1
                return inst.agent

        # 检查实例数量限制
        if self.instance_count >= self._max_instances:
            # 尝试清理空闲实例
            cleaned = await self.cleanup_idle()
            if self.instance_count >= self._max_instances:
                lock.release()
                raise RuntimeError(
                    f"Agent 实例数已达到上限 ({self._max_instances})，"
                    f"无法创建新实例"
                )

        # 创建新实例
        logger.info(f"创建新 Agent 实例: {agent_id}")
        agent = await self._create_agent_instance(agent_id)

        # 包装并存储
        inst = AgentInstance(agent_id, agent)
        inst.mark_active()
        inst.request_count = 1
        self._instances[agent_id] = inst

        return agent

    # 保持向后兼容的 get_agent
    async def get_agent(self, agent_id: str) -> Any:
        """获取 Agent 实例（向后兼容，内部自动释放锁）。"""
        return await self.acquire_agent(agent_id)

    async def release_agent(self, agent_id: str) -> None:
        """
        释放 Agent（标记为空闲并释放锁）。

        Args:
            agent_id: Agent ID
        """
        inst = self._instances.get(agent_id)
        if inst is None or inst.state == AgentInstanceState.DISPOSED:
            return

        inst.mark_idle()
        logger.debug(f"Agent {agent_id} 已标记为空闲")

        # 释放锁
        lock = self._locks.get(agent_id)
        if lock and lock.locked():
            lock.release()
            logger.debug(f"Agent {agent_id} 锁已释放")

    async def hibernate_agent(self, agent_id: str) -> None:
        """
        休眠 Agent（释放内存但保留实例）。

        Args:
            agent_id: Agent ID
        """
        inst = self._instances.get(agent_id)
        if inst is None or inst.state == AgentInstanceState.DISPOSED:
            return

        inst.mark_dormant()
        logger.info(f"Agent {agent_id} 已进入休眠状态")

    async def dispose_agent(self, agent_id: str) -> None:
        """
        销毁 Agent 实例。

        Args:
            agent_id: Agent ID
        """
        inst = self._instances.get(agent_id)
        if inst is None:
            return

        inst.mark_disposed()

        # 清理 MCP 连接
        try:
            await inst.agent.shutdown_mcp()
        except Exception as e:
            logger.warning(f"Agent {agent_id} 关闭 MCP 失败: {e}")

        # 从实例字典中移除
        del self._instances[agent_id]
        logger.info(f"Agent {agent_id} 已销毁")

        # 释放锁（如果锁还被持有）
        lock = self._locks.get(agent_id)
        if lock and lock.locked():
            lock.release()
            logger.debug(f"Agent {agent_id} 锁已释放")

    # ==================== 清理任务 ====================

    async def cleanup_idle(self) -> int:
        """
        清理所有空闲时间过长的 Agent。

        Returns:
            清理的 Agent 数量
        """
        cleaned = 0
        for agent_id, inst in list(self._instances.items()):
            if inst.is_idle_too_long(self._max_idle):
                logger.info(
                    f"Agent {agent_id} 空闲时间超过 {self._max_idle}s，"
                    f"进入休眠状态"
                )
                inst.mark_dormant()
                cleaned += 1

        if cleaned > 0:
            logger.info(f"已清理 {cleaned} 个空闲 Agent")

        return cleaned

    async def cleanup_all(self) -> int:
        """
        清理所有 Agent（关闭连接）。

        Returns:
            清理的 Agent 数量
        """
        count = self.instance_count
        for agent_id in list(self._instances.keys()):
            await self.dispose_agent(agent_id)

        logger.info(f"已清理所有 {count} 个 Agent")
        return count

    # ==================== 状态查询 ====================

    def get_status(self) -> dict[str, Any]:
        """获取 AgentPool 状态"""
        instances_info = []
        for agent_id, inst in self._instances.items():
            if inst.state != AgentInstanceState.DISPOSED:
                instances_info.append(self.get_instance_info(agent_id))

        return {
            "agents_dir": str(self._agents_dir),
            "instance_count": self.instance_count,
            "active_count": self.active_count,
            "max_instances": self._max_instances,
            "max_idle_seconds": self._max_idle,
            "instances": instances_info,
        }

    def __repr__(self) -> str:
        return (
            f"AgentPool(instances={self.instance_count}, "
            f"active={self.active_count}, "
            f"max={self._max_instances})"
        )