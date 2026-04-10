"""
Skills 配置管理

定义 Skills 模块的配置结构。
"""

from __future__ import annotations

import logging
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SkillsConfig(BaseModel):
    """
    Skills 模块配置

    Attributes:
        enabled: 是否启用 skills 功能
        global_path: 全局 skill 目录路径 (默认 ~/.agents/skills)
        project_path: 项目级 skill 目录路径 (默认项目根目录/.agents/skills)
        auto_load: 启动时自动加载 skills
        match_threshold: 匹配阈值（低于此阈值的匹配将被忽略）
        inject_to_prompt: 是否自动注入到 system prompt
    """

    enabled: bool = True
    global_path: Path = Field(
        default_factory=lambda: Path.home() / ".agents" / "skills"
    )
    project_path: Path | None = None
    auto_load: bool = True
    match_threshold: int = 1
    inject_to_prompt: bool = True

    def get_effective_paths(self) -> list[Path]:
        """
        获取所有有效的搜索路径

        初始化时自动将全局 skills symlink 到项目目录。

        Returns:
            路径列表
        """
        paths = []

        # 项目路径（本地 skills）
        if self.project_path:
            # 如果不存在，尝试创建
            if not self.project_path.exists():
                try:
                    self.project_path.mkdir(parents=True, exist_ok=True)
                    logger.info(f"创建项目 skills 目录：{self.project_path}")
                except Exception as e:
                    logger.warning(f"无法创建项目 skills 目录：{e}")

            if self.project_path.exists():
                # 自动同步全局 skills 到项目目录
                if self.global_path and self.global_path.exists():
                    self._sync_from_global(self.project_path, self.global_path)

                paths.append(self.project_path)

        return paths

    def _sync_from_global(self, project_path: Path, global_path: Path) -> None:
        """
        从全局目录同步 skills 到项目目录（通过 symlink）

        Args:
            project_path: 项目 skills 目录
            global_path: 全局 skills 目录
        """
        try:
            for item in global_path.iterdir():
                if item.is_dir() and (item / "SKILL.md").exists():
                    target = project_path / item.name
                    if not target.exists():
                        # 创建 symlink
                        target.symlink_to(item.resolve())
                        logger.info(f"  同步 skill：{item.name}")
                    elif target.is_symlink() and not target.resolve().exists():
                        # 修复损坏的 symlink
                        target.unlink()
                        target.symlink_to(item.resolve())
                        logger.info(f"  修复并同步 skill：{item.name}")
        except Exception as e:
            logger.warning(f"同步全局 skills 失败：{e}")

    def set_project_root(self, project_root: Path) -> None:
        """
        设置项目根目录，自动计算项目级 skill 路径

        Args:
            project_root: 项目根目录
        """
        self.project_path = project_root / ".agents" / "skills"

    @classmethod
    def with_defaults(cls, project_root: Path | None = None) -> "SkillsConfig":
        """
        使用默认配置创建实例

        Args:
            project_root: 项目根目录（可选）
        """
        config = cls()
        if project_root:
            config.set_project_root(project_root)
        return config
