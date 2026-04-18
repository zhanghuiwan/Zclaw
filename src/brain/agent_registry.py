"""
Agent Registry - Agent 注册表

管理多个 Agent 实例的注册、发现和生命周期。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Agent 配置"""
    id: str                               # Agent ID
    name: str                             # Agent 名称
    soul_file: str = ""                   # SOUL.md 文件路径
    user_file: str = ""                  # USER.md 文件路径
    agents_file: str = ""                # AGENTS.md 文件路径
    routes: list[dict[str, Any]] = field(default_factory=list)  # 路由规则
    tools: list[str] = field(default_factory=list)               # 可用工具
    model: str = ""                       # 使用的模型
    heartbeat_interval: int = 300        # 心跳间隔（秒）


class AgentRegistry:
    """
    Agent 注册表

    管理多个 Agent 实例，支持：
    - Agent 注册和发现
    - 路由规则配置
    - Agent 生命周期管理
    """

    def __init__(self):
        self._agents: dict[str, Any] = {}      # agent_id -> Agent 实例
        self._configs: dict[str, AgentConfig] = {}  # agent_id -> AgentConfig
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def register(self, config: AgentConfig) -> None:
        """
        注册 Agent 配置。

        Args:
            config: AgentConfig 对象
        """
        if config.id in self._configs:
            logger.warning(f"Agent {config.id} 已注册，将被覆盖")

        self._configs[config.id] = config
        logger.info(f"Agent 配置已注册: {config.id} ({config.name})")

    def unregister(self, agent_id: str) -> bool:
        """
        注销 Agent。

        Args:
            agent_id: Agent ID

        Returns:
            bool: 是否成功
        """
        if agent_id in self._configs:
            del self._configs[agent_id]
            logger.info(f"Agent 配置已注销: {agent_id}")
            return True
        return False

    def get_config(self, agent_id: str) -> AgentConfig | None:
        """获取 Agent 配置"""
        return self._configs.get(agent_id)

    def list_agents(self) -> list[AgentConfig]:
        """列出所有注册的 Agent 配置"""
        return list(self._configs.values())

    def set_agent_instance(self, agent_id: str, instance: Any) -> None:
        """
        设置 Agent 实例。

        Args:
            agent_id: Agent ID
            instance: Agent 实例
        """
        if agent_id not in self._configs:
            logger.warning(f"Agent {agent_id} 未注册配置，先注册空配置")
            self.register(AgentConfig(id=agent_id, name=agent_id))

        self._agents[agent_id] = instance
        logger.info(f"Agent 实例已设置: {agent_id}")

    def get_agent(self, agent_id: str) -> Any | None:
        """获取 Agent 实例"""
        return self._agents.get(agent_id)

    def has_agent(self, agent_id: str) -> bool:
        """检查 Agent 是否已注册"""
        return agent_id in self._configs

    def has_agent_instance(self, agent_id: str) -> bool:
        """检查 Agent 实例是否已设置"""
        return agent_id in self._agents

    def remove_agent_instance(self, agent_id: str) -> bool:
        """移除 Agent 实例"""
        if agent_id in self._agents:
            del self._agents[agent_id]
            logger.info(f"Agent 实例已移除: {agent_id}")
            return True
        return False

    def get_all_routes(self) -> list[dict[str, Any]]:
        """获取所有路由规则"""
        routes = []
        for config in self._configs.values():
            for route in config.routes:
                routes.append({
                    "agent_id": config.id,
                    **route,
                })
        return routes

    def find_agent_by_route(
        self, channel: str, sender_id: str = "", channel_id: str = ""
    ) -> str | None:
        """
        根据路由规则查找 Agent。

        Args:
            channel: 渠道
            sender_id: 发送者 ID
            channel_id: 频道 ID

        Returns:
            str | None: Agent ID 或 None
        """
        for config in self._configs.values():
            for route in config.routes:
                # 检查渠道匹配
                if route.get("channel") != channel:
                    continue

                # 检查发送者匹配
                if route.get("sender") and route.get("sender") != sender_id:
                    continue

                # 检查频道匹配
                if route.get("channel_id") and route.get("channel_id") != channel_id:
                    continue

                return config.id

        return None

    def load_from_agents_directory(self, agents_dir: str | Path) -> int:
        """
        从 agents 配置目录加载所有 Agent 配置。

        Args:
            agents_dir: agents 目录路径

        Returns:
            int: 加载的 Agent 数量
        """
        agents_dir = Path(agents_dir)
        if not agents_dir.exists():
            logger.warning(f"agents 目录不存在: {agents_dir}")
            return 0

        count = 0
        for agent_dir in agents_dir.iterdir():
            if not agent_dir.is_dir():
                continue

            config = self._discover_agent_config(agent_dir)
            if config:
                self.register(config)
                count += 1

        logger.info(f"从 {agents_dir} 加载了 {count} 个 Agent 配置")
        return count

    def _discover_agent_config(self, agent_dir: Path) -> AgentConfig | None:
        """发现单个 Agent 的配置"""
        agent_id = agent_dir.name

        soul_file = agent_dir / "SOUL.md"
        user_file = agent_dir / "USER.md"
        agents_file = agent_dir / "AGENTS.md"

        if not soul_file.exists():
            logger.warning(f"Agent {agent_id} 缺少 SOUL.md，跳过")
            return None

        # 加载 AGENTS.md 获取路由规则
        routes = []
        tools = []
        heartbeat_interval = 300

        if agents_file.exists():
            try:
                from src.brain.agents_config import AgentsConfigLoader
                loader = AgentsConfigLoader()
                config = loader.load(agents_file)

                # 从 startup_behavior 推断一些配置
                # 这里可以添加更多解析逻辑

            except Exception as e:
                logger.error(f"加载 {agents_file} 失败: {e}")

        config = AgentConfig(
            id=agent_id,
            name=agent_id,
            soul_file=str(soul_file),
            user_file=str(user_file) if user_file.exists() else "",
            agents_file=str(agents_file) if agents_file.exists() else "",
            routes=routes,
            tools=tools,
            heartbeat_interval=heartbeat_interval,
        )

        return config

    def get_status(self) -> dict[str, Any]:
        """获取注册表状态"""
        return {
            "running": self._running,
            "agent_count": len(self._configs),
            "instance_count": len(self._agents),
            "agents": [
                {
                    "id": config.id,
                    "name": config.name,
                    "has_instance": config.id in self._agents,
                    "route_count": len(config.routes),
                }
                for config in self._configs.values()
            ],
        }
