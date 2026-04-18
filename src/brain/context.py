"""
Context Assembler - 上下文组装器

组装 Agent 的完整上下文，包括 SOUL、USER、记忆、可用工具等。
"""

from __future__ import annotations

import logging
from typing import Any

from src.brain.soul_loader import Soul, SoulLoader
from src.brain.user_profile import UserProfile, UserProfileLoader
from src.brain.agents_config import AgentBehaviorConfig, AgentsConfigLoader

logger = logging.getLogger(__name__)


class ContextAssembler:
    """
    上下文组装器

    将 SOUL、USER、记忆、工具等信息组装成完整的上下文，
    供 Agent 使用。
    """

    def __init__(
        self,
        soul_loader: SoulLoader | None = None,
        user_loader: UserProfileLoader | None = None,
        agents_loader: AgentsConfigLoader | None = None,
    ):
        self._soul_loader = soul_loader or SoulLoader()
        self._user_loader = user_loader or UserProfileLoader()
        self._agents_loader = agents_loader or AgentsConfigLoader()

    def assemble(
        self,
        soul: Soul,
        user_profile: UserProfile,
        behavior_config: AgentBehaviorConfig | None = None,
        recent_memories: list[str] | None = None,
        available_tools: list[str] | None = None,
        additional_context: dict[str, Any] | None = None,
    ) -> str:
        """
        组装完整上下文。

        Args:
            soul: Soul 配置
            user_profile: 用户配置
            behavior_config: 行为配置
            recent_memories: 最近的记忆片段
            available_tools: 可用工具列表
            additional_context: 额外的上下文

        Returns:
            str: 组装后的上下文字符串
        """
        sections = []

        # 1. Soul 部分
        soul_prompt = self._soul_loader.to_system_prompt(soul)
        sections.append(soul_prompt)

        # 2. User 部分
        user_context = self._user_loader.to_context_string(user_profile)
        sections.append(user_context)

        # 3. 行为规则
        if behavior_config and behavior_config.startup_behavior:
            sections.append("## 行为规则")
            for behavior in behavior_config.startup_behavior:
                sections.append(f"- {behavior}")
            sections.append("")

        # 4. 最近的记忆
        if recent_memories:
            sections.append("## 近期上下文")
            for i, memory in enumerate(recent_memories, 1):
                sections.append(f"{i}. {memory}")
            sections.append("")

        # 5. 可用工具
        if available_tools:
            sections.append("## 可用工具")
            sections.append(f"共 {len(available_tools)} 个工具可用：")
            sections.append(", ".join(available_tools))
            sections.append("")

        # 6. 额外的上下文
        if additional_context:
            sections.append("## 额外上下文")
            for key, value in additional_context.items():
                sections.append(f"- {key}: {value}")
            sections.append("")

        return "\n\n".join(sections)

    def assemble_from_paths(
        self,
        soul_path: str | None,
        user_path: str | None,
        agents_path: str | None,
        **kwargs,
    ) -> str:
        """
        从文件路径组装上下文。

        Args:
            soul_path: SOUL.md 文件路径
            user_path: USER.md 文件路径
            agents_path: AGENTS.md 文件路径
            **kwargs: 其他参数传递给 assemble

        Returns:
            str: 组装后的上下文字符串
        """
        soul = self._soul_loader.load(soul_path) if soul_path else Soul()
        user_profile = self._user_loader.load(user_path) if user_path else UserProfile()
        behavior_config = self._agents_loader.load(agents_path) if agents_path else None

        return self.assemble(
            soul=soul,
            user_profile=user_profile,
            behavior_config=behavior_config,
            **kwargs,
        )
