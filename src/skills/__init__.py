"""
Skills 模块

Zclaw 的 Agent Skills 支持，遵循 Claude Code / OpenClaw 通用标准。

核心功能:
- 从 ~/.agents/skills/ 和项目 .agents/skills/ 目录加载 SKILL.md
- 根据用户输入自动匹配相关 skills
- 将 skill 内容注入到 LLM 上下文
- 执行 skill 定义的操作

用法:
    from src.skills import SkillManager, SkillsConfig

    config = SkillsConfig.with_defaults(project_root=PROJECT_ROOT)
    manager = SkillManager(config)
    manager.initialize()

    # 获取匹配的 skills
    matches = manager.match_skills("搜索附近的美食")

    # 执行 skill
    result = manager.execute_skill("amap-lbs-skill", "搜索西直门周边美食")
"""

from .config import SkillsConfig
from .executor import SkillExecutor, SkillResult
from .loader import SkillLoader
from .manager import SkillManager
from .models import SkillDefinition, SkillRequirements
from .registry import SkillRegistry
from .tool import SkillTool

__all__ = [
    # 配置
    "SkillsConfig",
    # 管理器
    "SkillManager",
    # 加载器
    "SkillLoader",
    # 注册表
    "SkillRegistry",
    # 执行器
    "SkillExecutor",
    # 数据模型
    "SkillDefinition",
    "SkillRequirements",
    # 执行结果
    "SkillResult",
    # 工具包装器
    "SkillTool",
]

__version__ = "0.6.1"
