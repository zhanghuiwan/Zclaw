"""
Agent 主类

Agent 的入口点和顶层协调器，负责初始化各模块并协调它们的工作。
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

import uuid

from src.config.settings import Settings
from src.core.loop import AgentLoop
from src.core.state import AgentState
from src.llm.models import Response, StreamEvent
from src.llm.router import LLMRouter
from src.sandbox.runner import CommandRunner
from src.security.permission import PermissionManager
from src.security.audit import AuditLogger
from src.memory.manager import MemoryManager
from src.mcp.manager import MCPManager
from src.tools.builtin.file_tools import FILE_TOOLS
from src.tools.builtin.search_tools import SEARCH_TOOLS
from src.tools.builtin.shell_tool import SHELL_TOOLS
from src.tools.builtin.grep_tool import GREP_TOOL
from src.tools.builtin.glob_tool import GLOB_TOOL
from src.tools.builtin.multi_edit_tool import MULTI_EDIT_TOOL
from src.tools.builtin.line_edit_tool import LINE_EDIT_TOOLS
from src.tools.builtin.diff_tool import DIFF_TOOLS
from src.tools.builtin.git_tool import GIT_TOOLS
from src.tools.builtin.ast_tool import AST_TOOLS
from src.tools.registry import ToolRegistry
from src.core.planner import Planner
from src.prompt.builder import PromptBuilder
from src.prompt.templates import DEFAULT_PERSONA
from src.skills.manager import SkillManager
from src.skills.config import SkillsConfig

logger = logging.getLogger(__name__)


DEFAULT_SYSTEM_PROMPT = """你是 Zclaw，一个强大的 AI 编程助手。

## 核心能力
- 读取、写入和修改代码文件
- 浏览目录结构和搜索文件
- 执行 Shell 命令
- 分析和解决编程问题

## 行为规则
1. 在行动之前理解用户需求，不确定时主动提问。
2. 使用 file_read 查看当前内容，然后再修改文件。
3. 提供准确、实用的回答。
4. 修改代码时考虑完整性和一致性。
5. 遇到错误时分析原因并提供解决方案。
6. 谨慎使用 shell 命令，避免破坏性操作。

## 工具使用指南
- **file_read**：读取文件内容，支持大文件的部分读取
- **file_write**：创建新文件或完全覆盖现有文件
- **file_edit**：精确修改文件内容的部分（推荐用于局部修改）
- **directory**：浏览目录结构
- **file_search**：按名称或内容搜索文件
- **shell**：执行 Shell 命令

## 输出格式
- 使用 Markdown 格式组织回答
- 代码块中标注语言类型
- 使用粗体或列表进行强调
"""


class Agent:
    """
    Agent 主类。

    职责：
    1. 初始化所有子模块（LLM、工具、记忆等）
    2. 提供统一的对话接口
    3. 协调子模块之间的交互
    """

    def __init__(self, settings: Settings, session_id: str | None = None):
        self._settings = settings
        self._session_id = session_id or uuid.uuid4().hex[:12]

        self._llm = LLMRouter(settings.llm)

        self._tools = ToolRegistry()

        # P7: 插件加载器和会话管理器
        from src.plugins.loader import PluginLoader
        from src.cli.session import SessionManager
        self._plugin_loader = PluginLoader()
        self._session_manager = SessionManager()

        self._init_builtin_tools()

        self._permissions = PermissionManager(config=settings.security)
        self._audit = AuditLogger(
            enabled=settings.security.audit_log,
            log_dir=settings.security.audit_log_path,
            session_id=self._session_id,
        )

        # P4+P8: 记忆模块（含自动提取和生命周期管理）
        from src.memory.extractor import create_extractor
        self._memory = MemoryManager(
            config=settings.memory,
            session_id=self._session_id,
            extractor=create_extractor(settings),
        )

        # P5: 上下文管理器
        default_max_tokens = 32768
        if settings.llm.default_provider in settings.llm.providers:
            default_max_tokens = settings.llm.providers[settings.llm.default_provider].max_context_tokens
        from src.context.manager import ContextManager
        self._context = ContextManager(config=settings.context, max_context_tokens=default_max_tokens)

        # P6: 规划器和提示词构建器
        self._planner = Planner()
        self._prompt_builder = PromptBuilder(persona=DEFAULT_PERSONA)

        # P10: Skill 管理器
        self._skill_manager = self._init_skills(settings)

        # P10: 将 skill 工具注册到工具注册表
        if self._skill_manager:
            skill_tools = self._skill_manager.get_skill_tools()
            if skill_tools:
                self._tools.register_many(skill_tools)
                logger.info(f"注册 {len(skill_tools)} 个 skill 工具: {[t.name for t in skill_tools]}")

        # P8: 构建初始 system prompt（含记忆上下文）
        initial_memory_ctx = self._memory.get_context()
        self._loop = AgentLoop(
            llm=self._llm,
            agent_config=settings.agent,
            system_prompt=self._prompt_builder.build(
                tool_names=self._tools.tool_names,
                memory_context=initial_memory_ctx,
            ),
            tool_registry=self._tools,
            permission_manager=self._permissions,
            audit_logger=self._audit,
            context_manager=self._context,
            memory_manager=self._memory,
            prompt_builder=self._prompt_builder,
        )

        logger.info(
            f"Agent initialized: {self._llm}, tools={len(self._tools)}, "
            f"session={self._session_id}, audit={'on' if self._audit.enabled else 'off'}, "
            f"skills={self._skill_manager.skill_count if self._skill_manager else 0}"
        )

    def _init_skills(self, settings: Settings) -> SkillManager | None:
        """初始化 Skill 管理器"""
        if not settings.skills.enabled:
            logger.info("Skills 功能已禁用")
            return None

        try:
            # 构建 Skills 配置
            from pathlib import Path
            # agent.py 在 src/core/ 目录下，需要向上两级到达项目根目录
            project_root = Path(__file__).resolve().parent.parent.parent

            # 使用 with_defaults 获取正确的项目路径（.agents/skills）
            skills_config = SkillsConfig.with_defaults(project_root=project_root)

            # 只覆盖需要从 settings 更新的字段
            skills_config.global_path = Path(settings.skills.global_path).expanduser()
            skills_config.auto_load = settings.skills.auto_load
            skills_config.inject_to_prompt = settings.skills.inject_to_prompt

            skill_manager = SkillManager(skills_config)
            skill_manager.initialize()
            return skill_manager
        except Exception as e:
            logger.error(f"初始化 Skills 失败：{e}")
            return None
            return None

    def _init_builtin_tools(self) -> None:
        all_tools = (
            FILE_TOOLS + SEARCH_TOOLS + SHELL_TOOLS + GREP_TOOL + GLOB_TOOL
            + MULTI_EDIT_TOOL + LINE_EDIT_TOOLS + DIFF_TOOLS + GIT_TOOLS + AST_TOOLS
        )
        self._tools.register_many(all_tools)
        logger.info(f"Registered {len(all_tools)} builtin tools: {[t.name for t in all_tools]}")

        # P7: 加载插件
        plugin_tools = self._plugin_loader.load_all()
        if plugin_tools:
            self._tools.register_many(plugin_tools)
            logger.info(f"Loaded {len(plugin_tools)} tool(s) from plugins")

        # P9: MCP 服务器集成
        self._mcp_manager = MCPManager(config_path=self._settings.mcp.config_path)
        # MCP 在初始化阶段不自动连接（需要 async），由 _init_mcp_tools 完成

    @property
    def loop(self) -> AgentLoop:
        return self._loop

    @property
    def llm(self) -> LLMRouter:
        return self._llm

    @property
    def tools(self) -> ToolRegistry:
        return self._tools

    @property
    def memory(self) -> MemoryManager:
        return self._memory

    @property
    def permission_manager(self) -> PermissionManager:
        return self._permissions

    @property
    def audit_logger(self) -> AuditLogger:
        return self._audit

    @property
    def context_manager(self):
        return self._context

    @property
    def mcp_manager(self) -> MCPManager:
        return self._mcp_manager

    @property
    def plugin_loader(self) -> PluginLoader:
        return self._plugin_loader

    @property
    def session_manager(self) -> SessionManager:
        return self._session_manager

    @property
    def planner(self) -> Planner:
        return self._planner

    @property
    def prompt_builder(self) -> PromptBuilder:
        return self._prompt_builder

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def state(self) -> AgentState:
        return self._loop.state

    async def init_mcp(self) -> int:
        """
        P9: 初始化 MCP 连接并注册工具。

        需要在 Agent 创建后手动调用（因为是 async 方法）。
        Returns:
            注册的 MCP 工具数量
        """
        if not self._settings.mcp.enabled or not self._settings.mcp.auto_connect:
            return 0
        try:
            mcp_tools = await self._mcp_manager.connect_all(
                config_path=self._settings.mcp.config_path,
            )
            if mcp_tools:
                self._tools.register_many(mcp_tools)
                # 更新 system prompt 以包含新的工具
                memory_ctx = self._memory.get_context()
                new_prompt = self._prompt_builder.build(
                    tool_names=self._tools.tool_names,
                    memory_context=memory_ctx,
                )
                self._loop.set_system_prompt(new_prompt)
                logger.info(f"已注册 {len(mcp_tools)} 个 MCP 工具")
            return len(mcp_tools)
        except Exception as e:
            logger.error(f"MCP 初始化失败: {e}")
            return 0

    async def shutdown_mcp(self) -> None:
        """P9: 断开所有 MCP 连接。"""
        count = await self._mcp_manager.disconnect_all()
        if count:
            logger.info(f"已断开 {count} 个 MCP 服务器连接")

    async def chat(self, user_input: str) -> Response:
        logger.info(f"User input: {user_input[:100]}...")
        # P8: 注入记忆上下文
        self._update_memory_context(user_input)
        response = await self._loop.run(user_input)
        # P8: 对话结束后自动提取记忆
        await self._memory.extract_from_conversation(self._loop.messages)
        return response

    async def chat_stream(self, user_input: str) -> AsyncIterator[StreamEvent]:
        logger.info(f"User input (stream): {user_input[:100]}...")
        # P8: 注入记忆上下文
        self._update_memory_context(user_input)
        async for event in self._loop.run_stream(user_input):
            yield event
        # P8: 对话结束后自动提取记忆
        await self._memory.extract_from_conversation(self._loop.messages)

    def _update_memory_context(self, user_input: str) -> None:
        """P8: 根据用户输入检索相关记忆并更新 system prompt。"""
        memory_ctx = self._memory.get_context(query=user_input)

        # P10: 同时注入 skill 上下文
        skill_ctx = ""
        if self._skill_manager:
            skill_ctx = self._skill_manager.get_context(query=user_input)

        if memory_ctx or skill_ctx:
            new_prompt = self._prompt_builder.build(
                tool_names=self._tools.tool_names,
                memory_context=memory_ctx,
                skill_context=skill_ctx if skill_ctx else None,
            )
            self._loop.set_system_prompt(new_prompt)
            logger.debug(f"已注入记忆上下文 ({len(memory_ctx) if memory_ctx else 0} 字符), "
                        f"skill 上下文 ({len(skill_ctx) if skill_ctx else 0} 字符)")

    def set_system_prompt(self, prompt: str) -> None:
        self._loop.set_system_prompt(prompt)

    def clear_history(self) -> None:
        self._loop.clear_history()

    def set_extractor(self, extractor) -> None:
        """P8: 替换记忆提取器（用于注入 LLM 提取器或测试 Mock）。"""
        self._memory.extractor = extractor

    def __repr__(self) -> str:
        return (
            f"Agent(state={self.state.value}, "
            f"provider={self._settings.llm.default_provider}, "
            f"model={self._settings.llm.providers[self._settings.llm.default_provider].model}, "
            f"tools={len(self._tools)}, session={self._session_id})"
        )
