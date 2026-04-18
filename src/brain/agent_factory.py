"""
AgentFactory - Agent 工厂

将 Gateway 与现有 Agent 类连接，负责从配置文件创建 Agent 实例。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.config.settings import Settings
from src.brain.soul_loader import SoulLoader, Soul
from src.brain.user_profile import UserProfileLoader, UserProfile
from src.brain.agents_config import AgentsConfigLoader, AgentBehaviorConfig

logger = logging.getLogger(__name__)


class AgentFactory:
    """
    Agent 工厂

    职责：
    1. 从 agents/ 目录加载配置
    2. 创建 Settings 对象
    3. 创建 Agent 实例并注册工具
    """

    def __init__(self, agents_dir: str | Path = "agents"):
        self._agents_dir = Path(agents_dir)
        self._settings_cache: dict[str, Settings] = {}
        self._soul_cache: dict[str, Soul] = {}
        self._user_cache: dict[str, UserProfile] = {}
        self._behavior_cache: dict[str, AgentBehaviorConfig] = {}

        self._soul_loader = SoulLoader()
        self._user_loader = UserProfileLoader()
        self._agents_loader = AgentsConfigLoader()

    def load_agents_from_directory(self) -> list[str]:
        """
        从 agents 目录加载所有 Agent 配置。

        Returns:
            list[str]: 加载的 Agent ID 列表
        """
        if not self._agents_dir.exists():
            logger.warning(f"agents 目录不存在: {self._agents_dir}")
            return []

        agent_ids = []
        for agent_dir in self._agents_dir.iterdir():
            if not agent_dir.is_dir():
                continue

            soul_file = agent_dir / "SOUL.md"
            if not soul_file.exists():
                logger.warning(f"Agent {agent_dir.name} 缺少 SOUL.md，跳过")
                continue

            agent_ids.append(agent_dir.name)

            # 预加载配置
            self._load_agent_config(agent_dir.name)

        logger.info(f"从 {self._agents_dir} 加载了 {len(agent_ids)} 个 Agent 配置: {agent_ids}")
        return agent_ids

    def _load_agent_config(self, agent_id: str) -> None:
        """加载单个 Agent 的配置到缓存"""
        if agent_id in self._settings_cache:
            return

        agent_dir = self._agents_dir / agent_id

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

        # 构建 Settings
        settings = self._build_settings(agent_id, soul, user, behavior)
        self._settings_cache[agent_id] = settings

    def _build_settings(
        self,
        agent_id: str,
        soul: Soul,
        user: UserProfile,
        behavior: AgentBehaviorConfig,
    ) -> Settings:
        """根据配置构建 Settings 对象"""
        from src.config.settings import (
            Settings,
            LLMConfig,
            AgentConfig,
            MemoryConfig,
            ContextConfig,
            MCPConfig,
            WebConfig,
            SecurityConfig,
            SkillsConfig,
            ProviderConfig,
        )

        # 使用默认的 LLM 配置（可以从 USER.md 或环境变量获取）
        providers = {
            "default": ProviderConfig(
                base_url="https://api.minimaxi.com/v1",
                api_key="",
                model="MiniMax-M2.7",
                max_context_tokens=32768,
                supports_tools=True,
                supports_streaming=True,
            )
        }

        llm_config = LLMConfig(
            default_provider="default",
            providers=providers,
            temperature=0.3,
            max_tokens=8192,
        )

        agent_config = AgentConfig(
            max_loop_rounds=50,
            planning_mode="auto",
        )

        memory_config = MemoryConfig(
            storage_path=f".Zclaw/agents/{agent_id}/memory",
            working_memory_max_tokens=30000,
            episodic_max_age_days=90,
        )

        context_config = ContextConfig(
            safety_margin_ratio=0.1,
        )

        mcp_config = MCPConfig(
            enabled=True,
            auto_connect=False,  # 启动时不自动连接，需要时再连接
        )

        web_config = WebConfig(
            enabled=True,
            host="0.0.0.0",
            port=8080,
        )

        security_config = SecurityConfig(
            auto_approve=["file_read", "directory", "file_search", "grep", "glob"],
            audit_log=True,
        )

        skills_config = SkillsConfig(
            enabled=True,
            auto_load=True,
            inject_to_prompt=True,
        )

        settings = Settings(
            llm=llm_config,
            agent=agent_config,
            memory=memory_config,
            context=context_config,
            mcp=mcp_config,
            web=web_config,
            security=security_config,
            skills=skills_config,
        )

        return settings

    def get_settings(self, agent_id: str) -> Settings | None:
        """获取 Agent 的 Settings"""
        if agent_id not in self._settings_cache:
            if not (self._agents_dir / agent_id / "SOUL.md").exists():
                return None
            self._load_agent_config(agent_id)

        return self._settings_cache.get(agent_id)

    def get_soul(self, agent_id: str) -> Soul | None:
        """获取 Agent 的 Soul"""
        if agent_id not in self._soul_cache:
            if not (self._agents_dir / agent_id / "SOUL.md").exists():
                return None
            self._load_agent_config(agent_id)

        return self._soul_cache.get(agent_id)

    def get_user_profile(self, agent_id: str) -> UserProfile | None:
        """获取 Agent 的 UserProfile"""
        if agent_id not in self._user_cache:
            if not (self._agents_dir / agent_id / "SOUL.md").exists():
                return None
            self._load_agent_config(agent_id)

        return self._user_cache.get(agent_id)

    def get_behavior_config(self, agent_id: str) -> AgentBehaviorConfig | None:
        """获取 Agent 的行为配置"""
        if agent_id not in self._behavior_cache:
            if not (self._agents_dir / agent_id / "SOUL.md").exists():
                return None
            self._load_agent_config(agent_id)

        return self._behavior_cache.get(agent_id)

    async def create_agent(self, agent_id: str = "default") -> Any:
        """
        创建 Agent 实例。

        Args:
            agent_id: Agent ID

        Returns:
            Agent: 创建的 Agent 实例
        """
        settings = self.get_settings(agent_id)
        if settings is None:
            logger.error(f"Agent 配置不存在: {agent_id}")
            raise ValueError(f"Agent 配置不存在: {agent_id}")

        # 创建 Agent
        from src.core.agent import Agent
        agent = Agent(settings=settings, session_id=agent_id)

        # 注册新工具
        await self._register_extra_tools(agent, agent_id)

        # 设置系统提示词（使用 Soul）
        soul = self.get_soul(agent_id)
        if soul:
            system_prompt = self._soul_loader.to_system_prompt(soul)
            # 在现有 system prompt 基础上添加 Soul 信息
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

            # 创建 BrowserTool 并注册
            browser_tool = BrowserTool(headless=True)
            agent.tools.register(browser_tool)
            logger.info(f"已注册 BrowserTool 到 Agent {agent_id}")

            # 创建 ProcessTool 并注册
            process_tool = ProcessTool()
            agent.tools.register(process_tool)
            logger.info(f"已注册 ProcessTool 到 Agent {agent_id}")

        except ImportError as e:
            logger.warning(f"无法注册额外工具: {e}")

    def list_agents(self) -> list[str]:
        """列出所有已加载的 Agent ID"""
        return list(self._settings_cache.keys())

    def get_status(self) -> dict[str, Any]:
        """获取 AgentFactory 状态"""
        return {
            "agents_dir": str(self._agents_dir),
            "loaded_agents": list(self._settings_cache.keys()),
            "agent_count": len(self._settings_cache),
        }
