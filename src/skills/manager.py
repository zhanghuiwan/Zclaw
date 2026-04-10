"""
Skill 管理器

统一管理所有 Skills 的加载、注册和执行。
"""

from __future__ import annotations

import logging
from pathlib import Path

from .config import SkillsConfig
from .executor import SkillExecutor, SkillResult
from .loader import SkillLoader
from .models import SkillDefinition
from .registry import SkillRegistry
from .tool import SkillTool

logger = logging.getLogger(__name__)


class SkillManager:
    """
    Skill 管理器

    统一入口，管理所有 skills 的生命周期。

    用法:
        config = SkillsConfig.with_defaults(project_root=Path("/path/to/project"))
        manager = SkillManager(config)
        manager.initialize()

        # 查询匹配的 skills
        matches = manager.match_skills("搜索附近的美食")

        # 执行 skill
        result = manager.execute("amap-lbs-skill", "搜索西直门周边美食")
    """

    def __init__(self, config: SkillsConfig | None = None):
        """
        初始化 SkillManager

        Args:
            config: Skills 配置，None 则使用默认配置
        """
        self._config = config or SkillsConfig()
        self._registry = SkillRegistry()
        self._loader = SkillLoader()
        self._executor = SkillExecutor()
        self._initialized = False

        self._setup_search_paths()

    def _setup_search_paths(self) -> None:
        """配置搜索路径，只使用有效的项目路径"""
        # 清空之前的搜索路径
        self._loader.clear_search_paths()

        # 使用 effective_paths（只包含项目目录）
        for path in self._config.get_effective_paths():
            self._loader.add_search_path(path, exist_ok=True)

    def initialize(self) -> int:
        """
        初始化：加载所有 skills

        Returns:
            成功加载的 skill 数量
        """
        if self._initialized:
            logger.warning("SkillManager 已初始化，跳过")
            return self._registry.count()

        if not self._config.enabled:
            logger.info("Skills 功能已禁用")
            self._initialized = True
            return 0

        logger.info("开始加载 skills...")

        # 加载所有 skills
        skills = self._loader.load_all_skills()

        # 注册到 registry
        for skill in skills:
            self._registry.register(skill)

        self._initialized = True
        logger.info(f"Skills 初始化完成，共加载 {len(skills)} 个 skills")

        return len(skills)

    def match_skills(self, query: str) -> list[SkillDefinition]:
        """
        根据用户查询匹配相关的 skills

        Args:
            query: 用户输入

        Returns:
            匹配的 skill 列表
        """
        if not self._config.enabled:
            return []

        matches = self._registry.match(query)

        # 过滤低于阈值的匹配
        threshold = self._config.match_threshold
        if threshold > 0 and matches:
            # 简单过滤：至少有触发词匹配
            filtered = []
            for skill in matches:
                if any(trigger in query for trigger in skill.triggers):
                    filtered.append(skill)
            matches = filtered or matches[:1]  # 至少保留一个

        return matches

    def get_skill(self, name: str) -> SkillDefinition | None:
        """
        根据名称获取 skill

        Args:
            name: skill 名称

        Returns:
            SkillDefinition 或 None
        """
        return self._registry.get(name)

    def execute_skill(
        self,
        name: str,
        arguments: str = ""
    ) -> SkillResult:
        """
        执行指定的 skill

        Args:
            name: skill 名称
            arguments: 执行参数

        Returns:
            SkillResult 执行结果
        """
        skill = self._registry.get(name)
        if not skill:
            return SkillResult(
                success=False,
                skill_name=name,
                error=f"Skill '{name}' 不存在",
            )

        return self._executor.execute(skill, arguments)

    def get_context(self, query: str) -> str:
        """
        根据查询获取 skill 上下文

        用于注入到 system prompt 中。

        Args:
            query: 用户输入

        Returns:
            渲染后的 skill 上下文
        """
        if not self._config.enabled:
            return ""

        matches = self.match_skills(query)

        if not matches:
            # 返回简短的 skills 摘要
            return self._registry.get_context_summary()

        # 返回匹配的完整 skill 内容
        contexts = []
        for skill in matches:
            if self._config.inject_to_prompt:
                contexts.append(
                    f"\n--- Skill: {skill.name} ---\n"
                    f"{skill.to_prompt()}\n"
                    f"--- End Skill: {skill.name} ---\n"
                )

        if not contexts:
            return self._registry.get_context_summary()

        return "\n".join(contexts)

    def list_skills(self) -> list[SkillDefinition]:
        """列出所有已注册的 skills"""
        return self._registry.list_all()

    def reload_skills(self) -> int:
        """
        重新加载所有 skills

        Returns:
            重新加载的 skill 数量
        """
        self._registry = SkillRegistry()
        skills = self._loader.load_all_skills()

        for skill in skills:
            self._registry.register(skill)

        logger.info(f"重新加载 {len(skills)} 个 skills")
        return len(skills)

    @property
    def is_enabled(self) -> bool:
        """是否启用"""
        return self._config.enabled

    @property
    def skill_count(self) -> int:
        """已加载的 skill 数量"""
        return self._registry.count()

    def get_skill_tools(self) -> list[SkillTool]:
        """
        获取所有 skill 工具

        返回包装为 SkillTool 的列表，可注册到 Agent 的工具注册表。

        Returns:
            SkillTool 列表
        """
        tools = []
        for skill in self._registry.list_all():
            tool = SkillTool(skill)
            tools.append(tool)
        return tools

    def register_custom_executor(
        self,
        skill_name: str,
        executor: callable
    ) -> None:
        """
        注册自定义 skill 执行器

        Args:
            skill_name: skill 名称
            executor: 执行函数
        """
        self._executor.register_executor(skill_name, executor)
        logger.debug(f"注册自定义 skill 执行器：{skill_name}")
